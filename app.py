"""
Pic {AI} sso - Streamlit Application

A workshop game where users describe images and AI generates new images
based on those descriptions, creating a "telephone game" effect.
"""

import base64
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from io import BytesIO
from typing import Dict, Optional

import streamlit as st
from google.cloud import storage
from google.oauth2 import service_account
from openai import OpenAI
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
IMG_WIDTH = 400
NUM_TRACKS = 4
LOCK_TIMEOUT_MINUTES = 10
OPENAI_MODEL = "gpt-image-2"
OPENAI_IMAGE_QUALITY = "low"
OPENAI_IMAGE_SIZE = "1024x1024"

# GCS blob name constants
GCS_GAME_STATE_BLOB = "game_state.json"
GCS_IMAGES_PREFIX = "images/"
STARTING_IMAGE_BLOBS = [f"images/track_{i}_image_000.png" for i in range(NUM_TRACKS)]

# Password protection
PASSWORD_HASH = st.secrets["PICAISSO_PASSWORD_HASH"]


def get_openai_client() -> OpenAI:
    """Return a cached OpenAI client."""
    if "openai_client" not in st.session_state:
        api_key = st.secrets["OPENAI_KEY"]
        if not api_key:
            st.error("OPENAI_KEY not found in secrets.")
            st.stop()
        st.session_state.openai_client = OpenAI(api_key=api_key)
    return st.session_state.openai_client


@st.cache_resource
def get_gcs_bucket() -> storage.Bucket:
    """Return a cached GCS bucket client built from st.secrets."""
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = service_account.Credentials.from_service_account_info(creds_dict)
    client = storage.Client(credentials=creds, project=creds_dict["project_id"])
    return client.bucket(st.secrets["GCP_BUCKET_NAME"])


# ── GCS storage helpers ────────────────────────────────────────────────────────

def load_image_gcs(blob_name: str) -> Optional[Image.Image]:
    """Download a blob from GCS and return it as a PIL Image."""
    try:
        bucket = get_gcs_bucket()
        blob = bucket.blob(blob_name)
        if not blob.exists():
            logger.warning("Image blob not found in GCS: %s", blob_name)
            return None
        image_bytes = blob.download_as_bytes()
        return Image.open(BytesIO(image_bytes)).copy()
    except Exception as e:
        logger.error("Failed to load image from GCS %s: %s", blob_name, e)
        return None


def save_image_gcs(image: Image.Image, blob_name: str) -> bool:
    """Upload a PIL Image as PNG to GCS."""
    try:
        bucket = get_gcs_bucket()
        buf = BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)
        bucket.blob(blob_name).upload_from_file(buf, content_type="image/png")
        logger.info("Image saved to GCS: %s", blob_name)
        return True
    except Exception as e:
        logger.error("Failed to save image to GCS %s: %s", blob_name, e)
        return False


def load_game_state() -> Dict:
    """Load game state from GCS."""
    try:
        bucket = get_gcs_bucket()
        blob = bucket.blob(GCS_GAME_STATE_BLOB)
        if blob.exists():
            state = json.loads(blob.download_as_text())
            if "tracks" not in state:
                state = _init_game_state()
            if "locks" not in state:
                state["locks"] = {
                    str(i): {"locked": False, "session_id": None, "timestamp": None}
                    for i in range(NUM_TRACKS)
                }
            return state
    except Exception as e:
        logger.error("Failed to load game state from GCS: %s", e)
    return _init_game_state()


def save_game_state(game_state: Dict) -> None:
    """Save game state to GCS."""
    try:
        bucket = get_gcs_bucket()
        bucket.blob(GCS_GAME_STATE_BLOB).upload_from_string(
            json.dumps(game_state, indent=2),
            content_type="application/json",
        )
        logger.info("Game state saved to GCS.")
    except Exception as e:
        logger.error("Failed to save game state to GCS: %s", e)
        st.error("Failed to save game state. Please try again.")


def _init_game_state() -> Dict:
    """Return a fresh game state structure."""
    return {
        "tracks": {str(i): {"history": []} for i in range(NUM_TRACKS)},
        "locks": {
            str(i): {"locked": False, "session_id": None, "timestamp": None}
            for i in range(NUM_TRACKS)
        },
    }


# ── Image generation ───────────────────────────────────────────────────────────

def generate_image(prompt: str) -> Optional[Image.Image]:
    """Generate an image via the OpenAI API and return it as a PIL Image."""
    try:
        client = get_openai_client()
        response = client.images.generate(
            model=OPENAI_MODEL,
            prompt=prompt,
            n=1,
            size=OPENAI_IMAGE_SIZE,
            quality=OPENAI_IMAGE_QUALITY,
        )
        # gpt-image-2 returns base64-encoded image data by default
        image_b64 = response.data[0].b64_json
        if not image_b64:
            logger.error("Image generation returned empty base64 data")
            return None
        image_bytes = base64.b64decode(image_b64)
        return Image.open(BytesIO(image_bytes))
    except Exception as e:
        logger.error("Image generation failed (%s): %s", type(e).__name__, e)
        return None


# ── Game state helpers ─────────────────────────────────────────────────────────

def initialize_session_state() -> None:
    """Initialize Streamlit session state variables."""
    defaults = {
        "generating": False,
        "game_loaded": False,
        "session_id": str(uuid.uuid4()),
        "selected_track": None,
        "user_name": None,
        "current_view": "onboarding",
        "generated_image_data": None,
        "show_prompting_tips": False,
        "disclaimer_accepted": False,
        "authenticated": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_next_image_number(game_state: Dict, track_id: int) -> int:
    return len(game_state["tracks"][str(track_id)]["history"])


def get_current_image_blob(game_state: Dict, track_id: int) -> str:
    image_num = len(game_state["tracks"][str(track_id)]["history"])
    return f"{GCS_IMAGES_PREFIX}track_{track_id}_image_{image_num:03d}.png"


def check_and_release_expired_locks(game_state: Dict) -> Dict:
    now = datetime.now()
    for track_id in range(NUM_TRACKS):
        lock = game_state["locks"][str(track_id)]
        if lock["locked"] and lock["timestamp"]:
            lock_time = datetime.fromisoformat(lock["timestamp"])
            if now - lock_time > timedelta(minutes=LOCK_TIMEOUT_MINUTES):
                logger.info("Releasing expired lock on track %s", track_id)
                lock["locked"] = False
                lock["session_id"] = None
                lock["timestamp"] = None
    return game_state


def is_track_locked(game_state: Dict, track_id: int) -> bool:
    return game_state["locks"][str(track_id)]["locked"]


def lock_track(game_state: Dict, track_id: int, session_id: str) -> Dict:
    game_state["locks"][str(track_id)] = {
        "locked": True,
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
    }
    return game_state


def release_track(game_state: Dict, track_id: int) -> Dict:
    game_state["locks"][str(track_id)] = {"locked": False, "session_id": None, "timestamp": None}
    return game_state


def can_user_access_track(game_state: Dict, track_id: int, session_id: str) -> bool:
    lock = game_state["locks"][str(track_id)]
    return not lock["locked"] or lock["session_id"] == session_id


# ── View helpers ───────────────────────────────────────────────────────────────

def display_current_image(game_state: Dict, track_id: int) -> None:
    current_blob = get_current_image_blob(game_state, track_id)
    image = load_image_gcs(current_blob)

    if image:
        st.image(image, width=IMG_WIDTH)
    else:
        starting_image = load_image_gcs(STARTING_IMAGE_BLOBS[track_id])
        if starting_image:
            st.image(starting_image, width=IMG_WIDTH)
        else:
            st.warning(f"No image found for Track {track_id + 1}.")
            st.info(f"Upload a starting image to GCS as: `{STARTING_IMAGE_BLOBS[track_id]}`")


# ── Views ──────────────────────────────────────────────────────────────────────

@st.dialog("🔐 Enter Password")
def show_password_dialog() -> None:
    """Show password entry dialog."""
    st.markdown("Please enter the password to play:")
    password = st.text_input("Password:", type="password", key="password_input")
    if st.button("Submit", type="primary", use_container_width=True):
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if password_hash == PASSWORD_HASH:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ Incorrect password. Please try again.")


@st.dialog("👋 Welcome to Pic{AI}sso 🎨 — Please Read First")
def show_disclaimer_dialog() -> None:
    st.info(
        "**This app uses my personal OpenAI API Key**.\n\n"
        "Every image you generate has a small but real cost — please be mindful and avoid unnecessary generations.\n\n"
        "Thank you & have fun 💛\n\n"
        "Elliot Kovanda"

    )
    st.error(
        "⚠️ **This is a public application.** Do NOT enter any internal company information, "
        "confidential data, client names, or sensitive content. "
        "Keep all descriptions limited to public, shareable content only. "
        "Note, that other players will see the images you generate and the prompts you enter. Thus, enter only work-appropriate, non-confidential descriptions."
    )
    st.markdown("By clicking below you confirm you have read and understood the above.")
    if st.button("✅ I understand, let me play!", type="primary", use_container_width=True):
        st.session_state.disclaimer_accepted = True
        st.rerun()


def render_onboarding_view() -> None:
    st.title("Welcome to Pic {AI} sso 🎨!")
    st.info("""
    Pic{AI}sso 🎨 is a game where you'll try to closely recreate an existing image by prompting an AI.
    As more people join in we can watch the chain evolve like the "Telephone Game" ("Stille Post").
    """)
    st.markdown("""
    ### How to Play

    1. **Choose a track** - Pick any available image track
    2. **Describe what you see** - Write a detailed description of the image
    3. **AI generates** - The AI creates a new image based on your description
    4. **See the evolution** - Watch how the image evolves across many iterations

    The goal is to practice **clear, precise prompting**. The more descriptive you are,
    the better the AI can recreate the image!
                
    The UI is in English for inclusivity but feel free to write your prompts in German if you prefer.
    """)
    st.markdown("---")
    name_input = st.text_input(
        "Enter your first name to begin:", placeholder="Your name...", key="onboarding_name_input"
    )
    if st.button("🚀 Start Playing", type="primary", disabled=not name_input.strip()):
        st.session_state.user_name = name_input.strip()
        st.session_state.current_view = "track_selection"
        st.rerun()


def render_track_selection_view(game_state: Dict) -> None:
    col_title, col_gallery = st.columns([3, 1])
    with col_title:
        st.title("🎨 Pic{AI}sso")
    with col_gallery:
        st.markdown("")
        if st.button("📸 Gallery", use_container_width=False):
            st.session_state.current_view = "gallery"
            st.rerun()

    st.markdown(f"**Welcome, {st.session_state.user_name}!** Choose an available track to start:")
    st.markdown("---")

    for track_id in range(NUM_TRACKS):
        is_locked = is_track_locked(game_state, track_id)
        can_access = can_user_access_track(game_state, track_id, st.session_state.session_id)

        with st.container():
            col_img, col_info = st.columns([1, 2])
            with col_img:
                current_blob = get_current_image_blob(game_state, track_id)
                image = load_image_gcs(current_blob)
                if image:
                    st.image(image, width=IMG_WIDTH)
                else:
                    starting_image = load_image_gcs(STARTING_IMAGE_BLOBS[track_id])
                    if starting_image:
                        st.image(starting_image, width=IMG_WIDTH)
                    else:
                        st.info(f"Track {track_id + 1}: No image available")

            with col_info:
                st.markdown(f"### Track {track_id + 1}")
                if is_locked and not can_access:
                    st.error("🔒 **Locked**")
                    st.caption("Someone is currently working on this track")
                else:
                    st.success("✅ **Available**")

                if is_locked and not can_access:
                    st.button("Select Track", key=f"track_select_{track_id}", disabled=True)
                else:
                    if st.button("Select Track", key=f"track_select_{track_id}", type="primary"):
                        game_state = lock_track(game_state, track_id, st.session_state.session_id)
                        save_game_state(game_state)
                        st.session_state.selected_track = track_id
                        st.session_state.current_view = "playing"
                        st.rerun()

        st.markdown("---")


def render_prompting_tips() -> None:
    with st.expander("### 🎨 Quick Tips for Better Image Prompts"):
        st.write("""
##### 🖌️ Style
Say the **type** of image you want: *photo, illustration, 3D render, watercolor* 🎭

##### 🧩 Composition
Name the **main object(s)** and how they're arranged: *close‑up, wide shot, centered, in the background* 📐

##### 🌈 Colors & Light
Add color vibes and lighting: *pastel, neon, warm tones, golden hour, dramatic shadows* 💡

##### 🌤️ Mood
Describe the feeling: *cozy, mysterious, playful, dreamy* ✨

---

**👎 Poor:** *A robot on a leaf*

**👍 Better:** *A crayon drawing of a tiny robot on a giant leaf, soft morning light*
""")


def render_playing_view(game_state: Dict) -> None:
    track_id = st.session_state.selected_track

    if not can_user_access_track(game_state, track_id, st.session_state.session_id):
        st.error("⚠️ You no longer have access to this track. It may have been claimed by someone else.")
        st.session_state.selected_track = None
        st.session_state.current_view = "track_selection"
        if st.button("Back to Track Selection"):
            st.rerun()
        st.stop()

    col_back, col_title = st.columns([1, 5])
    with col_back:
        if st.button("← Back"):
            game_state = release_track(game_state, track_id)
            save_game_state(game_state)
            st.session_state.selected_track = None
            st.session_state.current_view = "track_selection"
            st.rerun()
    with col_title:
        st.title(f"Track {track_id + 1}")

    st.info(
        "📝 **How to play:** Look at the image on the right and describe what you see in detail. "
        "The AI will create a new image based on your description. Try to get as close to the original as you can ☺️"
    )
    st.markdown("---")

    col_left, col_right = st.columns([1, 2])

    with col_left:
        render_prompting_tips()
        st.markdown("### Your Description")
        description = st.text_area(
            "Describe what you see in the image:",
            placeholder="E.g. A pencil drawing of...",
            height=200,
            key="description_input",
            help="Be as detailed as possible! Include colors, objects, positions, and atmosphere.",
        )

        if st.button("🎨 Generate Image", type="primary", disabled=st.session_state.generating):
            if not description.strip():
                st.error("Please enter a description before generating!")
            else:
                st.session_state.generating = True
                with st.spinner("✨ Generating your image... This may take a moment..."):
                    try:
                        generated_image = generate_image(description)
                        if generated_image is not None:
                            next_image_num = get_next_image_number(game_state, track_id)
                            next_image_filename = f"track_{track_id}_image_{next_image_num + 1:03d}.png"
                            next_image_blob = f"{GCS_IMAGES_PREFIX}{next_image_filename}"

                            if save_image_gcs(generated_image, next_image_blob):
                                game_state["tracks"][str(track_id)]["history"].append(
                                    {
                                        "image_filename": next_image_filename,
                                        "prompt_text": description.strip(),
                                        "user_name": st.session_state.user_name,
                                        "timestamp": datetime.now().isoformat(),
                                    }
                                )
                                game_state = release_track(game_state, track_id)
                                save_game_state(game_state)
                                st.session_state.generated_image_data = {
                                    "image_blob": next_image_blob,
                                    "prompt": description.strip(),
                                    "track_id": track_id,
                                }
                                st.session_state.generating = False
                                st.session_state.selected_track = None
                                st.session_state.current_view = "success"
                                st.rerun()
                            else:
                                st.error("❌ Failed to save image to GCS. Please try again.")
                                st.session_state.generating = False
                        else:
                            st.error("❌ Failed to generate image. Please try again.")
                            st.session_state.generating = False
                    except Exception as e:
                        logger.error("Error during image generation: %s", e)
                        st.error(f"❌ An error occurred: {str(e)}")
                        st.session_state.generating = False

    with col_right:
        st.markdown("### Target Image")
        display_current_image(game_state, track_id)

    st.markdown("---")


def render_success_view(game_state: Dict) -> None:
    if not st.session_state.generated_image_data:
        st.session_state.current_view = "track_selection"
        st.rerun()
        return

    data = st.session_state.generated_image_data
    st.balloons()
    st.title("🎉 Success!")
    st.success(f"**{st.session_state.user_name}**, your image has been generated!")
    st.markdown("---")
    st.markdown("### Your Generated Image")
    generated_image = load_image_gcs(data["image_blob"])
    if generated_image:
        st.image(generated_image, width=IMG_WIDTH)
    with st.expander("📝 Your Prompt"):
        st.write(data["prompt"])
    st.markdown("---")
    st.markdown("### What's Next?")
    st.markdown("View the gallery to see how your image fits into the track's evolution!")
    if st.button("📸 View Track Gallery", type="primary"):
        st.session_state.current_view = "gallery"
        st.session_state.gallery_selected_track = data["track_id"]
        st.session_state.generated_image_data = None
        st.rerun()


def render_gallery_view(game_state: Dict) -> None:
    col_back, col_title = st.columns([1, 5])
    with col_back:
        if st.button("← Back to Play"):
            st.session_state.current_view = "track_selection"
            st.rerun()
    with col_title:
        st.title("📸 Gallery")

    st.markdown("---")
    if "gallery_selected_track" not in st.session_state:
        st.session_state.gallery_selected_track = 0

    track_options = [f"Track {i + 1}" for i in range(NUM_TRACKS)]
    selected_track_name = st.selectbox(
        "Select Track to View:",
        track_options,
        index=st.session_state.gallery_selected_track,
        key="gallery_track_selector",
    )
    selected_track_id = int(selected_track_name.split()[1]) - 1
    st.session_state.gallery_selected_track = selected_track_id

    track_history = game_state["tracks"][str(selected_track_id)]["history"]
    total_images = len(track_history) + 1
    unique_users = len(set(entry["user_name"] for entry in track_history)) if track_history else 0

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Images", total_images)
    with col2:
        st.metric("Participants", unique_users)

    st.markdown("---")

    for idx, entry in enumerate(reversed(track_history), 1):
        actual_image_num = len(track_history) - idx + 1
        st.markdown(f"### Image {actual_image_num}")
        image_blob = f"{GCS_IMAGES_PREFIX}{entry['image_filename']}"
        image = load_image_gcs(image_blob)
        if image:
            st.image(image, width=IMG_WIDTH)
        st.caption(f"👤 **{entry['user_name']}** • 🕒 {entry['timestamp'][:19].replace('T', ' ')}")
        with st.expander("📝 View Prompt"):
            st.write(entry["prompt_text"])
        st.markdown("---")

    starting_image = load_image_gcs(STARTING_IMAGE_BLOBS[selected_track_id])
    if starting_image:
        st.markdown("### 🎬 Starting Image")
        st.image(starting_image, width=IMG_WIDTH)
        st.caption("**Starting Point**")
        st.markdown("---")


def _bootstrap_starting_images() -> None:
    """Copy pumpkin.png blob to any missing track starting image blobs in GCS."""
    bucket = get_gcs_bucket()
    source_blob = bucket.blob(f"{GCS_IMAGES_PREFIX}pumpkin.png")
    if not source_blob.exists():
        logger.warning("Bootstrap source not found in GCS: %simages/pumpkin.png", GCS_IMAGES_PREFIX)
        return
    for blob_name in STARTING_IMAGE_BLOBS:
        if not bucket.blob(blob_name).exists():
            try:
                bucket.copy_blob(source_blob, bucket, blob_name)
                logger.info("Bootstrapped starting image in GCS: %s", blob_name)
            except Exception as e:
                logger.warning("Could not copy starting image to GCS %s: %s", blob_name, e)


def main():
    st.set_page_config(page_title="Pic{AI}sso", page_icon="🎨", layout="wide", initial_sidebar_state="collapsed")

    _bootstrap_starting_images()
    initialize_session_state()

    # Check password first
    if not st.session_state.authenticated:
        show_password_dialog()
        st.stop()

    # Show disclaimer popup on every fresh session until accepted
    if not st.session_state.disclaimer_accepted:
        show_disclaimer_dialog()
        st.stop()

    game_state = load_game_state()
    game_state = check_and_release_expired_locks(game_state)
    save_game_state(game_state)

    bucket = get_gcs_bucket()
    missing_tracks = [i for i in range(NUM_TRACKS) if not bucket.blob(STARTING_IMAGE_BLOBS[i]).exists()]
    if len(missing_tracks) == NUM_TRACKS:
        st.error("⚠️ No starting images found in GCS!")
        st.info("Upload starting images to the GCS bucket as:")
        for blob_name in STARTING_IMAGE_BLOBS:
            st.code(blob_name)
        st.stop()

    if st.session_state.current_view == "onboarding":
        render_onboarding_view()
    elif st.session_state.current_view == "track_selection":
        render_track_selection_view(game_state)
    elif st.session_state.current_view == "playing":
        render_playing_view(game_state)
    elif st.session_state.current_view == "success":
        render_success_view(game_state)
    elif st.session_state.current_view == "gallery":
        render_gallery_view(game_state)

    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: gray; font-size: 0.8em;'>"
        f"Vibe Coded by Elliot Kovanda with GitHub Copilot"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()

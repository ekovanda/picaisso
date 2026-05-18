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
import shutil
import uuid
from datetime import datetime, timedelta
from io import BytesIO
from typing import Dict, Optional

import requests
import streamlit as st
from dotenv import find_dotenv, load_dotenv
from openai import OpenAI
from PIL import Image

load_dotenv(find_dotenv(), override=False)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
IMG_WIDTH = 400
NUM_TRACKS = 4
LOCK_TIMEOUT_MINUTES = 10
IMAGES_DIR = "images"
GAME_STATE_PATH = "game_state.json"
OPENAI_MODEL = "gpt-image-2"
OPENAI_IMAGE_QUALITY = "low"
OPENAI_IMAGE_SIZE = "1024x1024"

# Password protection
PASSWORD_HASH = os.environ.get("PICAISSO_PASSWORD_HASH")

# Starting images for each track
STARTING_IMAGE_PATHS = [os.path.join(IMAGES_DIR, f"track_{i}_image_000.png") for i in range(NUM_TRACKS)]


def get_openai_client() -> OpenAI:
    """Return a cached OpenAI client."""
    if "openai_client" not in st.session_state:
        api_key = os.environ.get("OPENAI_KEY")
        if not api_key:
            st.error("OPENAI_KEY not found in environment variables.")
            st.stop()
        st.session_state.openai_client = OpenAI(api_key=api_key)
    return st.session_state.openai_client


# ── Local storage helpers ──────────────────────────────────────────────────────

def load_image_local(path: str) -> Optional[Image.Image]:
    """Load a PIL Image from a local file path."""
    try:
        if os.path.exists(path):
            return Image.open(path).copy()
        logger.warning("Image not found locally: %s", path)
        return None
    except Exception as e:
        logger.error("Failed to load image %s: %s", path, e)
        return None


def save_image_local(image: Image.Image, path: str) -> bool:
    """Save a PIL Image to a local file path, creating directories as needed."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        image.save(path, format="PNG")
        logger.info("Image saved: %s", path)
        return True
    except Exception as e:
        logger.error("Failed to save image %s: %s", path, e)
        return False


def load_game_state() -> Dict:
    """Load game state from the local JSON file."""
    try:
        if os.path.exists(GAME_STATE_PATH):
            with open(GAME_STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
            if "tracks" not in state:
                state = _init_game_state()
            if "locks" not in state:
                state["locks"] = {
                    str(i): {"locked": False, "session_id": None, "timestamp": None}
                    for i in range(NUM_TRACKS)
                }
            return state
    except Exception as e:
        logger.error("Failed to load game state: %s", e)
    return _init_game_state()


def save_game_state(game_state: Dict) -> None:
    """Save game state to the local JSON file."""
    try:
        with open(GAME_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(game_state, f, indent=2)
        logger.info("Game state saved.")
    except Exception as e:
        logger.error("Failed to save game state: %s", e)
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


def get_current_image_path(game_state: Dict, track_id: int) -> str:
    image_num = len(game_state["tracks"][str(track_id)]["history"])
    return os.path.join(IMAGES_DIR, f"track_{track_id}_image_{image_num:03d}.png")


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
    current_path = get_current_image_path(game_state, track_id)
    image = load_image_local(current_path)

    if image:
        st.image(image, width=IMG_WIDTH)
    else:
        starting_image = load_image_local(STARTING_IMAGE_PATHS[track_id])
        if starting_image:
            st.image(starting_image, width=IMG_WIDTH)
        else:
            st.warning(f"No image found for Track {track_id + 1}.")
            st.info(f"Place a starting image at: `{STARTING_IMAGE_PATHS[track_id]}`")


# ── Views ──────────────────────────────────────────────────────────────────────

@st.dialog("� Enter Password")
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


@st.dialog("�👋 Welcome to Pic{AI}sso — Please Read First")
def show_disclaimer_dialog() -> None:
    st.warning(
        "**This app uses Elliot Kovanda's personal OpenAI API Key** (AI Solutions & Data Insights). "
        "Every image you generate has a real cost — please be mindful and avoid unnecessary generations."
    )
    st.error(
        "⚠️ **This is a public application.** Do NOT enter any internal company information, "
        "confidential data, client names, or sensitive content. "
        "Keep all descriptions limited to public, shareable content only."
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
                current_path = get_current_image_path(game_state, track_id)
                image = load_image_local(current_path)
                if image:
                    st.image(image, width=IMG_WIDTH)
                else:
                    starting_image = load_image_local(STARTING_IMAGE_PATHS[track_id])
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
                            next_image_path = os.path.join(IMAGES_DIR, next_image_filename)

                            if save_image_local(generated_image, next_image_path):
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
                                    "image_path": next_image_path,
                                    "prompt": description.strip(),
                                    "track_id": track_id,
                                }
                                st.session_state.generating = False
                                st.session_state.selected_track = None
                                st.session_state.current_view = "success"
                                st.rerun()
                            else:
                                st.error("❌ Failed to save image. Please try again.")
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
    generated_image = load_image_local(data["image_path"])
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
        image_path = os.path.join(IMAGES_DIR, entry["image_filename"])
        image = load_image_local(image_path)
        if image:
            st.image(image, width=IMG_WIDTH)
        st.caption(f"👤 **{entry['user_name']}** • 🕒 {entry['timestamp'][:19].replace('T', ' ')}")
        with st.expander("📝 View Prompt"):
            st.write(entry["prompt_text"])
        st.markdown("---")

    starting_image = load_image_local(STARTING_IMAGE_PATHS[selected_track_id])
    if starting_image:
        st.markdown("### 🎬 Starting Image")
        st.image(starting_image, width=IMG_WIDTH)
        st.caption("**Starting Point**")
        st.markdown("---")


def _bootstrap_starting_images() -> None:
    """Copy pumpkin.png to any missing track starting images."""
    source = os.path.join(IMAGES_DIR, "pumpkin.png")
    if not os.path.exists(source):
        return
    for path in STARTING_IMAGE_PATHS:
        if not os.path.exists(path):
            try:
                shutil.copy2(source, path)
                logger.info("Bootstrapped starting image: %s", path)
            except Exception as e:
                logger.warning("Could not copy starting image to %s: %s", path, e)


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

    missing_tracks = [i for i in range(NUM_TRACKS) if not os.path.exists(STARTING_IMAGE_PATHS[i])]
    if len(missing_tracks) == NUM_TRACKS:
        st.error("⚠️ No starting images found!")
        st.info("Place at least one starting image in the `images/` directory:")
        for path in STARTING_IMAGE_PATHS:
            st.code(path)
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

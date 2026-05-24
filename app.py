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

from translations import TRANSLATIONS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def t(key: str) -> str:
    """Return the UI string for the current language."""
    lang = st.session_state.get("lang", "de")
    return TRANSLATIONS.get(lang, TRANSLATIONS["de"]).get(key, key)


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

@st.cache_data(ttl=300, show_spinner=False)
def load_image_gcs(blob_name: str) -> Optional[Image.Image]:
    """Download a blob from GCS and return it as a PIL Image. Cached for 5 minutes."""
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
        st.error(t("save_state_error"))


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
        "lang": "de",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_next_image_number(game_state: Dict, track_id: int) -> int:
    return len(game_state["tracks"][str(track_id)]["history"])


def get_current_image_blob(game_state: Dict, track_id: int) -> str:
    image_num = len(game_state["tracks"][str(track_id)]["history"])
    return f"{GCS_IMAGES_PREFIX}track_{track_id}_image_{image_num:03d}.png"


def check_and_release_expired_locks(game_state: Dict) -> tuple[Dict, bool]:
    changed = False
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
                changed = True
    return game_state, changed


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
            st.warning(t("no_image_for_track").format(num=track_id + 1))
            st.info(t("upload_starting_image").format(blob=STARTING_IMAGE_BLOBS[track_id]))


# ── Views ──────────────────────────────────────────────────────────────────────

@st.dialog("🔐 Password / Passwort")
def show_password_dialog() -> None:
    """Show password entry dialog."""
    st.markdown(t("password_dialog_text"))
    password = st.text_input(t("password_label"), type="password", key="password_input")
    if st.button(t("submit_btn"), type="primary", use_container_width=True):
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if password_hash == PASSWORD_HASH:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error(t("wrong_password"))


@st.dialog("👋 Please Read First / Bitte zuerst lesen — Pic{AI}sso 🎨")
def show_disclaimer_dialog() -> None:
    st.info(t("disclaimer_api_info"))
    st.error(t("disclaimer_confidentiality"))
    st.markdown(t("disclaimer_confirm_text"))
    if st.button(t("disclaimer_btn"), type="primary", use_container_width=True):
        st.session_state.disclaimer_accepted = True
        st.rerun()


def render_onboarding_view() -> None:
    st.title(t("onboarding_title"))
    st.info(t("onboarding_intro"))
    st.markdown(t("how_to_play_header"))
    st.markdown(t("how_to_play_steps"))
    st.markdown(t("how_to_play_goal"))
    st.markdown("---")
    name_input = st.text_input(
        t("name_input_label"), placeholder=t("name_placeholder"), key="onboarding_name_input"
    )
    if st.button(t("start_btn"), type="primary", disabled=not name_input.strip()):
        st.session_state.user_name = name_input.strip()
        st.session_state.current_view = "track_selection"
        st.rerun()


def render_track_selection_view(game_state: Dict) -> None:
    col_title, col_gallery = st.columns([3, 1])
    with col_title:
        st.title(t("app_title"))
    with col_gallery:
        st.markdown("")
        if st.button(t("gallery_btn"), use_container_width=False):
            st.session_state.current_view = "gallery"
            st.rerun()

    st.markdown(t("track_select_welcome").format(name=st.session_state.user_name))
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
                        st.info(t("track_no_image").format(num=track_id + 1))

            with col_info:
                st.markdown(t("track_header").format(num=track_id + 1))
                if is_locked and not can_access:
                    st.error(t("track_locked"))
                    st.caption(t("track_locked_caption"))
                else:
                    st.success(t("track_available"))

                if is_locked and not can_access:
                    st.button(t("select_track_btn"), key=f"track_select_{track_id}", disabled=True)
                else:
                    if st.button(t("select_track_btn"), key=f"track_select_{track_id}", type="primary"):
                        game_state = lock_track(game_state, track_id, st.session_state.session_id)
                        save_game_state(game_state)
                        st.session_state.selected_track = track_id
                        st.session_state.current_view = "playing"
                        st.rerun()

        st.markdown("---")


def render_prompting_tips() -> None:
    with st.expander(t("tips_expander")):
        st.markdown(t("tips_content"))


def render_playing_view(game_state: Dict) -> None:
    track_id = st.session_state.selected_track

    if not can_user_access_track(game_state, track_id, st.session_state.session_id):
        st.error(t("track_access_lost"))
        st.session_state.selected_track = None
        st.session_state.current_view = "track_selection"
        if st.button(t("back_to_track_selection_btn")):
            st.rerun()
        st.stop()

    col_back, col_title = st.columns([1, 5])
    with col_back:
        if st.button(t("back_btn")):
            game_state = release_track(game_state, track_id)
            save_game_state(game_state)
            st.session_state.selected_track = None
            st.session_state.current_view = "track_selection"
            st.rerun()
    with col_title:
        st.title(t("track_title").format(num=track_id + 1))

    st.info(t("how_to_play_info"))
    st.markdown("---")

    col_left, col_right = st.columns([1, 2])

    with col_left:
        render_prompting_tips()
        st.markdown(t("your_description_header"))
        description = st.text_area(
            t("description_label"),
            placeholder=t("description_placeholder"),
            height=200,
            key="description_input",
            help=t("description_help"),
        )

        if st.button(t("generate_btn"), type="primary", disabled=st.session_state.generating):
            if not description.strip():
                st.error(t("no_description_error"))
            else:
                st.session_state.generating = True
                with st.spinner(t("generating_spinner")):
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
                                st.error(t("save_failed_error"))
                                st.session_state.generating = False
                        else:
                            st.error(t("generation_failed_error"))
                            st.session_state.generating = False
                    except Exception as e:
                        logger.error("Error during image generation: %s", e)
                        st.error(t("error_occurred").format(error=str(e)))
                        st.session_state.generating = False

    with col_right:
        st.markdown(t("target_image_header"))
        display_current_image(game_state, track_id)

    st.markdown("---")


def render_success_view(game_state: Dict) -> None:
    if not st.session_state.generated_image_data:
        st.session_state.current_view = "track_selection"
        st.rerun()
        return

    data = st.session_state.generated_image_data
    st.balloons()
    st.title(t("success_title"))
    st.success(t("success_message").format(name=st.session_state.user_name))
    st.markdown("---")
    st.markdown(t("your_generated_image_header"))
    generated_image = load_image_gcs(data["image_blob"])
    if generated_image:
        st.image(generated_image, width=IMG_WIDTH)
    with st.expander(t("your_prompt_expander")):
        st.write(data["prompt"])
    st.markdown("---")
    st.markdown(t("whats_next_header"))
    st.markdown(t("whats_next_text"))
    if st.button(t("view_gallery_btn"), type="primary"):
        st.session_state.current_view = "gallery"
        st.session_state.gallery_selected_track = data["track_id"]
        st.session_state.generated_image_data = None
        st.rerun()


def render_gallery_view(game_state: Dict) -> None:
    col_back, col_title = st.columns([1, 5])
    with col_back:
        if st.button(t("back_to_play_btn")):
            st.session_state.current_view = "track_selection"
            st.rerun()
    with col_title:
        st.title(t("gallery_title"))

    st.markdown("---")
    if "gallery_selected_track" not in st.session_state:
        st.session_state.gallery_selected_track = 0

    track_options = [t("track_option").format(num=i + 1) for i in range(NUM_TRACKS)]
    selected_track_name = st.selectbox(
        t("select_track_label"),
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
        st.metric(t("total_images_metric"), total_images)
    with col2:
        st.metric(t("participants_metric"), unique_users)

    st.markdown("---")

    for idx, entry in enumerate(reversed(track_history), 1):
        actual_image_num = len(track_history) - idx + 1
        st.markdown(t("image_header").format(num=actual_image_num))
        image_blob = f"{GCS_IMAGES_PREFIX}{entry['image_filename']}"
        image = load_image_gcs(image_blob)
        if image:
            st.image(image, width=IMG_WIDTH)
        st.caption(t("image_caption").format(
            name=entry["user_name"],
            timestamp=entry["timestamp"][:19].replace("T", " "),
        ))
        with st.expander(t("view_prompt_expander")):
            st.write(entry["prompt_text"])
        st.markdown("---")

    starting_image = load_image_gcs(STARTING_IMAGE_BLOBS[selected_track_id])
    if starting_image:
        st.markdown(t("starting_image_header"))
        st.image(starting_image, width=IMG_WIDTH)
        st.caption(t("starting_point_caption"))
        st.markdown("---")


@st.cache_resource
def _bootstrap_starting_images() -> None:
    """Copy pumpkin.png blob to any missing track starting image blobs in GCS. Runs once per server process."""
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


@st.cache_data(ttl=3600, show_spinner=False)
def _any_starting_images_missing() -> bool:
    """Returns True only if ALL starting images are absent (first-run guard). Cached for 1 hour."""
    bucket = get_gcs_bucket()
    return all(not bucket.blob(b).exists() for b in STARTING_IMAGE_BLOBS)


def main():
    st.set_page_config(page_title="Pic{AI}sso", page_icon="🎨", layout="wide", initial_sidebar_state="auto")

    _bootstrap_starting_images()
    initialize_session_state()

    with st.sidebar:
        selected_lang = st.radio(
            t("language_label"),
            ["🇩🇪 Deutsch", "🇬🇧 English"],
            index=0 if st.session_state.lang == "de" else 1,
            key="lang_radio",
        )
        st.session_state.lang = "de" if selected_lang == "🇩🇪 Deutsch" else "en"

    # Check password first
    if not st.session_state.authenticated:
        show_password_dialog()
        st.stop()

    # Show disclaimer popup on every fresh session until accepted
    if not st.session_state.disclaimer_accepted:
        show_disclaimer_dialog()
        st.stop()

    game_state = load_game_state()
    game_state, locks_expired = check_and_release_expired_locks(game_state)
    if locks_expired:
        save_game_state(game_state)

    if _any_starting_images_missing():
        st.error(t("no_starting_images_error"))
        st.info(t("upload_starting_images_info"))
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

"""
Translation strings for Pic{AI}sso.
To add a new UI string: add it under both "en" and "de" with the same key.
"""

TRANSLATIONS: dict = {
    "en": {
        # ── Password dialog ────────────────────────────────────────────────────
        "password_dialog_title": "🔐 Password / Passwort",
        "password_dialog_text": "Please enter the password to play:",
        "password_label": "Password:",
        "submit_btn": "Submit",
        "wrong_password": "❌ Incorrect password. Please try again.",
        # ── Disclaimer dialog ──────────────────────────────────────────────────
        "disclaimer_dialog_title": "👋 Please Read First / Bitte zuerst lesen — Pic{AI}sso 🎨",
        "disclaimer_api_info": (
            "**This app uses my personal OpenAI API Key**.\n\n"
            "Every image you generate has a small but real cost — please be mindful "
            "and avoid unnecessary generations.\n\nThank you & have fun 💛\n\nElliot Kovanda"
        ),
        "disclaimer_confidentiality": (
            "⚠️ **This is a public application.** Do NOT enter any internal company "
            "information, confidential data, client names, or sensitive content. "
            "Keep all descriptions limited to public, shareable content only. "
            "Note, that other players will see the images you generate and the prompts "
            "you enter. Thus, enter only work-appropriate, non-confidential descriptions."
        ),
        "disclaimer_confirm_text": "By clicking below you confirm you have read and understood the above.",
        "disclaimer_btn": "✅ I understand, let me play!",
        # ── Onboarding ─────────────────────────────────────────────────────────
        "onboarding_title": "Welcome to Pic {AI} sso 🎨!",
        "onboarding_intro": (
            'Pic{AI}sso 🎨 is a game where you\'ll try to closely recreate an existing image by prompting an AI.\n'
            'As more people join in we can watch the chain evolve like the "Telephone Game" ("Stille Post").'
        ),
        "how_to_play_header": "### How to Play",
        "how_to_play_steps": (
            "1. **Choose a track** - Pick any available image track\n"
            "2. **Describe what you see** - Write a detailed description of the image\n"
            "3. **AI generates** - The AI creates a new image based on your description\n"
            "4. **See the evolution** - Watch how the image evolves across many iterations"
        ),
        "how_to_play_goal": (
            "The goal is to practice **clear, precise prompting**. The more descriptive you are, "
            "the better the AI can recreate the image!"
        ),
        "name_input_label": "Enter your first name to begin:",
        "name_placeholder": "Your name...",
        "start_btn": "🚀 Start Playing",
        # ── Track selection ────────────────────────────────────────────────────
        "app_title": "🎨 Pic{AI}sso",
        "gallery_btn": "📸 Gallery",
        "track_select_welcome": "**Welcome, {name}!** Choose an available track to start:",
        "track_header": "### Track {num}",
        "track_locked": "🔒 **Locked**",
        "track_locked_caption": "Someone is currently working on this track",
        "track_available": "✅ **Available**",
        "select_track_btn": "Select Track",
        "track_no_image": "Track {num}: No image available",
        # ── Playing view ───────────────────────────────────────────────────────
        "back_btn": "← Back",
        "track_title": "Track {num}",
        "how_to_play_info": (
            "📝 **How to play:** Look at the image on the right and describe what you see in detail. "
            "The AI will create a new image based on your description. "
            "Try to get as close to the original as you can ☺️"
        ),
        "tips_expander": "🎨 Quick Tips for Better Image Prompts",
        "tips_content": """\
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
""",
        "your_description_header": "### Your Description",
        "description_label": "Describe what you see in the image:",
        "description_placeholder": "E.g. A pencil drawing of...",
        "description_help": "Be as detailed as possible! Include colors, objects, positions, and atmosphere.",
        "generate_btn": "🎨 Generate Image",
        "no_description_error": "Please enter a description before generating!",
        "generating_spinner": "✨ Generating your image... This may take a moment...",
        "save_failed_error": "❌ Failed to save image to GCS. Please try again.",
        "generation_failed_error": "❌ Failed to generate image. Please try again.",
        "error_occurred": "❌ An error occurred: {error}",
        "target_image_header": "### Target Image",
        "track_access_lost": (
            "⚠️ You no longer have access to this track. "
            "It may have been claimed by someone else."
        ),
        "back_to_track_selection_btn": "Back to Track Selection",
        # ── Success view ───────────────────────────────────────────────────────
        "success_title": "🎉 Success!",
        "success_message": "**{name}**, your image has been generated!",
        "your_generated_image_header": "### Your Generated Image",
        "your_prompt_expander": "📝 Your Prompt",
        "whats_next_header": "### What's Next?",
        "whats_next_text": "View the gallery to see how your image fits into the track's evolution!",
        "view_gallery_btn": "📸 View Track Gallery",
        # ── Gallery view ───────────────────────────────────────────────────────
        "back_to_play_btn": "← Back to Play",
        "gallery_title": "📸 Gallery",
        "select_track_label": "Select Track to View:",
        "track_option": "Track {num}",
        "total_images_metric": "Total Images",
        "participants_metric": "Participants",
        "image_header": "### Image {num}",
        "image_caption": "👤 **{name}** • 🕒 {timestamp}",
        "view_prompt_expander": "📝 View Prompt",
        "starting_image_header": "### 🎬 Starting Image",
        "starting_point_caption": "**Starting Point**",
        # ── Errors / warnings ──────────────────────────────────────────────────
        "no_starting_images_error": "⚠️ No starting images found in GCS!",
        "upload_starting_images_info": "Upload starting images to the GCS bucket as:",
        "no_image_for_track": "No image found for Track {num}.",
        "upload_starting_image": "Upload a starting image to GCS as: `{blob}`",
        "save_state_error": "Failed to save game state. Please try again.",
        # ── Sidebar ────────────────────────────────────────────────────────────
        "language_label": "🌐 Language / Sprache",
    },
    "de": {
        # ── Password dialog ────────────────────────────────────────────────────
        "password_dialog_title": "🔐 Password / Passwort",
        "password_dialog_text": "Bitte gib das Passwort ein, um zu spielen:",
        "password_label": "Passwort:",
        "submit_btn": "Bestätigen",
        "wrong_password": "❌ Falsches Passwort. Bitte versuche es erneut.",
        # ── Disclaimer dialog ──────────────────────────────────────────────────
        "disclaimer_dialog_title": "👋 Please Read First / Bitte zuerst lesen — Pic{AI}sso 🎨",
        "disclaimer_api_info": (
            "**Diese App verwendet meinen persönlichen OpenAI API-Schlüssel**.\n\n"
            "Jedes Bild, das du generierst, verursacht geringe, aber reale Kosten – "
            "bitte sei achtsam und vermeide unnötige Generierungen.\n\n"
            "Danke & viel Spaß 💛\n\nElliot Kovanda"
        ),
        "disclaimer_confidentiality": (
            "⚠️ **Dies ist eine öffentliche Anwendung.** Gib KEINE internen "
            "Unternehmensinformationen, vertraulichen Daten, Kundennamen oder sensible Inhalte ein. "
            "Beschränke alle Beschreibungen auf öffentlich teilbare Inhalte. "
            "Beachte, dass andere Spieler die von dir generierten Bilder und eingegebenen Prompts "
            "sehen können. Gib daher nur arbeitsgerechte, nicht vertrauliche Beschreibungen ein."
        ),
        "disclaimer_confirm_text": "Durch Klicken unten bestätigst du, dass du das Obige gelesen und verstanden hast.",
        "disclaimer_btn": "✅ Verstanden, ich möchte spielen!",
        # ── Onboarding ─────────────────────────────────────────────────────────
        "onboarding_title": "Willkommen bei Pic {AI} sso 🎨!",
        "onboarding_intro": (
            'Pic{AI}sso 🎨 ist ein Spiel, bei dem du ein bestehendes Bild so genau wie möglich '
            'durch einen KI-Prompt nachbilden sollst.\n'
            'Je mehr Mitspieler mitmachen, desto mehr können wir beobachten, wie die Kette sich '
            'entwickelt – wie beim "Stille Post"-Spiel.'
        ),
        "how_to_play_header": "### So wird gespielt",
        "how_to_play_steps": (
            "1. **Wähle einen Track** – Wähle einen verfügbaren Bild-Track aus\n"
            "2. **Beschreibe, was du siehst** – Schreibe eine detaillierte Beschreibung des Bildes\n"
            "3. **KI generiert** – Die KI erstellt ein neues Bild anhand deiner Beschreibung\n"
            "4. **Beobachte die Entwicklung** – Schau zu, wie sich das Bild über viele Iterationen verändert"
        ),
        "how_to_play_goal": (
            "Das Ziel ist es, **klares, präzises Prompten** zu üben. "
            "Je detaillierter du bist, desto besser kann die KI das Bild nachbilden!"
        ),
        "name_input_label": "Gib deinen Vornamen ein, um zu beginnen:",
        "name_placeholder": "Dein Name...",
        "start_btn": "🚀 Spielen starten",
        # ── Track selection ────────────────────────────────────────────────────
        "app_title": "🎨 Pic{AI}sso",
        "gallery_btn": "📸 Galerie",
        "track_select_welcome": "**Willkommen, {name}!** Wähle einen verfügbaren Track aus:",
        "track_header": "### Track {num}",
        "track_locked": "🔒 **Gesperrt**",
        "track_locked_caption": "Jemand arbeitet gerade an diesem Track",
        "track_available": "✅ **Verfügbar**",
        "select_track_btn": "Track auswählen",
        "track_no_image": "Track {num}: Kein Bild verfügbar",
        # ── Playing view ───────────────────────────────────────────────────────
        "back_btn": "← Zurück",
        "track_title": "Track {num}",
        "how_to_play_info": (
            "📝 **So wird gespielt:** Schau dir das Bild rechts an und beschreibe detailliert, was du siehst. "
            "Die KI erstellt ein neues Bild anhand deiner Beschreibung. "
            "Versuche, so nah wie möglich ans Original zu kommen ☺️"
        ),
        "tips_expander": "🎨 Schnelle Tipps für bessere Bild-Prompts",
        "tips_content": """\
##### 🖌️ Stil
Sage den **Bildtyp**, den du möchtest: *Foto, Illustration, 3D-Render, Aquarell* 🎭

##### 🧩 Komposition
Nenne die **Hauptobjekte** und wie sie angeordnet sind: *Nahaufnahme, Weitwinkel, zentriert, im Hintergrund* 📐

##### 🌈 Farben & Licht
Füge Farbstimmungen und Beleuchtung hinzu: *Pastell, Neon, Warme Töne, Goldene Stunde, Dramatische Schatten* 💡

##### 🌤️ Stimmung
Beschreibe das Gefühl: *gemütlich, geheimnisvoll, verspielt, verträumt* ✨

---

**👎 Schlecht:** *Ein Roboter auf einem Blatt*

**👍 Besser:** *Eine Buntstiftzeichnung eines winzigen Roboters auf einem riesigen Blatt, sanftes Morgenlicht*
""",
        "your_description_header": "### Deine Beschreibung",
        "description_label": "Beschreibe, was du im Bild siehst:",
        "description_placeholder": "Z.B. Eine Bleistiftzeichnung von...",
        "description_help": "Sei so detailliert wie möglich! Nenne Farben, Objekte, Positionen und Atmosphäre.",
        "generate_btn": "🎨 Bild generieren",
        "no_description_error": "Bitte gib eine Beschreibung ein, bevor du generierst!",
        "generating_spinner": "✨ Dein Bild wird generiert... Das kann einen Moment dauern...",
        "save_failed_error": "❌ Bild konnte nicht in GCS gespeichert werden. Bitte versuche es erneut.",
        "generation_failed_error": "❌ Bild konnte nicht generiert werden. Bitte versuche es erneut.",
        "error_occurred": "❌ Ein Fehler ist aufgetreten: {error}",
        "target_image_header": "### Ziel-Bild",
        "track_access_lost": (
            "⚠️ Du hast keinen Zugriff mehr auf diesen Track. "
            "Er wurde möglicherweise von jemand anderem übernommen."
        ),
        "back_to_track_selection_btn": "Zurück zur Track-Auswahl",
        # ── Success view ───────────────────────────────────────────────────────
        "success_title": "🎉 Erfolg!",
        "success_message": "**{name}**, dein Bild wurde generiert!",
        "your_generated_image_header": "### Dein generiertes Bild",
        "your_prompt_expander": "📝 Dein Prompt",
        "whats_next_header": "### Wie geht's weiter?",
        "whats_next_text": "Sieh dir die Galerie an, um zu sehen, wie dein Bild zur Entwicklung des Tracks beiträgt!",
        "view_gallery_btn": "📸 Track-Galerie anzeigen",
        # ── Gallery view ───────────────────────────────────────────────────────
        "back_to_play_btn": "← Zurück zum Spiel",
        "gallery_title": "📸 Galerie",
        "select_track_label": "Track auswählen:",
        "track_option": "Track {num}",
        "total_images_metric": "Bilder gesamt",
        "participants_metric": "Teilnehmer",
        "image_header": "### Bild {num}",
        "image_caption": "👤 **{name}** • 🕒 {timestamp}",
        "view_prompt_expander": "📝 Prompt anzeigen",
        "starting_image_header": "### 🎬 Startbild",
        "starting_point_caption": "**Ausgangspunkt**",
        # ── Errors / warnings ──────────────────────────────────────────────────
        "no_starting_images_error": "⚠️ Keine Startbilder in GCS gefunden!",
        "upload_starting_images_info": "Lade Startbilder in den GCS-Bucket hoch als:",
        "no_image_for_track": "Kein Bild für Track {num} gefunden.",
        "upload_starting_image": "Lade ein Startbild in GCS hoch als: `{blob}`",
        "save_state_error": "Spielstand konnte nicht gespeichert werden. Bitte versuche es erneut.",
        # ── Sidebar ────────────────────────────────────────────────────────────
        "language_label": "🌐 Language / Sprache",
    },
}

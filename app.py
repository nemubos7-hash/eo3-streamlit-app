
import os
import time
import streamlit as st

# --- Google GenAI SDK (Gemini API + Veo 3) ---
from google import genai
from google.genai import types

# Page config
st.set_page_config(page_title="Veo 3 Video Generator", layout="centered", page_icon="🎬")

st.title("🎬 Veo 3 Video Generator (Gemini API)")
st.caption("Text-to-Video 8 detik (Veo 3). Siap untuk Streamlit Cloud.")

with st.expander("ℹ️ Info singkat"):
    st.markdown(
        """
- **Veo 3** menghasilkan video **8 detik** dengan audio native.
- Biaya mengikuti tarif model pada Gemini API. Pastikan punya billing aktif.
- **Aspect ratio**: 16:9 dan 9:16. (Catatan: 1080p terutama untuk 16:9).
- Model ID: `veo-3.0-generate-001` (kualitas) dan `veo-3.0-fast-generate-001` (lebih cepat/hemat).
        """
    )

# --- API Key lookup precedence: st.secrets -> env var -> input box ---
API_KEY = None
try:
    # Streamlit Cloud secrets
    API_KEY = st.secrets.get("GEMINI_API_KEY", None) or st.secrets.get("GOOGLE_API_KEY", None)
except Exception:
    API_KEY = None

API_KEY = API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
api_key_input = st.text_input(
    "API Key (opsional jika tidak pakai Secrets/Environment)", 
    type="password", 
    help="Set di Streamlit Cloud Secrets (GEMINI_API_KEY) atau ENV. Kamu juga bisa isi langsung di sini untuk uji coba lokal."
)

if api_key_input:
    API_KEY = api_key_input

if not API_KEY:
    st.warning("Masukkan API Key di atas atau set `GEMINI_API_KEY` via Secrets/ENV.")
    st.stop()

# Init client
try:
    client = genai.Client(api_key=API_KEY)
except Exception as e:
    st.error(f"Gagal inisialisasi client: {e}")
    st.stop()

# --- Sidebar ---
st.sidebar.header("Settings")
model = st.sidebar.selectbox("Model", ["veo-3.0-generate-001", "veo-3.0-fast-generate-001"], index=0)
aspect = st.sidebar.selectbox("Aspect Ratio", ["16:9", "9:16"], index=0)
resolution = st.sidebar.selectbox("Resolution", ["720p", "1080p"], index=0, help="1080p saat ini utamanya untuk 16:9.")
seed = st.sidebar.number_input("Seed (opsional)", min_value=0, step=1, value=0)
negative_prompt = st.sidebar.text_input("Negative prompt (opsional)", value="")

st.sidebar.subheader("Preset Prompt (opsional)")
preset = st.sidebar.selectbox(
    "Pilih preset",
    [
        "— (manual) —",
        "Cinematic: kitten + giant mushrooms (rain)",
        "Product shot: soda can splash",
        "Anime action: city rooftop night",
    ],
    index=0
)

# --- Main prompt ---
default_text = ""
if preset == "Cinematic: kitten + giant mushrooms (rain)":
    default_text = 'Low-angle orbit of an orange kitten dashing through giant rainbow mushrooms; wet ground reflections; light rain ambience; SFX droplets; dialogue: "I can do this!"'
elif preset == "Product shot: soda can splash":
    default_text = "Ultra slow-motion product shot of a cold soda can; droplets and splash; studio lighting; macro lens; white sweep background; tasteful logo reveal."
elif preset == "Anime action: city rooftop night":
    default_text = "Dynamic anime-style action on a neon-lit city rooftop at night; hero leaps with wind-up; speed lines; dramatic lighting; subtle camera shake."

prompt = st.text_area(
    "Prompt video (jelaskan motion, gaya visual, lighting, audio/dialog):",
    value=default_text,
    height=150,
)

col1, col2 = st.columns(2)
with col1:
    btn = st.button("🚀 Generate 8s Video", type="primary")
with col2:
    clr = st.button("🗑️ Reset")

if clr:
    st.experimental_rerun()

if btn:
    if not prompt.strip():
        st.error("Isi prompt terlebih dahulu.")
        st.stop()

    st.info("Mengirim job ke Veo 3...")
    try:
        config = types.GenerateVideosConfig(
            aspect_ratio=aspect,
            resolution=resolution,
            negative_prompt=negative_prompt or None,
            seed=seed if seed else None,
        )

        operation = client.models.generate_videos(
            model=model,
            prompt=prompt,
            config=config
        )
    except Exception as e:
        st.error(f"Gagal memulai generate: {e}")
        st.stop()

    progress = st.progress(0)
    status = st.empty()
    i = 0

    try:
        while not operation.done:
            i += 1
            status.write(f"Status: processing (poll {i})")
            time.sleep(6)
            operation = client.operations.get(operation)
            progress.progress(min(100, i * 7))

        progress.progress(100)
        status.success("Selesai. Mengunduh video...")

        if not operation.response.generated_videos:
            st.error("Tidak ada video di response.")
            st.stop()

        video_obj = operation.response.generated_videos[0]

        # Unduh file
        client.files.download(file=video_obj.video)  # fetch remote bytes
        out_name = "veo_output.mp4"
        video_obj.video.save(out_name)

        st.video(out_name)
        with open(out_name, "rb") as f:
            st.download_button("⬇️ Download MP4", data=f, file_name=out_name, mime="video/mp4")

        with st.expander("Detail hasil"):
            st.json({
                "model": model,
                "aspect_ratio": aspect,
                "resolution": resolution,
                "seed": seed if seed else None,
                "duration_sec": 8,
                "has_audio": True
            })

    except Exception as e:
        st.error(f"Error saat polling/unduh: {e}")

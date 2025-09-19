import os
import time
import streamlit as st

from google import genai
from google.genai import types

st.set_page_config(page_title="Veo Generator (Video & Image)", layout="wide")
st.title("🎬 Veo Generator — Video & Image")
st.caption("Text→Video, Image→Video, dan Generate Image (alias “Nano Banana”). 1 baris prompt = 1 output.")

# ========== API KEY ==========
API_KEY = None
try:
    API_KEY = st.secrets.get("GEMINI_API_KEY", None) or st.secrets.get("GOOGLE_API_KEY", None)
except Exception:
    API_KEY = None
API_KEY = API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

with st.sidebar:
    st.header("Settings")
    api_key_input = st.text_input("API Key (opsional—kalau tak ada di Secrets/ENV)", type="password")
    if api_key_input:
        API_KEY = api_key_input

if not API_KEY:
    st.warning("Masukkan API key di sidebar, atau set di Secrets/ENV.")
    st.stop()

# Init client
try:
    client = genai.Client(api_key=API_KEY)
except Exception as e:
    st.error(f"Gagal inisialisasi client: {e}")
    st.stop()

# ========== MODEL MAPS ==========
VIDEO_MODEL_LABELS = {
    "Veo 3 (Preview)": "veo-3.0-preview-001",
    "Veo 3 (Fast)": "veo-3.0-fast-generate-001",
    "Veo 3 (Quality)": "veo-3.0-generate-001",
    "Veo 2": "veo-2.0-generate-001",
}

IMAGE_MODEL_LABELS = {
    "Imagen 3 (Quality) — Nano Banana": "imagen-3.0-generate-001",
    "Imagen 3 (Fast) — Nano Banana": "imagen-3.0-fast-generate-001",
}

# ========== UTIL ==========
def collect_prompts(raw: str, limit: int):
    lines = [ln.strip() for ln in (raw or "").split("\n")]
    lines = [ln for ln in lines if ln]
    return lines[: max(1, limit)]

def pil_image_from_uploaded(uploaded):
    if uploaded is None:
        return None, None
    raw = uploaded.read()
    mime = uploaded.type or "image/png"
    return raw, mime

# ========== TABS ==========
tab1, tab2, tab3 = st.tabs(["Text → Video", "Image → Video", "Generate Image (Nano Banana)"])

# ===================== TAB 1 — TEXT → VIDEO =====================
with tab1:
    st.subheader("Text → Video (Batch)")

    col_left, col_right = st.columns([1, 1])
    with col_left:
        video_model_label = st.selectbox("Model Video", list(VIDEO_MODEL_LABELS.keys()), index=1)
        aspect = st.selectbox("Aspect Ratio", ["16:9", "9:16"], index=1)
        resolution = st.selectbox("Resolution", ["720p", "1080p"], index=0, help="1080p stabil untuk 16:9. 9:16 → 720p.")
        seed = st.number_input("Seed (opsional)", min_value=0, step=1, value=0)
    with col_right:
        negative_prompt = st.text_input("Negative prompt (opsional)", value="")
        max_batch = st.number_input("Batas batch", min_value=1, max_value=20, value=10)
        st.caption("Tip: Untuk 9:16, gunakan 720p agar tidak fallback ke 16:9.")

    if aspect == "9:16" and resolution == "1080p":
        st.info("Untuk 9:16, 1080p belum stabil → otomatis 720p.")
        resolution = "720p"

    prompts_text = st.text_area(
        "📝 Prompt (satu baris = satu video)",
        height=180,
        placeholder="Contoh:\nKucing oranye berlari di bawah jamur raksasa; hujan\nProduk minuman kaleng; splash slow motion",
    )
    prompts = collect_prompts(prompts_text, int(max_batch))

    run = st.button(f"🚀 Generate {len(prompts) if prompts else 0} Video", type="primary")

    if run:
        if not prompts:
            st.error("Isi minimal 1 baris prompt.")
            st.stop()

        model = VIDEO_MODEL_LABELS[video_model_label]
        overall = st.progress(0)
        status_global = st.empty()

        for idx, p in enumerate(prompts, start=1):
            section = st.container()
            with section:
                st.markdown(f"#### #{idx} Prompt")
                st.write(p)
                pbar = st.progress(0, text=f"Prompt #{idx}: menyiapkan…")

            # Kirim job
            try:
                cfg = types.GenerateVideosConfig(
                    aspect_ratio=aspect,
                    resolution=resolution,
                    negative_prompt=negative_prompt or None,
                    seed=seed or None,
                )
                op = client.models.generate_videos(model=model, prompt=p, config=cfg)
            except Exception as e:
                with section:
                    st.error(f"Gagal mulai generate: {e}")
                overall.progress(int(idx / len(prompts) * 100))
                continue

            # Polling sampai selesai
            ticks = 0
            try:
                while not op.done:
                    time.sleep(6)
                    ticks += 1
                    op = client.operations.get(op)
                    pbar.progress(min(100, ticks * 7), text=f"Prompt #{idx}: processing…")

                pbar.progress(100, text=f"Prompt #{idx}: mengunduh…")

                vids = getattr(op.response, "generated_videos", [])
                if not vids:
                    with section:
                        st.error("Response tidak berisi video.")
                else:
                    v = vids[0]
                    client.files.download(file=v.video)
                    out_name = f"text2video_{idx:02d}.mp4"
                    v.video.save(out_name)

                    with section:
                        st.video(out_name)
                        with open(out_name, "rb") as f:
                            st.download_button("⬇️ Download MP4", data=f, file_name=out_name, mime="video/mp4")
            except Exception as e:
                with section:
                    st.error(f"Error saat proses/unduh: {e}")

            overall.progress(int(idx / len(prompts) * 100))
            status_global.info(f"Selesai #{idx}/{len(prompts)}")

# ===================== TAB 2 — IMAGE → VIDEO =====================
with tab2:
    st.subheader("Image → Video")

    col_left, col_right = st.columns([1, 1])
    with col_left:
        video_model_label_i2v = st.selectbox("Model Video", list(VIDEO_MODEL_LABELS.keys()), index=1, key="i2v_model")
        aspect_i2v = st.selectbox("Aspect Ratio", ["16:9", "9:16"], index=1, key="i2v_ar")
        resolution_i2v = st.selectbox("Resolution", ["720p", "1080p"], index=0, key="i2v_res")
        seed_i2v = st.number_input("Seed (opsional)", min_value=0, step=1, value=0, key="i2v_seed")
    with col_right:
        negative_prompt_i2v = st.text_input("Negative prompt (opsional)", value="", key="i2v_neg")
        max_batch_i2v = st.number_input("Batas batch", min_value=1, max_value=20, value=5, key="i2v_batch")

    if aspect_i2v == "9:16" and resolution_i2v == "1080p":
        st.info("Untuk 9:16, 1080p belum stabil → otomatis 720p.")
        resolution_i2v = "720p"

    uploaded_image = st.file_uploader("Upload gambar (PNG/JPG)", type=["png", "jpg", "jpeg"])
    prompts_text_i2v = st.text_area(
        "📝 Prompt (1 baris = 1 video, gambar sama untuk semua baris)",
        height=160,
        placeholder="Contoh:\nOrbit pelan, cinematic rain\nDolly-in, dramatic lighting",
        key="i2v_text",
    )
    prompts_i2v = collect_prompts(prompts_text_i2v, int(max_batch_i2v))

    run_i2v = st.button(f"🚀 Generate {len(prompts_i2v) if prompts_i2v else 0} Video dari Gambar", type="primary")

    if run_i2v:
        if uploaded_image is None:
            st.error("Upload satu gambar dulu.")
            st.stop()
        if not prompts_i2v:
            st.error("Isi minimal 1 baris prompt.")
            st.stop()

        image_bytes, mime = pil_image_from_uploaded(uploaded_image)
        if not image_bytes:
            st.error("Gagal membaca file gambar.")
            st.stop()

        image_input = types.Image(image_bytes=image_bytes, mime_type=mime)
        model_i2v = VIDEO_MODEL_LABELS[video_model_label_i2v]
        overall_i2v = st.progress(0)
        status_i2v = st.empty()

        for idx, p in enumerate(prompts_i2v, start=1):
            section = st.container()
            with section:
                st.markdown(f"#### (I2V) #{idx} Prompt")
                st.write(p)
                pbar = st.progress(0, text=f"Prompt #{idx}: menyiapkan…")

            try:
                cfg = types.GenerateVideosConfig(
                    aspect_ratio=aspect_i2v,
                    resolution=resolution_i2v,
                    negative_prompt=negative_prompt_i2v or None,
                    seed=seed_i2v or None,
                )
                op = client.models.generate_videos(
                    model=model_i2v,
                    prompt=p,
                    image=image_input,
                    config=cfg
                )
            except Exception as e:
                with section:
                    st.error(f"Gagal mulai generate: {e}")
                overall_i2v.progress(int(idx / len(prompts_i2v) * 100))
                continue

            ticks = 0
            try:
                while not op.done:
                    time.sleep(6)
                    ticks += 1
                    op = client.operations.get(op)
                    pbar.progress(min(100, ticks * 7), text=f"Prompt #{idx}: processing…")

                pbar.progress(100, text=f"Prompt #{idx}: mengunduh…")

                vids = getattr(op.response, "generated_videos", [])
                if not vids:
                    with section:
                        st.error("Response tidak berisi video.")
                else:
                    v = vids[0]
                    client.files.download(file=v.video)
                    out_name = f"image2video_{idx:02d}.mp4"
                    v.video.save(out_name)

                    with section:
                        st.video(out_name)
                        with open(out_name, "rb") as f:
                            st.download_button("⬇️ Download MP4", data=f, file_name=out_name, mime="video/mp4")
            except Exception as e:
                with section:
                    st.error(f"Error saat proses/unduh: {e}")

            overall_i2v.progress(int(idx / len(prompts_i2v) * 100))
            status_i2v.info(f"Selesai #{idx}/{len(prompts_i2v)}")

# ===================== TAB 3 — GENERATE IMAGE =====================
with tab3:
    st.subheader("Generate Image (Imagen 3 — alias “Nano Banana”)")

    image_model_label = st.selectbox("Model Gambar", list(IMAGE_MODEL_LABELS.keys()), index=1)
    img_seed = st.number_input("Seed (opsional)", min_value=0, step=1, value=0, key="img_seed")
    max_batch_img = st.number_input("Batas batch", min_value=1, max_value=20, value=10, key="img_batch")
    st.caption("Satu baris prompt = satu gambar.")

    prompts_text_img = st.text_area(
        "📝 Prompt Gambar (1 baris = 1 gambar)",
        height=180,
        placeholder="Contoh:\nOrange kitten dancing in neon jungle\nSoda can product shot, studio white",
        key="img_text",
    )
    prompts_img = collect_prompts(prompts_text_img, int(max_batch_img))

    run_img = st.button(f"🖼️ Generate {len(prompts_img) if prompts_img else 0} Gambar", type="primary")

    if run_img:
        if not prompts_img:
            st.error("Isi minimal 1 baris prompt.")
            st.stop()

        img_model = IMAGE_MODEL_LABELS[image_model_label]
        overall_img = st.progress(0)
        status_img = st.empty()

        for idx, p in enumerate(prompts_img, start=1):
            section = st.container()
            with section:
                st.markdown(f"#### (IMG) #{idx} Prompt")
                st.write(p)

            try:
                out = client.models.generate_images(
                    model=img_model,
                    prompt=p,
                    seed=img_seed or None,
                )
                if not getattr(out, "generated_images", None):
                    with section:
                        st.error("Response tidak berisi gambar.")
                else:
                    g = out.generated_images[0]
                    client.files.download(file=g.image)
                    img_bytes = g.image.bytes
                    out_name = f"image_{idx:02d}.png"
                    with open(out_name, "wb") as f:
                        f.write(img_bytes)

                    with section:
                        st.image(out_name, use_column_width=True)
                        with open(out_name, "rb") as f:
                            st.download_button("⬇️ Download PNG", data=f, file_name=out_name, mime="image/png")
            except Exception as e:
                with section:
                    st.error(f"Gagal generate image: {e}")

            overall_img.progress(int(idx / len(prompts_img) * 100))
            status_img.info(f"Selesai #{idx}/{len(prompts_img)}")

import os
import time
import streamlit as st

from google import genai
from google.genai import types

st.set_page_config(page_title="Veo Generator (Video & Image)", layout="wide")
st.title("🎬 Veo Generator — Video & Image")
st.caption("Text→Video, Image→Video (multi), dan Generate Image (Imagen 4 / Gemini 2.5 Flash Image). 1 baris prompt = 1 output.")

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

# ========== MODEL MAPS (pakai ID resmi) ==========
VIDEO_MODEL_LABELS = {
    "Veo 3 (Preview)": "veo-3.0-generate-preview",
    "Veo 3 (Fast)": "veo-3.0-fast-generate-001",
    "Veo 3 (Quality)": "veo-3.0-generate-001",
    "Veo 2": "veo-2.0-generate-001",
}
# fallback kandidat untuk Veo (jaga-jaga region/preview)
VIDEO_MODEL_FALLBACKS = {
    "Veo 3 (Preview)": ["veo-3.0-generate-preview", "veo-3.0-generate-001"],
    "Veo 3 (Fast)": ["veo-3.0-fast-generate-001", "veo-3.0-fast-generate-preview"],
    "Veo 3 (Quality)": ["veo-3.0-generate-001"],
    "Veo 2": ["veo-2.0-generate-001", "veo-2.0"],  # terakhir best-effort
}

# Imagen 4 & Gemini 2.5 Flash Image (Nano-Banana)
IMAGE_MODEL_LABELS = {
    "Imagen 4 (Quality)": "imagen-4.0-generate-001",
    "Gemini 2.5 Flash Image (Nano-Banana)": "gemini-2.5-flash-image-preview",
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

def guard_video_config(model_label: str, aspect: str, resolution: str):
    """Penuhi aturan dokumen: Veo 3 hanya 16:9; Veo 2 hanya 720p."""
    msg = None
    # Veo 3: 16:9 only (1080p & 720p); paksa ke 16:9 kalau user pilih lain
    if model_label in ("Veo 3 (Preview)", "Veo 3 (Fast)", "Veo 3 (Quality)"):
        if aspect != "16:9":
            aspect = "16:9"
            msg = "Veo 3 hanya mendukung aspek 16:9. Otomatis diubah ke 16:9."
    # Veo 2: 720p only
    if model_label == "Veo 2" and resolution != "720p":
        resolution = "720p"
        msg = (msg + " " if msg else "") + "Veo 2 hanya 720p. Otomatis diubah ke 720p."
    return aspect, resolution, msg

def build_cfg(aspect: str, resolution: str, negative: str = "", seed: int = 0):
    kwargs = {"aspect_ratio": aspect, "resolution": resolution}
    if negative:
        kwargs["negative_prompt"] = negative
    if seed and seed > 0:
        kwargs["seed"] = seed
    return types.GenerateVideosConfig(**kwargs)

def generate_with_fallback(client, model_label: str, prompt: str, cfg: types.GenerateVideosConfig, image=None):
    """Coba beberapa ID model + fallback config agar robust."""
    candidates = VIDEO_MODEL_FALLBACKS.get(model_label, [VIDEO_MODEL_LABELS.get(model_label, "")])
    last_err = None
    for name in candidates:
        # 1) coba apa adanya
        try:
            return client.models.generate_videos(model=name, prompt=prompt, image=image, config=cfg), name
        except Exception as e1:
            last_err = e1
        # 2) fallback config aman
        try:
            cfg2 = types.GenerateVideosConfig(aspect_ratio="16:9", resolution="720p")
            return client.models.generate_videos(model=name, prompt=prompt, image=image, config=cfg2), name
        except Exception as e2:
            last_err = e2
        # 3) fallback minimal
        try:
            cfg3 = types.GenerateVideosConfig(aspect_ratio="16:9", resolution="720p")
            return client.models.generate_videos(model=name, prompt=prompt, image=image, config=cfg3), name
        except Exception as e3:
            last_err = e3
            continue
    raise last_err

# ========== TABS ==========
tab1, tab2, tab3 = st.tabs(["Text → Video", "Image → Video (multi)", "Generate Image"])

# ===================== TAB 1 — TEXT → VIDEO =====================
with tab1:
    st.subheader("Text → Video (Batch)")

    col_left, col_right = st.columns([1, 1])
    with col_left:
        video_model_label = st.selectbox("Model Video", list(VIDEO_MODEL_LABELS.keys()), index=1)
        aspect = st.selectbox("Aspect Ratio", ["16:9", "9:16"], index=0)
        resolution = st.selectbox("Resolution", ["720p", "1080p"], index=0,
                                  help="Veo 3: 16:9 only. Veo 2: 720p only.")
        seed = st.number_input("Seed (opsional)", min_value=0, step=1, value=0,
                               help="Seed = angka untuk hasil yang lebih konsisten (tidak 100% deterministik).")
    with col_right:
        negative_prompt = st.text_input("Negative prompt (opsional)", value="")
        max_batch = st.number_input("Batas batch", min_value=1, max_value=50, value=10,
                                    help="Maksimal item diproses dalam satu run.")

    # jaga aturan model
    aspect, resolution, info_msg = guard_video_config(video_model_label, aspect, resolution)
    if info_msg:
        st.info(info_msg)

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

        overall = st.progress(0)
        status_global = st.empty()

        for idx, p in enumerate(prompts, start=1):
            section = st.container()
            with section:
                st.markdown(f"#### #{idx} Prompt")
                st.write(p)
                pbar = st.progress(0, text=f"Prompt #{idx}: menyiapkan…")

            try:
                cfg = build_cfg(aspect, resolution, negative_prompt, seed)
                op, model_used = generate_with_fallback(client, video_model_label, p, cfg, image=None)
            except Exception as e:
                with section:
                    st.error(f"Gagal mulai generate: {e}")
                overall.progress(int(idx / len(prompts) * 100))
                continue

            ticks = 0
            try:
                while not op.done:
                    time.sleep(6)
                    ticks += 1
                    op = client.operations.get(op)
                    pbar.progress(min(100, ticks * 7), text=f"Prompt #{idx}: processing… ({model_used})")

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
                        st.caption(f"Model: {model_used}")
                        with open(out_name, "rb") as f:
                            st.download_button("⬇️ Download MP4", data=f, file_name=out_name, mime="video/mp4")
            except Exception as e:
                with section:
                    st.error(f"Error saat proses/unduh: {e}")

            overall.progress(int(idx / len(prompts) * 100))
            status_global.info(f"Selesai #{idx}/{len(prompts)}")

# ===================== TAB 2 — IMAGE → VIDEO (MULTI) =====================
with tab2:
    st.subheader("Image → Video (Multi Image Upload)")

    col_left, col_right = st.columns([1, 1])
    with col_left:
        video_model_label_i2v = st.selectbox("Model Video", list(VIDEO_MODEL_LABELS.keys()), index=1, key="i2v_model")
        aspect_i2v = st.selectbox("Aspect Ratio", ["16:9", "9:16"], index=0, key="i2v_ar")
        resolution_i2v = st.selectbox("Resolution", ["720p", "1080p"], index=0, key="i2v_res",
                                      help="Veo 3: 16:9 only. Veo 2: 720p only.")
        seed_i2v = st.number_input("Seed (opsional)", min_value=0, step=1, value=0, key="i2v_seed",
                                   help="Seed = angka untuk hasil yang lebih konsisten.")
    with col_right:
        negative_prompt_i2v = st.text_input("Negative prompt (opsional)", value="", key="i2v_neg")
        max_batch_i2v = st.number_input("Batas batch", min_value=1, max_value=50, value=10, key="i2v_batch",
                                        help="Maksimum total item (gambar/prompt) diproses dalam satu run.")

    # guard
    aspect_i2v, resolution_i2v, info_msg2 = guard_video_config(video_model_label_i2v, aspect_i2v, resolution_i2v)
    if info_msg2:
        st.info(info_msg2)

    uploaded_images = st.file_uploader(
        "Upload beberapa gambar (PNG/JPG) — bisa pilih banyak sekaligus",
        type=["png", "jpg", "jpeg"], accept_multiple_files=True
    )

    st.caption("📝 Prompt pairing:\n"
               "- Kalau **1 baris prompt**, dipakai untuk **semua gambar**.\n"
               "- Kalau **>1 baris**, baris ke-N dipakai untuk **gambar ke-N** (kelebihan gambar pakai prompt terakhir).")

    prompts_text_i2v = st.text_area(
        "📝 Prompt (alignment sesuai urutan gambar)",
        height=160,
        placeholder="Contoh:\nOrbit pelan, cinematic rain\nDolly-in, dramatic lighting",
        key="i2v_text",
    )

    images = uploaded_images or []
    if images and len(images) > int(max_batch_i2v):
        st.warning(f"Jumlah gambar > batas batch ({int(max_batch_i2v)}). Yang diproses hanya {int(max_batch_i2v)} pertama.")
        images = images[: int(max_batch_i2v)]

    raw_prompts_i2v = [ln.strip() for ln in (prompts_text_i2v or "").split("\n") if ln.strip()]
    if raw_prompts_i2v and len(raw_prompts_i2v) > int(max_batch_i2v):
        raw_prompts_i2v = raw_prompts_i2v[: int(max_batch_i2v)]

    run_i2v = st.button(
        f"🚀 Generate Video untuk {len(images) if images else 0} Gambar",
        type="primary"
    )

    if run_i2v:
        if not images:
            st.error("Upload minimal 1 gambar.")
            st.stop()

        overall_i2v = st.progress(0)
        status_i2v = st.empty()

        total = len(images)
        for idx, img_file in enumerate(images, start=1):
            # pilih prompt untuk gambar ini
            if len(raw_prompts_i2v) == 0:
                p = ""
            elif len(raw_prompts_i2v) == 1:
                p = raw_prompts_i2v[0]
            else:
                p = raw_prompts_i2v[min(idx-1, len(raw_prompts_i2v)-1)]

            section = st.container()
            with section:
                st.markdown(f"#### (I2V) Gambar #{idx}/{total}")
                st.image(img_file, width=280)
                st.write(f"**Prompt dipakai:** {p if p else '(kosong)'}")
                pbar = st.progress(0, text=f"Gambar #{idx}: menyiapkan…")

            image_bytes = img_file.read()
            mime = img_file.type or "image/png"
            image_input = types.Image(image_bytes=image_bytes, mime_type=mime)

            try:
                cfg = build_cfg(aspect_i2v, resolution_i2v, negative_prompt_i2v, seed_i2v)
                op, model_used = generate_with_fallback(client, video_model_label_i2v, p, cfg, image=image_input)
            except Exception as e:
                with section:
                    st.error(f"Gagal mulai generate: {e}")
                overall_i2v.progress(int(idx / total * 100))
                continue

            # Polling per-gambar
            ticks = 0
            try:
                while not op.done:
                    time.sleep(6)
                    ticks += 1
                    op = client.operations.get(op)
                    pbar.progress(min(100, ticks * 7), text=f"Gambar #{idx}: processing… ({model_used})")

                pbar.progress(100, text=f"Gambar #{idx}: mengunduh…")

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
                        st.caption(f"Model: {model_used}")
                        with open(out_name, "rb") as f:
                            st.download_button("⬇️ Download MP4", data=f, file_name=out_name, mime="video/mp4")
            except Exception as e:
                with section:
                    st.error(f"Error saat proses/unduh: {e}")

            overall_i2v.progress(int(idx / total * 100))
            status_i2v.info(f"Selesai gambar #{idx}/{total}")

# ===================== TAB 3 — GENERATE IMAGE (Imagen 4 / Gemini 2.5 Flash Image) =====================
with tab3:
    st.subheader("Generate Image")

    image_model_label = st.selectbox(
        "Model Gambar",
        list(IMAGE_MODEL_LABELS.keys()),
        index=0,
        help="Pilih Imagen 4 untuk T2I berkualitas; atau Gemini 2.5 Flash Image (Nano-Banana) untuk generate/edit yang lincah."
    )
    img_seed = st.number_input("Seed (opsional)", min_value=0, step=1, value=0,
                               help="Seed = angka untuk hasil yang lebih konsisten (tidak 100% deterministik).")
    max_batch_img = st.number_input("Batas batch", min_value=1, max_value=50, value=8,
                                    help="Maksimum jumlah gambar per run.")
    aspect_img = st.selectbox("Aspect Ratio", ["1:1", "3:4", "4:3", "9:16", "16:9"], index=0,
                              help="Aspect ratio didukung oleh Imagen 4; Gemini Flash Image akan mengusahakan komposisi serupa.")

    st.caption("Satu baris prompt = satu gambar. Kosongkan prompt bila ingin uji coba respons default (tidak disarankan).")

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
            st.error("Isi minimal 1 baris prompt (atau isi satu spasi untuk uji coba).")
            st.stop()

        model_id = IMAGE_MODEL_LABELS[image_model_label]
        overall_img = st.progress(0)
        status_img = st.empty()

        for idx, p in enumerate(prompts_img, start=1):
            section = st.container()
            with section:
                st.markdown(f"#### (IMG) #{idx} Prompt")
                st.write(p if p else "(prompt kosong)")

            try:
                # Imagen 4 mendukung aspect_ratio & number_of_images; Gemini 2.5 Flash Image juga via API Images
                cfg = types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=aspect_img
                )
                out = client.models.generate_images(
                    model=model_id,
                    prompt=p,
                    seed=img_seed or None,
                    config=cfg,
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

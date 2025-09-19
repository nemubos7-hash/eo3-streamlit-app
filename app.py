import os
import time
import streamlit as st

# SDK yang direkomendasikan untuk Veo 3
from google import genai
from google.genai import types

st.set_page_config(page_title="Veo 3 Video Generator (Batch)", layout="wide")
st.title("🎬 Veo 3 Video Generator — Batch Mode")
st.caption("Batch generate video 8 detik dengan Google Veo 3. (1 baris prompt = 1 video)")

# ===== API KEY =====
API_KEY = None
try:
    # Prioritas: Secrets di Streamlit Cloud
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

# ===== Kontrol =====
with st.sidebar:
    model = st.selectbox("Model", ["veo-3.0-generate-001", "veo-3.0-fast-generate-001"], index=1)
    aspect = st.selectbox("Aspect Ratio", ["16:9", "9:16"], index=1)
    resolution = st.selectbox("Resolution", ["720p", "1080p"], index=0, help="1080p stabil untuk 16:9. 9:16 → 720p.")
    if aspect == "9:16" and resolution == "1080p":
        st.info("Untuk 9:16, 1080p belum stabil → otomatis 720p.")
        resolution = "720p"
    seed = st.number_input("Seed (opsional)", min_value=0, step=1, value=0)
    negative_prompt = st.text_input("Negative prompt (opsional)", value="")
    max_batch = st.number_input("Batas batch", min_value=1, max_value=20, value=10)

st.subheader("📝 Prompt (satu baris = satu video)")
prompts_text = st.text_area(
    "Contoh:\n"
    "Kucing oranye berlari di bawah jamur raksasa; hujan; dialog: 'Aku bisa!'\n"
    "Produk minuman kaleng; splash slow motion; studio putih\n"
    "Anime action rooftop malam; neon; camera shake",
    height=180,
)

def collect_prompts(raw: str):
    lines = [ln.strip() for ln in (raw or "").split("\n")]
    lines = [ln for ln in lines if ln]
    return lines[: max_batch]

prompts = collect_prompts(prompts_text)

col1, col2 = st.columns(2)
with col1:
    run = st.button(f"🚀 Generate {len(prompts) if prompts else ''} Video", type="primary")
with col2:
    if st.button("🗑️ Reset"):
        st.experimental_rerun()

if not run:
    st.stop()
if not prompts:
    st.error("Isi minimal 1 baris prompt.")
    st.stop()

overall = st.progress(0)
status = st.empty()
results = []  # list of (prompt, filename, error)

for idx, p in enumerate(prompts, start=1):
    status.write(f"#{idx}/{len(prompts)} Mengirim job…")
    try:
        cfg = types.GenerateVideosConfig(
            aspect_ratio=aspect,
            resolution=resolution,
            negative_prompt=negative_prompt or None,
            seed=seed or None,
        )
        op = client.models.generate_videos(model=model, prompt=p, config=cfg)
    except Exception as e:
        results.append((p, None, f"Gagal mulai generate: {e}"))
        overall.progress(int(idx / len(prompts) * 100))
        continue

    # Polling
    poll = st.progress(0, text=f"Prompt #{idx}: processing…")
    ticks = 0
    try:
        while not op.done:
            time.sleep(6)
            ticks += 1
            op = client.operations.get(op)
            poll.progress(min(100, ticks * 7), text=f"Prompt #{idx}: processing…")

        poll.progress(100, text=f"Prompt #{idx}: mengunduh video…")

        vids = getattr(op.response, "generated_videos", [])
        if not vids:
            results.append((p, None, "Response tidak berisi video."))
        else:
            v = vids[0]
            client.files.download(file=v.video)  # ambil bytes ke object file
            out_name = f"veo_output_{idx:02d}.mp4"
            v.video.save(out_name)               # simpan ke disk
            results.append((p, out_name, None))
    except Exception as e:
        results.append((p, None, f"Error saat proses/unduh: {e}"))

    overall.progress(int(idx / len(prompts) * 100))

status.success("Selesai! Lihat hasil di bawah.")

# Tampilkan hasil
for i, (p, fname, err) in enumerate(results, start=1):
    with st.expander(f"#{i} Prompt: {p[:80]}{'…' if len(p) > 80 else ''}", expanded=bool(err)):
        if err:
            st.error(err)
        else:
            st.video(fname)
            with open(fname, "rb") as f:
                st.download_button("⬇️ Download MP4", data=f, file_name=fname, mime="video/mp4")

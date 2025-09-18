
# Veo 3 Video Generator (Streamlit + Gemini API)

Aplikasi Streamlit siap-deploy untuk membuat video 8 detik dengan **Veo 3** (Gemini API).

## 🚀 Cepat Pakai di Streamlit Community Cloud
1. **Buat repo GitHub baru** lalu upload semua file dalam folder ini.
2. Masuk ke **https://streamlit.io/cloud**, pilih *New app* → hubungkan ke repo.
3. Pada **Advanced settings → Secrets**, masukkan:
```
GEMINI_API_KEY = "ISI_API_KEY_KAMU"
```
4. Deploy → Kamu akan dapat URL publik seperti `https://username-veo3-app.streamlit.app`

> *Catatan:* kamu bisa juga set `GOOGLE_API_KEY` sebagai alternatif.

## 💻 Jalankan Lokal
```bash
pip install -r requirements.txt
export GEMINI_API_KEY="ISI_API_KEY_KAMU"   # atau set di Windows: setx GEMINI_API_KEY "ISI_API_KEY_KAMU"
streamlit run app.py
```

## ⚙️ Fitur
- Model: `veo-3.0-generate-001` (kualitas tinggi) atau `veo-3.0-fast-generate-001` (lebih cepat/hemat)
- Aspect ratio 16:9 / 9:16; resolusi 720p / 1080p*
- Negative prompt, seed, progress polling, preview, tombol **Download MP4**
- Baca API key dari **Secrets**, ENV, atau input field

\* 1080p terutama untuk 16:9; 9:16 tersedia, cek update dok terbaru.

## ❗ Syarat & Catatan
- Pastikan akun kamu memiliki akses ke **Veo 3** di Google AI Studio/Vertex.
- Set billing/project yang benar agar request tidak ditolak.
- Model video berjalan sebagai **long-running operation** → app ini melakukan polling sampai selesai.

## 🧩 Struktur
```
.
├─ app.py
├─ requirements.txt
├─ .streamlit/
│  ├─ config.toml
│  └─ secrets.toml.example
├─ README.md
└─ LICENSE
```

Selamat berkarya! 🎬

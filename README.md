# 🚀 OmniLoad - All-in-One Local & Web-App Media Downloader (MP3 / MP4)

โปรแกรมและเว็บแอปพลิเคชันสำหรับดาวน์โหลดวิดีโอและไฟล์เสียงจากทุกแพลตฟอร์มยอดนิยม **ไม่มีการจำกัดโควต้า (100% Unlimited)** ใช้งานได้ทั้งบนเครื่องคอมพิวเตอร์ของคุณ (Local Windows/Mac) หรือ Deploy ขึ้นเป็น **Web-App Server บน Cloud / VPS / Docker**

---

## 🌟 แพลตฟอร์มที่รองรับ (Supported Platforms)

- 🔴 **YouTube**: วิดีโอความคมชัดสูงสุด (4K / 1080p), Shorts, และแปลงเป็น MP3 320kbps คุณภาพสตูดิโอ
- 𝕏 **X (Twitter)**: คลิปและวิดีโอทวีต (รวมถึง Amplify 1080p Full HD)
- 🎵 **TikTok & Douyin**: วิดีโอแบบไม่มีลายน้ำ (No Watermark) และเพลงประกอบ
- 📸 **Instagram**: Reels, Video Posts, Stories
- 📌 **Pinterest**: วิดีโอจากพิน (Video Pins), ภาพ GIF, และรูปภาพความละเอียดสูงสุด (Originals) รวมถึงลิงก์ย่อ `pin.it`
- 📘 **Facebook**: Reels, Watch, คลิปสาธารณะ
- 🤖 **Reddit**: วิดีโอ `v.redd.it` พร้อมผสานเสียงอัตโนมัติ
- 🧵 **Threads**: โพสต์วิดีโอบน Threads
- ☁️ **SoundCloud**: สตรีมเพลงและแปลงเป็น MP3 320 kbps
- 📺 **Bilibili**: วิดีโอและอนิเมะ (รวมถึงลิงก์ย่อ `b23.tv`)
- 🟣 **Twitch**: Clips และ VODs
- 🦋 **Bluesky**: วิดีโอบน `bsky.app`
- 🎬 **Vimeo, Dailymotion, Streamable, Direct Links** (`.mp4`, `.mp3`, `.m3u8`)

---

## 💻 1. การใช้งานบนเครื่องส่วนตัว (Local Windows)

1. ดับเบิลคลิกที่ไฟล์ **`start.bat`** (หรือรัน `python run.py`)
2. ระบบจะทำการตรวจสอบความพร้อมและเปิดเบราว์เซอร์ไปที่ `http://127.0.0.1:8000` ให้อัตโนมัติ

---

## ⚡ 2. การ Deploy ขึ้น Vercel (Serverless Web-App)

โปรเจกต์นี้มีไฟล์ `vercel.json` และ `api/index.py` รองรับ Vercel 100%:

### วิธีที่ 1: Deploy ผ่าน Vercel CLI (ง่ายและเร็วสุด)
```bash
# ติดตั้ง vercel CLI (ถ้ายังไม่มี)
npm i -g vercel

# สั่ง Deploy ได้ทันที
vercel
```

### วิธีที่ 2: เชื่อมต่อผ่าน GitHub
1. Push โฟลเดอร์โปรเจกต์นี้ขึ้น GitHub Repository
2. เข้าเว็บ [vercel.com](https://vercel.com) แล้วกด **"Add New Project"** ➔ เลือก Repository ของคุณ
3. กด **Deploy** ได้ทันทีโดยไม่ต้องตั้งค่าเพิ่มเติมใดๆ

---

## 🐳 3. การ Deploy ด้วย Docker (Cloud / VPS)

สามารถนำโฟลเดอร์นี้ไปรันบน VPS (เช่น DigitalOcean, Hetzner, AWS, Google Cloud) หรือ Synology NAS / Railway / Render:

```bash
# รันด้วย Docker Compose ใน 1 คำสั่ง
docker-compose up -d --build
```
ระบบจะเปิดพอร์ต `8000` และแมปโฟลเดอร์ `downloads/` ให้อัตโนมัติ

---

## 🐧 3. การ Deploy บน Linux VPS (Ubuntu / Debian)

1. อัปโหลดไฟล์โปรเจกต์ขึ้น Server
2. รันสคริปต์ติดตั้งอัตโนมัติ:
```bash
chmod +x deploy.sh
./deploy.sh
```
สคริปต์จะติดตั้ง Python, FFmpeg, Dependencies และสร้าง Systemd Service ให้ทำงานอัตโนมัติตลอด 24 ชม.

---

## ⚙️ Environment Variables (สำหรับ Web-App)

คุณสามารถกำหนดค่าผ่านไฟล์ `.env` หรือตัวแปรระบบได้:

| Variable | ค่าเริ่มต้น | คำอธิบาย |
|---|---|---|
| `PORT` | `8000` | พอร์ตของเว็บแอปพลิเคชัน |
| `HOST` | `0.0.0.0` | IP Host สำหรับรับคำขอ |
| `DOWNLOAD_DIR` | `/app/downloads` | โฟลเดอร์จัดเก็บไฟล์ |
| `AUTO_CLEANUP_HOURS` | `24` | ล้างไฟล์ที่ดาวน์โหลดแล้วอัตโนมัติเมื่อครบ X ชั่วโมง (ตั้ง `0` เพื่อปิด) |
| `MAX_CONCURRENT` | `4` | จำนวนคิวที่ประมวลผลพร้อมกันสูงสุด |

---

## 📂 โครงสร้างโฟลเดอร์โปรเจกต์

```
├── app/
│   ├── main.py              # FastAPI Web Server, Streaming & WebSocket
│   ├── downloader.py        # Multi-Platform Engine & Fallback Extractors
│   ├── ffmpeg_setup.py      # Cross-Platform FFmpeg Resolver
│   └── config.py            # Configuration & Auto-cleanup engine
├── static/
│   ├── index.html           # Modern Responsive Cyber Dark Web UI
│   ├── app.js               # Frontend Controller & Real-Time Sync
│   └── style.css            # Platform-Specific Badges & Styling
├── Dockerfile               # Production Docker Container
├── docker-compose.yml       # Production Docker Stack
├── deploy.sh                # Linux VPS 1-Click Deployment Script
├── requirements.txt         # Dependencies list
├── run.py                   # Local Python Runner
└── start.bat                # Windows Launcher
```

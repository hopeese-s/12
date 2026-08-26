import os
import sys

# Ensure project root is in sys.path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Ensure UTF-8 output encoding on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import time
import urllib.request
import webbrowser
import threading
import subprocess

def check_dependencies():
    print("=" * 60)
    print(" OmniLoad - All-in-One Local Media Downloader (MP3 / MP4)")
    print("=" * 60)
    print("[1/3] Checking Python dependencies...")
    
    req_file = os.path.join(ROOT_DIR, "requirements.txt")
    try:
        import fastapi
        import uvicorn
        import yt_dlp
        import requests
        import websockets
        import imageio_ffmpeg
    except ImportError:
        print("[!] Installing required dependencies from requirements.txt...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])
    
    print("[2/3] Preparing FFmpeg Engine...")
    from app.ffmpeg_setup import ensure_ffmpeg
    ffmpeg_path = ensure_ffmpeg()
    print(f"[OK] FFmpeg is ready at: {ffmpeg_path}")

def open_browser_when_ready():
    """Polls server until it responds with 200 before launching browser."""
    print("[3/3] Waiting for OmniLoad server to be ready...")
    for _ in range(60): # wait up to 30s
        time.sleep(0.5)
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/", timeout=1) as response:
                if response.status == 200:
                    print("[OK] Server is ready! Opening Web Browser automatically...")
                    webbrowser.open("http://localhost:8000")
                    return
        except Exception:
            pass
    # Fallback if polling timed out
    webbrowser.open("http://localhost:8000")

def main():
    check_dependencies()
    
    # Run browser launcher in background thread
    threading.Thread(target=open_browser_when_ready, daemon=True).start()
    
    import uvicorn
    print("\n" + "=" * 60)
    print(" [OK] Server running at: http://localhost:8000 (0.0.0.0:8000)")
    print(" [i] 100% Local & Unlimited Mode")
    print(" [i] Keep this command prompt window OPEN while using OmniLoad")
    print(" [i] Press Ctrl + C to stop the server")
    print("=" * 60 + "\n")
    
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")

if __name__ == "__main__":
    main()

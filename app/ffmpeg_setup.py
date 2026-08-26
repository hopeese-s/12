import os
import sys
import shutil
import logging
import zipfile
import urllib.request

logger = logging.getLogger("ffmpeg_setup")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN_DIR = os.path.join(BASE_DIR, "bin")

def ensure_ffmpeg() -> str:
    """
    Ensures ffmpeg is available across Windows, Linux, and Docker.
    1. Checks system PATH (e.g. /usr/bin/ffmpeg on Linux/Docker)
    2. Checks local bin/ directory
    3. Checks imageio_ffmpeg
    4. Auto-downloads static release if on Windows
    """
    os.makedirs(BIN_DIR, exist_ok=True)
    
    # Add bin directory to PATH
    path_sep = ";" if sys.platform == "win32" else ":"
    if BIN_DIR not in os.environ.get("PATH", ""):
        os.environ["PATH"] = f"{BIN_DIR}{path_sep}" + os.environ.get("PATH", "")

    # 1. Check system PATH
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    # 2. Check local bin/
    local_ffmpeg = os.path.join(BIN_DIR, "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    if os.path.exists(local_ffmpeg):
        return local_ffmpeg

    # 3. Check imageio_ffmpeg
    try:
        import imageio_ffmpeg
        img_ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        if img_ffmpeg and os.path.exists(img_ffmpeg):
            if sys.platform == "win32":
                shutil.copy2(img_ffmpeg, local_ffmpeg)
                return local_ffmpeg
            return img_ffmpeg
    except Exception as e:
        logger.warning(f"imageio_ffmpeg check failed: {e}")

    # 4. If on Windows and still not found, download static release
    if sys.platform == "win32":
        try:
            logger.info("Downloading portable FFmpeg for Windows...")
            url = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
            zip_path = os.path.join(BIN_DIR, "ffmpeg.zip")
            
            urllib.request.urlretrieve(url, zip_path)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for member in zip_ref.namelist():
                    filename = os.path.basename(member)
                    if filename in ("ffmpeg.exe", "ffprobe.exe", "ffplay.exe"):
                        source = zip_ref.open(member)
                        target = open(os.path.join(BIN_DIR, filename), "wb")
                        with source, target:
                            shutil.copyfileobj(source, target)
            
            if os.path.exists(zip_path):
                os.remove(zip_path)
                
            if os.path.exists(local_ffmpeg):
                return local_ffmpeg
        except Exception as e:
            logger.error(f"Failed to auto-download FFmpeg: {e}")

    return BIN_DIR

import os
import sys
import json
import time
import subprocess
import logging

logger = logging.getLogger("config")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("NOW_REGION"))
DEFAULT_DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "/tmp/downloads" if IS_VERCEL else os.path.join(BASE_DIR, "downloads"))
BIN_DIR = "/tmp/bin" if IS_VERCEL else os.path.join(BASE_DIR, "bin")
CONFIG_FILE = "/tmp/settings.json" if IS_VERCEL else os.path.join(BASE_DIR, "settings.json")

# Environment configurations for Web-App / Cloud Deployments
PORT = int(os.environ.get("PORT", 8000))
HOST = os.environ.get("HOST", "0.0.0.0" if os.environ.get("DOCKER") or os.environ.get("PORT") else "127.0.0.1")
IS_CLOUD_DEPLOY = bool(IS_VERCEL or os.environ.get("DOCKER") or os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RENDER") or sys.platform != "win32")

DEFAULT_SETTINGS = {
    "download_dir": DEFAULT_DOWNLOAD_DIR,
    "embed_thumbnail": True,
    "embed_metadata": True,
    "video_format": "best",      # 'best', '1080', '720', '480'
    "audio_bitrate": "320",      # '320', '192', '128'
    "max_concurrent_downloads": int(os.environ.get("MAX_CONCURRENT", 4)),
    "auto_cleanup_hours": int(os.environ.get("AUTO_CLEANUP_HOURS", 24 if IS_CLOUD_DEPLOY else 0)), # 0 = disabled
    "is_cloud_mode": IS_CLOUD_DEPLOY
}

def load_settings():
    settings = DEFAULT_SETTINGS.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                settings.update(saved)
        except Exception as e:
            logger.warning(f"Failed to load settings.json: {e}")
    return settings

def save_settings(settings: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")

def get_download_dir():
    settings = load_settings()
    d = settings.get("download_dir", DEFAULT_DOWNLOAD_DIR)
    os.makedirs(d, exist_ok=True)
    return d

def cleanup_old_downloads():
    """Removes files older than auto_cleanup_hours if configured."""
    settings = load_settings()
    hours = settings.get("auto_cleanup_hours", 0)
    if hours <= 0:
        return {"deleted_count": 0, "freed_bytes": 0}

    download_dir = get_download_dir()
    cutoff_time = time.time() - (hours * 3600)
    deleted_count = 0
    freed_bytes = 0

    try:
        for fname in os.listdir(download_dir):
            fpath = os.path.join(download_dir, fname)
            if os.path.isfile(fpath):
                stat = os.stat(fpath)
                if stat.st_mtime < cutoff_time:
                    freed_bytes += stat.st_size
                    os.remove(fpath)
                    deleted_count += 1
                    logger.info(f"Auto-cleaned expired file: {fname}")
    except Exception as e:
        logger.error(f"Error during auto-cleanup: {e}")

    return {"deleted_count": deleted_count, "freed_bytes": freed_bytes}

def open_in_file_manager(path: str = None):
    """Opens the directory or highlights the file in local OS file manager."""
    target = path or get_download_dir()
    target = os.path.abspath(target)
    
    if sys.platform == "win32":
        if os.path.isfile(target):
            subprocess.run(["explorer", "/select,", target])
        else:
            if not os.path.exists(target):
                os.makedirs(target, exist_ok=True)
            os.startfile(target)
    elif sys.platform == "darwin":
        subprocess.run(["open", target])
    else:
        # Linux / Docker (no GUI file explorer)
        pass

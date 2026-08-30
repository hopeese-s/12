import os
import sys
import time
import shutil
import asyncio
import logging
import subprocess
from typing import List, Optional
from pydantic import BaseModel

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks, File, UploadFile, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config import (
    BASE_DIR, 
    get_download_dir, 
    load_settings, 
    save_settings, 
    open_in_file_manager,
    cleanup_old_downloads,
    IS_CLOUD_DEPLOY
)
from app.ffmpeg_setup import ensure_ffmpeg
from app.downloader import (
    extract_video_info, 
    start_download_task, 
    TASKS, 
    SUBSCRIBERS,
    format_bytes,
    format_seconds
)
from app.converter import (
    pdf_to_images,
    images_to_pdf,
    convert_image,
    merge_pdfs
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

app = FastAPI(title="OmniLoad - All-in-One Local & Cloud Media Downloader", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background auto-cleanup worker
TASK_EXPIRY_SECONDS = 1800  # 30 minutes

async def periodic_cleanup():
    while True:
        try:
            await asyncio.sleep(300)  # Check every 5 minutes
            now = time.time()
            expired_ids = [
                tid for tid, t in list(TASKS.items())
                if now - t.get("created_at", now) > TASK_EXPIRY_SECONDS
            ]
            for tid in expired_ids:
                # Also delete the downloaded file if it exists
                try:
                    fpath = TASKS[tid].get("filepath") or ""
                    if fpath and os.path.exists(fpath):
                        os.remove(fpath)
                except Exception:
                    pass
                TASKS.pop(tid, None)
            if expired_ids:
                logger.info(f"Auto-purged {len(expired_ids)} expired task(s) from memory")
            cleanup_old_downloads()
        except Exception as e:
            logger.error(f"Periodic cleanup error: {e}")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(periodic_cleanup())
    ensure_ffmpeg()

# Pydantic Request Models
class InfoRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    format_type: str = "mp4"   # "mp4" or "mp3"
    quality: str = "best"      # "best", "1080", "720", "480", "320", "192", "128"
    custom_title: Optional[str] = ""
    direct_url: Optional[str] = ""

class BatchDownloadRequest(BaseModel):
    urls: List[str]
    format_type: str = "mp4"
    quality: str = "best"

class SettingsModel(BaseModel):
    download_dir: Optional[str] = None
    video_format: Optional[str] = None
    audio_bitrate: Optional[str] = None
    auto_cleanup_hours: Optional[int] = None
    embed_thumbnail: Optional[bool] = None
    embed_metadata: Optional[bool] = None

class FileActionRequest(BaseModel):
    filename: str

# =========================================================================
# API ENDPOINTS
# =========================================================================

@app.post("/api/info")
async def get_info(req: InfoRequest):
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="URL cannot be empty")
    loop = asyncio.get_running_loop()
    info = await loop.run_in_executor(None, extract_video_info, req.url.strip())
    return info

@app.post("/api/download")
async def create_download(req: DownloadRequest):
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="URL cannot be empty")
    task_id = await start_download_task(
        url=req.url.strip(),
        format_type=req.format_type,
        quality=req.quality,
        custom_title=req.custom_title or "",
        direct_url=req.direct_url or ""
    )
    return {"success": True, "task_id": task_id}

@app.post("/api/batch")
async def create_batch_download(req: BatchDownloadRequest):
    valid_urls = [u.strip() for u in req.urls if u and u.strip()]
    if not valid_urls:
        raise HTTPException(status_code=400, detail="No valid URLs provided")
    
    task_ids = []
    for url in valid_urls:
        t_id = await start_download_task(
            url=url,
            format_type=req.format_type,
            quality=req.quality
        )
        task_ids.append(t_id)
        await asyncio.sleep(0.08)

    return {"success": True, "task_ids": task_ids, "count": len(task_ids)}

@app.get("/api/tasks")
async def get_tasks():
    sorted_tasks = sorted(TASKS.values(), key=lambda x: x.get("created_at", 0), reverse=True)
    return sorted_tasks

@app.get("/api/history")
async def get_history():
    download_dir = get_download_dir()
    if not os.path.exists(download_dir):
        return []
    
    allowed_exts = {".mp4", ".mp3", ".m4a", ".webm", ".mkv", ".wav", ".opus", ".flac", ".jpg", ".png", ".gif"}
    items = []
    
    for fname in os.listdir(download_dir):
        fpath = os.path.join(download_dir, fname)
        if os.path.isfile(fpath):
            ext = os.path.splitext(fname)[1].lower()
            if ext in allowed_exts:
                stat = os.stat(fpath)
                if ext in {".mp3", ".m4a", ".wav", ".opus", ".flac"}:
                    media_type = "audio"
                elif ext in {".jpg", ".png", ".gif"}:
                    media_type = "image"
                else:
                    media_type = "video"

                items.append({
                    "filename": fname,
                    "filepath": fpath,
                    "media_type": media_type,
                    "size_bytes": stat.st_size,
                    "size_str": format_bytes(stat.st_size),
                    "created_at": stat.st_ctime,
                    "modified_at": stat.st_mtime,
                    "ext": ext.lstrip('.').upper(),
                    "download_url": f"/downloads/{fname}",
                    "stream_url": f"/api/stream/{fname}"
                })
    
    items.sort(key=lambda x: x["modified_at"], reverse=True)
    return items

@app.delete("/api/history/{filename}")
async def delete_history_item(filename: str):
    download_dir = get_download_dir()
    safe_name = os.path.basename(filename)
    fpath = os.path.join(download_dir, safe_name)
    if os.path.exists(fpath):
        try:
            os.remove(fpath)
            return {"success": True, "message": f"Deleted {safe_name}"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    raise HTTPException(status_code=404, detail="File not found")

@app.post("/api/open-folder")
async def open_folder():
    if IS_CLOUD_DEPLOY:
        return {"success": False, "message": "File explorer is disabled on cloud/docker deployment."}
    download_dir = get_download_dir()
    open_in_file_manager(download_dir)
    return {"success": True, "path": download_dir}

@app.post("/api/open-file")
async def open_file(req: FileActionRequest):
    if IS_CLOUD_DEPLOY:
        return {"success": False, "message": "File explorer is disabled on cloud/docker deployment."}
    download_dir = get_download_dir()
    safe_name = os.path.basename(req.filename)
    fpath = os.path.join(download_dir, safe_name)
    if os.path.exists(fpath):
        open_in_file_manager(fpath)
        return {"success": True, "path": fpath}
    raise HTTPException(status_code=404, detail="File not found")

@app.post("/api/cleanup-now")
async def trigger_cleanup():
    res = cleanup_old_downloads()
    return {"success": True, "result": res}

@app.get("/api/settings")
async def get_app_settings():
    return load_settings()

@app.post("/api/settings")
async def update_app_settings(req: SettingsModel):
    current = load_settings()
    update_data = req.model_dump(exclude_none=True)
    current.update(update_data)
    save_settings(current)
    return {"success": True, "settings": current}

@app.get("/api/system-status")
async def get_system_status():
    download_dir = get_download_dir()
    ffmpeg_path = ensure_ffmpeg()
    
    try:
        import yt_dlp.version
        ytdlp_ver = yt_dlp.version.__version__
    except Exception:
        ytdlp_ver = "unknown"
    
    total, used, free = shutil.disk_usage(download_dir)
    settings = load_settings()
    
    return {
        "python_version": sys.platform + " " + sys.version.split()[0],
        "ytdlp_version": ytdlp_ver,
        "ffmpeg_status": "Ready" if (shutil.which("ffmpeg") or os.path.exists(ffmpeg_path)) else "Missing",
        "ffmpeg_path": ffmpeg_path,
        "download_dir": download_dir,
        "disk_free_str": format_bytes(free),
        "disk_total_str": format_bytes(total),
        "disk_free_percent": round((free / total) * 100, 1) if total > 0 else 0,
        "is_cloud_mode": IS_CLOUD_DEPLOY,
        "auto_cleanup_hours": settings.get("auto_cleanup_hours", 0)
    }

@app.post("/api/update-ytdlp")
async def update_ytdlp():
    try:
        proc = subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"], capture_output=True, text=True, timeout=60)
        return {"success": proc.returncode == 0, "output": proc.stdout or proc.stderr}
    except Exception as e:
        return {"success": False, "error": str(e)}

# =========================================================================
# UNIVERSAL CONVERTER SUITE ENDPOINTS
# =========================================================================

@app.post("/api/convert/pdf-to-images")
async def api_pdf_to_images(
    file: UploadFile = File(...),
    output_format: str = Form("jpg"),
    dpi: int = Form(150),
    quality: int = Form(90)
):
    try:
        content = await file.read()
        res = pdf_to_images(
            pdf_bytes=content,
            original_filename=file.filename or "document.pdf",
            output_format=output_format,
            dpi=dpi,
            quality=quality
        )
        return res
    except Exception as e:
        logger.error(f"PDF to images error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/convert/images-to-pdf")
async def api_images_to_pdf(
    files: List[UploadFile] = File(...),
    pdf_name: str = Form("combined_images.pdf")
):
    try:
        image_items = []
        for f in files:
            content = await f.read()
            image_items.append((f.filename or "image.jpg", content))
        
        res = images_to_pdf(image_items=image_items, output_filename=pdf_name)
        return res
    except Exception as e:
        logger.error(f"Images to PDF error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/convert/image-to-image")
async def api_convert_image(
    files: List[UploadFile] = File(...),
    target_format: str = Form("jpg"),
    quality: int = Form(90)
):
    try:
        converted = []
        for f in files:
            content = await f.read()
            res = convert_image(
                image_bytes=content,
                original_filename=f.filename or "image.png",
                target_format=target_format,
                quality=quality
            )
            converted.append(res)
        return {"success": True, "results": converted, "count": len(converted)}
    except Exception as e:
        logger.error(f"Image format conversion error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/convert/pdf-merge")
async def api_merge_pdfs(
    files: List[UploadFile] = File(...),
    output_filename: str = Form("merged_document.pdf")
):
    try:
        pdf_items = []
        for f in files:
            content = await f.read()
            pdf_items.append((f.filename or "doc.pdf", content))
        res = merge_pdfs(pdf_items=pdf_items, output_filename=output_filename)
        return res
    except Exception as e:
        logger.error(f"PDF merge error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# Serve downloaded files for browser downloading (attachment mode)
@app.get("/downloads/{filename}")
async def serve_downloaded_file(filename: str):
    download_dir = get_download_dir()
    safe_name = os.path.basename(filename)
    fpath = os.path.join(download_dir, safe_name)
    if os.path.exists(fpath):
        return FileResponse(fpath, filename=safe_name, media_type="application/octet-stream")
    raise HTTPException(status_code=404, detail="File not found")

# Serve inline stream for media player playback
@app.get("/api/stream/{filename}")
async def stream_media_file(filename: str):
    download_dir = get_download_dir()
    safe_name = os.path.basename(filename)
    fpath = os.path.join(download_dir, safe_name)
    if os.path.exists(fpath):
        ext = os.path.splitext(safe_name)[1].lower()
        content_type = "audio/mpeg" if ext == ".mp3" else "video/mp4" if ext == ".mp4" else "application/octet-stream"
        return FileResponse(fpath, media_type=content_type)
    raise HTTPException(status_code=404, detail="File not found")

# WebSocket Endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    queue = asyncio.Queue()
    SUBSCRIBERS.append(queue)
    try:
        await websocket.send_json({"type": "init", "tasks": list(TASKS.values())})
        while True:
            msg = await queue.get()
            await websocket.send_json(msg)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if queue in SUBSCRIBERS:
            SUBSCRIBERS.remove(queue)

STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"message": "OmniLoad API Server running."})

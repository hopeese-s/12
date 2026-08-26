import os
import re
import time
import uuid
import asyncio
import logging
import urllib.parse
from typing import Dict, Any, Optional, List
import requests
import yt_dlp

from app.config import get_download_dir, BIN_DIR
from app.ffmpeg_setup import ensure_ffmpeg

logger = logging.getLogger("downloader")

TASKS: Dict[str, Dict[str, Any]] = {}
SUBSCRIBERS: List[asyncio.Queue] = []

def clean_error_message(err_str: str) -> str:
    """Strips ANSI escape codes and cleans error messages."""
    if not err_str:
        return "Unknown error"
    cleaned = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', err_str)
    cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
    cleaned = cleaned.replace("ERROR: ", "").strip()
    return cleaned

def unshorten_url(url: str) -> str:
    """Resolves short links like pin.it, youtu.be, t.co, vt.tiktok.com, b23.tv, fb.watch."""
    url_lower = url.lower()
    short_domains = ["pin.it", "vt.tiktok.com", "vm.tiktok.com", "b23.tv", "fb.watch", "t.co", "bit.ly", "tinyurl.com"]
    
    if any(d in url_lower for d in short_domains):
        try:
            resp = requests.head(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, allow_redirects=True, timeout=6)
            if resp.url and resp.url != url:
                logger.info(f"Unshortened {url} -> {resp.url}")
                return resp.url
        except Exception as e:
            logger.warning(f"Could not unshorten {url}: {e}")
    return url

def detect_platform(url: str) -> str:
    url_lower = url.lower()
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "YouTube"
    elif "twitter.com" in url_lower or "x.com" in url_lower:
        return "X (Twitter)"
    elif "tiktok.com" in url_lower or "douyin.com" in url_lower:
        return "TikTok"
    elif "instagram.com" in url_lower:
        return "Instagram"
    elif "pinterest.com" in url_lower or "pin.it" in url_lower:
        return "Pinterest"
    elif "facebook.com" in url_lower or "fb.watch" in url_lower:
        return "Facebook"
    elif "reddit.com" in url_lower or "redd.it" in url_lower:
        return "Reddit"
    elif "threads.net" in url_lower:
        return "Threads"
    elif "soundcloud.com" in url_lower:
        return "SoundCloud"
    elif "bilibili.com" in url_lower or "b23.tv" in url_lower:
        return "Bilibili"
    elif "twitch.tv" in url_lower:
        return "Twitch"
    elif "bsky.app" in url_lower:
        return "Bluesky"
    elif "vimeo.com" in url_lower:
        return "Vimeo"
    elif "dailymotion.com" in url_lower:
        return "Dailymotion"
    elif "kuaishou.com" in url_lower:
        return "Kuaishou"
    return "Web Media"

def broadcast_task_update(task_id: str):
    """Notify all connected websockets about task update."""
    if task_id in TASKS:
        data = TASKS[task_id]
        for q in SUBSCRIBERS[:]:
            try:
                q.put_nowait({"type": "task_update", "data": data})
            except Exception:
                pass

def format_bytes(size: Optional[float]) -> str:
    if not size or size <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_idx = 0
    while size >= 1024 and unit_idx < len(units) - 1:
        size /= 1024.0
        unit_idx += 1
    return f"{size:.2f} {units[unit_idx]}"

def format_seconds(seconds: Optional[float]) -> str:
    if seconds is None or seconds < 0:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

# =========================================================================
# SPECIALIZED FALLBACK EXTRACTORS
# =========================================================================

def extract_twitter_fallback(url: str) -> Optional[Dict[str, Any]]:
    """Fallback extractor for Twitter/X videos."""
    match = re.search(r'(?:status|statuses)/(\d+)', url)
    if not match:
        digit_match = re.search(r'/(\d{15,25})', url)
        if digit_match:
            tweet_id = digit_match.group(1)
        else:
            return None
    else:
        tweet_id = match.group(1)

    endpoints = [
        f"https://api.fxtwitter.com/status/{tweet_id}",
        f"https://api.vxtwitter.com/status/{tweet_id}",
        f"https://api.fixupx.com/status/{tweet_id}",
    ]

    for ep in endpoints:
        try:
            resp = requests.get(ep, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=7)
            if resp.status_code == 200:
                data = resp.json()
                tweet = data.get('tweet', {})
                media = tweet.get('media', {})
                videos = media.get('videos', [])
                if not videos:
                    all_media = media.get('all', [])
                    videos = [m for m in all_media if m.get('type') in ('video', 'gif')]

                if videos:
                    v = videos[0]
                    raw_text = tweet.get('text', f"Tweet_{tweet_id}").strip()
                    title = re.sub(r'https?://\S+', '', raw_text).strip()
                    if not title:
                        title = f"Twitter_{tweet_id}"
                    
                    author = tweet.get('author', {})
                    uploader = author.get('name') or author.get('screen_name') or 'Twitter'
                    thumbnail = v.get('thumbnail_url') or ''
                    duration = int(v.get('duration') or 0)

                    variants = v.get('variants', []) or v.get('formats', [])
                    mp4_variants = [var for var in variants if 'mp4' in str(var.get('content_type', '')) or var.get('container') == 'mp4' or '.mp4' in str(var.get('url', ''))]
                    mp4_variants.sort(key=lambda x: x.get('bitrate', 0), reverse=True)
                    
                    best_url = mp4_variants[0].get('url') if mp4_variants else v.get('url')

                    if best_url:
                        return {
                            "success": True,
                            "url": url,
                            "direct_url": best_url,
                            "platform": "X (Twitter)",
                            "title": title[:100],
                            "thumbnail": thumbnail,
                            "duration": duration,
                            "duration_formatted": format_seconds(duration),
                            "uploader": uploader,
                            "available_qualities": ["Best Quality (Original)", "1080p", "720p", "480p"],
                            "is_playlist": False,
                            "entry_count": 1,
                            "is_fallback": True
                        }
        except Exception as e:
            logger.warning(f"Twitter fallback endpoint {ep} error: {e}")

    return None

def extract_pinterest_fallback(url: str) -> Optional[Dict[str, Any]]:
    """Fallback extractor for Pinterest video & image pins."""
    real_url = unshorten_url(url)
    try:
        resp = requests.get(real_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
        }, timeout=8)
        
        if resp.status_code == 200:
            html = resp.text
            
            # Find video URL in HTML
            # Patterns: "url":"https://v.pinimg.com/videos/mc/720p/..." or <video src="..."
            video_match = re.search(r'"(https://v\.pinimg\.com/videos/[^"]+\.mp4)"', html)
            if not video_match:
                video_match = re.search(r'<video[^>]+src=["\'](https://[^"\']+\.mp4)["\']', html)
            
            # Find thumbnail / title
            title_match = re.search(r'<meta property="og:title" content="([^"]+)"', html)
            title = title_match.group(1) if title_match else "Pinterest Pin"
            
            thumb_match = re.search(r'<meta property="og:image" content="([^"]+)"', html)
            thumbnail = thumb_match.group(1) if thumb_match else ""

            if video_match:
                video_url = video_match.group(1).replace("\\/", "/")
                return {
                    "success": True,
                    "url": real_url,
                    "direct_url": video_url,
                    "platform": "Pinterest",
                    "title": title[:100],
                    "thumbnail": thumbnail,
                    "duration": 0,
                    "duration_formatted": "--:--",
                    "uploader": "Pinterest Creator",
                    "available_qualities": ["Best Quality (Original Video)", "720p", "480p"],
                    "is_playlist": False,
                    "entry_count": 1,
                    "is_fallback": True
                }
    except Exception as e:
        logger.warning(f"Pinterest fallback error: {e}")
    return None

# =========================================================================
# GENERAL VIDEO INFO EXTRACTOR
# =========================================================================

def get_ffmpeg_location() -> Optional[str]:
    try:
        ffmpeg_exe = ensure_ffmpeg()
        if ffmpeg_exe and os.path.exists(ffmpeg_exe):
            if os.path.isfile(ffmpeg_exe):
                return os.path.dirname(ffmpeg_exe)
            return ffmpeg_exe
    except Exception:
        pass
    return None

def extract_video_info(url: str) -> Dict[str, Any]:
    """
    Extracts metadata from URL without downloading.
    Supports YouTube, TikTok, Facebook, Instagram, Twitter/X, SoundCloud, Pinterest, etc.
    """
    url_clean = unshorten_url(url.strip())
    
    # 1. Fast path for Twitter/X
    if "twitter.com" in url_clean.lower() or "x.com" in url_clean.lower():
        fb = extract_twitter_fallback(url_clean)
        if fb:
            return fb

    # 2. Fast path for Pinterest
    if "pinterest.com" in url_clean.lower() or "pin.it" in url_clean.lower():
        pin_fb = extract_pinterest_fallback(url_clean)
        if pin_fb:
            return pin_fb

    # 3. Standard yt-dlp Extractor
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'no_color': True,
        'extract_flat': False,
        'skip_download': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        }
    }
    ff_loc = get_ffmpeg_location()
    if ff_loc:
        ydl_opts['ffmpeg_location'] = ff_loc
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url_clean, download=False)
            if not info:
                raise ValueError("Could not extract media info")
            
            if 'entries' in info and info['entries']:
                first_entry = list(info['entries'])[0]
                title = info.get('title') or first_entry.get('title', 'Unknown Title')
                thumbnail = info.get('thumbnail') or first_entry.get('thumbnail', '')
                duration = sum([e.get('duration', 0) for e in info['entries'] if e and e.get('duration')])
                is_playlist = True
                entry_count = len(info['entries'])
            else:
                title = info.get('title', 'Unknown Title')
                thumbnail = info.get('thumbnail', '')
                duration = info.get('duration', 0)
                is_playlist = False
                entry_count = 1

            formats = info.get('formats', [])
            heights = sorted(list(set([f.get('height') for f in formats if f.get('height') and f.get('vcodec') != 'none'])), reverse=True)

            return {
                "success": True,
                "url": url_clean,
                "platform": detect_platform(url_clean),
                "title": title,
                "thumbnail": thumbnail,
                "duration": duration,
                "duration_formatted": format_seconds(duration),
                "uploader": info.get('uploader') or info.get('channel') or info.get('creator') or info.get('artist') or 'Unknown',
                "available_qualities": [f"{h}p" for h in heights] if heights else ["Best Quality", "1080p", "720p", "480p"],
                "is_playlist": is_playlist,
                "entry_count": entry_count
            }
        except Exception as e:
            err_msg = str(e)
            logger.warning(f"yt-dlp extract failed for {url_clean}: {err_msg}")
            
            # Re-check fallbacks on error
            if "twitter.com" in url_clean.lower() or "x.com" in url_clean.lower():
                fb = extract_twitter_fallback(url_clean)
                if fb: return fb

            if "pinterest.com" in url_clean.lower() or "pin.it" in url_clean.lower():
                pin_fb = extract_pinterest_fallback(url_clean)
                if pin_fb: return pin_fb
            
            return {
                "success": False,
                "url": url_clean,
                "platform": detect_platform(url_clean),
                "error": clean_error_message(err_msg)
            }

# =========================================================================
# DOWNLOAD JOB
# =========================================================================

class DownloadJob:
    def __init__(self, task_id: str, url: str, format_type: str = "mp4", quality: str = "best", custom_title: str = "", direct_url: str = ""):
        self.task_id = task_id
        self.url = unshorten_url(url.strip())
        self.direct_url = direct_url
        self.format_type = format_type.lower() # 'mp4' or 'mp3'
        self.quality = quality                  # 'best', '1080', '720', '480', '320', '192', '128'
        self.custom_title = custom_title
        self.platform = detect_platform(self.url)
        self.output_path = ""
        self.filename = ""
        self.final_filepath = ""

    def progress_hook(self, d: Dict[str, Any]):
        status = d.get('status')
        task = TASKS.get(self.task_id)
        if not task:
            return

        if status == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes') or 0
            speed = d.get('speed') or 0
            eta = d.get('eta') or 0
            
            percent = 0.0
            if total > 0:
                percent = round((downloaded / total) * 100, 1)
            elif '_percent_str' in d:
                clean_pct = re.sub(r'[^\d.]', '', d['_percent_str'])
                try:
                    percent = float(clean_pct)
                except ValueError:
                    percent = 0.0

            filename = os.path.basename(d.get('filename', ''))
            
            task.update({
                "status": "downloading",
                "percent": percent,
                "downloaded_bytes": downloaded,
                "downloaded_str": format_bytes(downloaded),
                "total_bytes": total,
                "total_str": format_bytes(total) if total > 0 else "Calculating...",
                "speed": speed,
                "speed_str": f"{format_bytes(speed)}/s" if speed > 0 else "--",
                "eta": eta,
                "eta_str": format_seconds(eta),
                "current_file": filename
            })
            broadcast_task_update(self.task_id)

        elif status == 'finished':
            task.update({
                "status": "processing",
                "percent": 100.0,
                "eta_str": "Processing...",
                "speed_str": "Merging/Converting..."
            })
            broadcast_task_update(self.task_id)

    def postprocessor_hook(self, d: Dict[str, Any]):
        status = d.get('status')
        task = TASKS.get(self.task_id)
        if not task:
            return
        if status == 'started':
            task.update({
                "status": "processing",
                "eta_str": "Post-processing..."
            })
            broadcast_task_update(self.task_id)
        elif status == 'finished':
            info = d.get('info_dict', {})
            filepath = info.get('filepath') or info.get('_filename') or ''
            if filepath and os.path.exists(filepath):
                self.final_filepath = filepath
                self.filename = os.path.basename(filepath)

    def run(self):
        download_dir = get_download_dir()
        ensure_ffmpeg()
        
        task = TASKS.get(self.task_id)
        if task:
            task["status"] = "starting"
            broadcast_task_update(self.task_id)

        target_url = self.url
        
        # Check platform-specific fallbacks
        if ("twitter.com" in self.url.lower() or "x.com" in self.url.lower()) and not self.direct_url:
            fb = extract_twitter_fallback(self.url)
            if fb and fb.get("direct_url"):
                self.direct_url = fb.get("direct_url")
                if not self.custom_title and fb.get("title"):
                    self.custom_title = fb.get("title")

        if ("pinterest.com" in self.url.lower() or "pin.it" in self.url.lower()) and not self.direct_url:
            pin_fb = extract_pinterest_fallback(self.url)
            if pin_fb and pin_fb.get("direct_url"):
                self.direct_url = pin_fb.get("direct_url")
                if not self.custom_title and pin_fb.get("title"):
                    self.custom_title = pin_fb.get("title")

        if self.direct_url:
            target_url = self.direct_url

        # Sanitize filename template
        outtmpl = os.path.join(download_dir, '%(title).120B [%(id)s].%(ext)s')
        if self.custom_title:
            clean_custom = re.sub(r'[\\/*?:"<>|]', "", self.custom_title).strip()
            if clean_custom:
                outtmpl = os.path.join(download_dir, f"{clean_custom[:80]}.%(ext)s")

        ydl_opts: Dict[str, Any] = {
            'outtmpl': outtmpl,
            'quiet': True,
            'no_warnings': True,
            'no_color': True,
            'progress_hooks': [self.progress_hook],
            'postprocessor_hooks': [self.postprocessor_hook],
            'windowsfilenames': True,
            'restrictfilenames': False,
            'overwrites': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            }
        }

        ff_loc = get_ffmpeg_location()
        if ff_loc:
            ydl_opts['ffmpeg_location'] = ff_loc

        if self.format_type == 'mp3':
            bitrate = self.quality if self.quality in ['320', '192', '128'] else '320'
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': bitrate,
                    },
                    {
                        'key': 'FFmpegMetadata',
                        'add_metadata': True,
                    }
                ]
            })
        else:
            q = self.quality
            if q == '1080':
                fmt = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best'
            elif q == '720':
                fmt = 'bestvideo[height<=720]+bestaudio/best[height<=720]/best'
            elif q == '480':
                fmt = 'bestvideo[height<=480]+bestaudio/best[height<=480]/best'
            else:
                fmt = 'bestvideo+bestaudio/best'

            ydl_opts.update({
                'format': fmt,
                'merge_output_format': 'mp4',
                'postprocessors': [
                    {
                        'key': 'FFmpegMetadata',
                        'add_metadata': True,
                    }
                ]
            })

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(target_url, download=True)
                
                # Retrieve final filename
                if not self.final_filepath:
                    if info:
                        if 'requested_downloads' in info and info['requested_downloads']:
                            self.final_filepath = info['requested_downloads'][0].get('filepath', '')
                        if not self.final_filepath:
                            self.final_filepath = ydl.prepare_filename(info)
                            
                        if self.format_type == 'mp3':
                            base_no_ext = os.path.splitext(self.final_filepath)[0]
                            mp3_path = base_no_ext + ".mp3"
                            if os.path.exists(mp3_path):
                                self.final_filepath = mp3_path
                
                if self.final_filepath and os.path.exists(self.final_filepath):
                    self.filename = os.path.basename(self.final_filepath)
                    file_size = os.path.getsize(self.final_filepath)
                else:
                    files = [os.path.join(download_dir, f) for f in os.listdir(download_dir) if os.path.isfile(os.path.join(download_dir, f))]
                    if files:
                        newest = max(files, key=os.path.getctime)
                        self.final_filepath = newest
                        self.filename = os.path.basename(newest)
                        file_size = os.path.getsize(newest)
                    else:
                        file_size = 0

                title = self.custom_title or (info.get('title') if info else self.filename)
                thumbnail = info.get('thumbnail', '') if info else ''
                duration = info.get('duration', 0) if info else 0

                if task:
                    task.update({
                        "status": "completed",
                        "percent": 100.0,
                        "title": title,
                        "thumbnail": thumbnail,
                        "duration": duration,
                        "duration_str": format_seconds(duration),
                        "filename": self.filename,
                        "filepath": self.final_filepath,
                        "file_size": file_size,
                        "file_size_str": format_bytes(file_size),
                        "completed_at": time.time()
                    })
                    broadcast_task_update(self.task_id)

        except Exception as e:
            # Fallback retry on failure
            if ("twitter.com" in self.url.lower() or "x.com" in self.url.lower()) and not self.direct_url:
                try:
                    fb = extract_twitter_fallback(self.url)
                    if fb and fb.get("direct_url"):
                        self.direct_url = fb.get("direct_url")
                        self.custom_title = self.custom_title or fb.get("title")
                        self.run()
                        return
                except Exception:
                    pass

            if ("pinterest.com" in self.url.lower() or "pin.it" in self.url.lower()) and not self.direct_url:
                try:
                    pin_fb = extract_pinterest_fallback(self.url)
                    if pin_fb and pin_fb.get("direct_url"):
                        self.direct_url = pin_fb.get("direct_url")
                        self.custom_title = self.custom_title or pin_fb.get("title")
                        self.run()
                        return
                except Exception:
                    pass

            clean_err = clean_error_message(str(e))
            logger.error(f"Download task {self.task_id} failed: {clean_err}")
            if task:
                task.update({
                    "status": "error",
                    "error": clean_err,
                    "completed_at": time.time()
                })
                broadcast_task_update(self.task_id)

async def start_download_task(url: str, format_type: str = "mp4", quality: str = "best", custom_title: str = "", direct_url: str = "") -> str:
    """Spawns an async download job."""
    task_id = str(uuid.uuid4())
    cleaned_url = unshorten_url(url.strip())
    TASKS[task_id] = {
        "task_id": task_id,
        "url": cleaned_url,
        "platform": detect_platform(cleaned_url),
        "format_type": format_type,
        "quality": quality,
        "status": "queued",
        "percent": 0.0,
        "speed_str": "--",
        "eta_str": "--",
        "downloaded_str": "0 B",
        "total_str": "--",
        "filename": "",
        "filepath": "",
        "created_at": time.time(),
        "error": None
    }
    broadcast_task_update(task_id)

    job = DownloadJob(task_id, cleaned_url, format_type, quality, custom_title, direct_url)
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, job.run)
    return task_id

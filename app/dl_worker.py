"""One-shot yt-dlp worker, so the web server itself never loads yt-dlp.

    python -m app.dl_worker info  <url>
        prints one line:  \x1eOMNI {"ok": true, "data": {...}}

    python -m app.dl_worker download   (reads a JSON job on stdin)
        prints a line per progress update:  \x1eOMNI {"task": {...}}

yt-dlp, ffmpeg post-processing and the HTTP buffers they allocate all live in
this process; when it exits the memory goes straight back to the OS. Only the
lines starting with the marker are protocol; anything else yt-dlp prints is
ignored by the parent.
"""
import json
import sys

MARK = "\x1eOMNI "
_out = sys.stdout


def emit(obj) -> None:
    _out.write(MARK + json.dumps(obj, ensure_ascii=False, default=str) + "\n")
    _out.flush()


def main() -> int:
    # Keep yt-dlp's own chatter off the protocol stream
    sys.stdout = sys.stderr
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    from app import downloader

    if mode == "info":
        try:
            emit({"ok": True, "data": downloader.extract_video_info(sys.argv[2])})
        except Exception as e:
            emit({"ok": False, "error": str(e)})
        return 0

    if mode == "download":
        job = json.loads(sys.stdin.read())
        task = job["task"]
        tid = task["task_id"]
        downloader.TASKS[tid] = task
        # Every progress update the job publishes is forwarded to the parent
        downloader.broadcast_task_update = lambda task_id: emit({"task": downloader.TASKS.get(task_id, {})})
        dj = downloader.DownloadJob(tid, job["url"], job["format_type"], job["quality"],
                                    job.get("custom_title", ""), job.get("direct_url", ""))
        try:
            dj.run()
        finally:
            emit({"task": downloader.TASKS.get(tid, {}), "final": True})
        return 0

    print("usage: python -m app.dl_worker info <url> | download", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())

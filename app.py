"""Local-only ranked video editor. Run with python app.py."""

import json
import mimetypes
import os
import re
import subprocess
import threading
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont
from open_browser import open_browser

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
UPLOADS = ROOT / "data" / "uploads"
EXPORTS = ROOT / "data" / "exports"
PREVIEWS = ROOT / "data" / "previews"
AUDIO = ROOT / "data" / "audio"
UPLOADS.mkdir(parents=True, exist_ok=True)
EXPORTS.mkdir(parents=True, exist_ok=True)
PREVIEWS.mkdir(parents=True, exist_ok=True)
AUDIO.mkdir(parents=True, exist_ok=True)
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
JOBS = {}
LOCK = threading.Lock()
MAX_UPLOAD = 2 * 1024 * 1024 * 1024
EXTENSIONS = {".mp4", ".mov", ".webm", ".m4v", ".mkv"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
FONT_BOLD = Path("C:/Windows/Fonts/arialbd.ttf")
FONT_REGULAR = Path("C:/Windows/Fonts/arial.ttf")
TITLE_FONTS = {
    "Arial": Path("C:/Windows/Fonts/arialbd.ttf"),
    "Impact": Path("C:/Windows/Fonts/impact.ttf"),
    "Georgia": Path("C:/Windows/Fonts/georgiab.ttf"),
    "Trebuchet": Path("C:/Windows/Fonts/trebucbd.ttf"),
    "Verdana": Path("C:/Windows/Fonts/verdanab.ttf"),
}


def font(size, bold=True, family=None):
    path = TITLE_FONTS.get(family) if family else (FONT_BOLD if bold else FONT_REGULAR)
    path = path or FONT_BOLD
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def safe_color(value, fallback):
    return value if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value) else fallback


def wrapped(draw, text, chosen_font, max_width):
    words = str(text).split()
    lines = []
    current = ""
    for word in words:
        attempt = f"{current} {word}".strip()
        if current and draw.textbbox((0, 0), attempt, font=chosen_font)[2] > max_width:
            lines.append(current)
            current = word
        else:
            current = attempt
    if current:
        lines.append(current)
    return lines[:3]


def make_overlay(project, active, target):
    image = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    title = str(project.get("title", ""))[:110].strip() or "Top Moments"
    family = project.get("titleFont", "Arial")
    title_size = max(60, min(100, int(project.get("titleSize", 77))))
    title_font = font(title_size, family=family)
    title_color = safe_color(project.get("titleColor"), "#ffffff")
    accent_color = safe_color(project.get("accentColor"), "#45b6ff")
    title_lines = wrapped(draw, title, title_font, 980)
    y = 168
    for line in title_lines:
        draw.text((540, y), line, font=title_font, anchor="ma", fill=title_color,
                  stroke_width=6, stroke_fill="#101015")
        y += 88
    accent = str(project.get("accent", ""))[:40].strip()
    if accent:
        draw.text((540, y), accent, font=title_font, anchor="ma", fill=accent_color,
                  stroke_width=6, stroke_fill="#101015")

    clips = project["clips"]
    count = len(clips)
    row_height = min(104, int(620 / max(count, 1)))
    top = 1550 - count * row_height
    label_font = font(min(54, max(38, row_height - 31)))
    number_font = font(min(56, max(40, row_height - 25)))
    ranked_clips = sorted(enumerate(clips), key=lambda pair: int(pair[1].get("rank", count - pair[0])))
    for row, (index, clip) in enumerate(ranked_clips):
        rank = int(clip.get("rank", count - index))
        row_y = top + row * row_height
        seen = index <= active
        current = index == active
        color = "#ffce3b" if current else "white"
        draw.text((74, row_y), f"{rank}.", font=number_font, fill=color,
                  stroke_width=4, stroke_fill="#111116")
        if seen:
            label = str(clip.get("label", ""))[:46].strip() or f"Moment {rank}"
            while draw.textbbox((0, 0), label, font=label_font)[2] > 820 and len(label) > 4:
                label = label[:-2].rstrip() + "…"
            draw.text((157, row_y + 2), label, font=label_font, fill=color,
                      stroke_width=4, stroke_fill="#111116")
    image.save(target)


def has_audio(path):
    result = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)],
                            capture_output=True, text=True, errors="replace")
    return "Audio:" in result.stderr


def probe_duration(path):
    result = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)],
                            capture_output=True, text=True, errors="replace")
    match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not match or "Video:" not in result.stderr:
        raise ValueError("File has no readable video")
    hours, minutes, seconds = match.groups()
    return round(int(hours) * 3600 + int(minutes) * 60 + float(seconds), 2)


def valid_media_name(name):
    return bool(re.fullmatch(r"[a-f0-9]{32}\.(mp4|mov|webm|m4v|mkv)", name))


def valid_audio_name(name):
    return bool(re.fullmatch(r"[a-f0-9]{32}\.(mp3|wav|m4a|aac|ogg|flac)", name))


def run_ffmpeg(args):
    result = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args],
                            capture_output=True, text=True, errors="replace")
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[-1200:] or "FFmpeg failed")


def render(job_id, project):
    work = EXPORTS / job_id
    work.mkdir()
    try:
        clips = project["clips"]
        parts = []
        for index, clip in enumerate(clips):
            source = UPLOADS / clip["id"]
            overlay = work / f"overlay-{index}.png"
            part = work / f"part-{index}.mp4"
            make_overlay(project, index, overlay)
            start = float(clip["start"])
            duration = float(clip["end"]) - start
            visual = (
                "[0:v]fps=30,split=2[bg0][fg0];"
                "[bg0]scale=540:960:force_original_aspect_ratio=increase,"
                "crop=540:960,boxblur=12:1,scale=1080:1920[bg];"
                "[fg0]scale=1080:1120:force_original_aspect_ratio=increase,"
                "crop=1080:1120[fg];"
                "[bg][fg]overlay=0:400[base];"
                "[base][1:v]overlay=0:0:shortest=1,setsar=1[v]"
            )
            keep_clip_sound = not clip.get("muted", not project.get("audio", True))
            audio_map = "0:a:0" if keep_clip_sound and has_audio(source) else "2:a:0"
            args = ["-ss", str(start), "-t", str(duration), "-i", str(source),
                    "-loop", "1", "-i", str(overlay),
                    "-f", "lavfi", "-t", str(duration), "-i", "anullsrc=r=48000:cl=stereo",
                    "-filter_complex", visual, "-map", "[v]", "-map", audio_map,
                    "-t", str(duration), "-r", "30", "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
                    "-movflags", "+faststart", str(part)]
            run_ffmpeg(args)
            parts.append(part)
            with LOCK:
                JOBS[job_id]["progress"] = round((index + 1) / (len(clips) + 1) * 100)
        listing = work / "list.txt"
        listing.write_text("".join(f"file '{part.as_posix()}'\n" for part in parts), encoding="utf-8")
        music = project.get("music")
        output = EXPORTS / f"ranklocal-{datetime.now():%Y%m%d-%H%M%S}-{job_id[:6]}.mp4"
        joined = work / "joined.mp4" if music else output
        run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(listing),
                    "-c", "copy", "-movflags", "+faststart", str(joined)])
        if music:
            volume = float(music["volume"])
            total = sum(float(c["end"]) - float(c["start"]) for c in clips)
            mix = (f"[1:a]volume={volume}[music];"
                   "[0:a][music]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
                   "alimiter=limit=0.95[a]")
            run_ffmpeg(["-i", str(joined), "-stream_loop", "-1", "-i", str(AUDIO / music["id"]),
                        "-filter_complex", mix, "-map", "0:v", "-map", "[a]", "-t", str(total),
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        "-movflags", "+faststart", str(output)])
        with LOCK:
            JOBS[job_id].update(status="done", progress=100, url=f"/exports/{output.name}")
    except Exception as exc:
        with LOCK:
            JOBS[job_id].update(status="error", error=str(exc))
    finally:
        for item in work.glob("*"):
            item.unlink(missing_ok=True)
        work.rmdir()


def validate_project(project):
    if not isinstance(project, dict) or not isinstance(project.get("clips"), list):
        raise ValueError("Invalid project")
    if not 1 <= len(project["clips"]) <= 8:
        raise ValueError("Add 1–8 clips")
    ranks = [int(clip.get("rank", len(project["clips"]) - index))
             for index, clip in enumerate(project["clips"])]
    if sorted(ranks) != list(range(1, len(ranks) + 1)):
        raise ValueError("Ranks must be unique numbers from 1 to clip count")
    for clip in project["clips"]:
        ident = str(clip.get("id", ""))
        if not valid_media_name(ident):
            raise ValueError("Invalid clip")
        if not (UPLOADS / ident).is_file():
            raise ValueError("Clip file missing. Upload it again")
        start, end = float(clip["start"]), float(clip["end"])
        if start < 0 or end <= start:
            raise ValueError("Each clip needs a valid start and end")
        if end > probe_duration(UPLOADS / ident) + 0.1:
            raise ValueError("Trim exceeds source clip length")
    music = project.get("music")
    if music:
        name = music.get("id", "")
        if not valid_audio_name(name) or not (AUDIO / name).is_file():
            raise ValueError("Audio file missing. Add it again")
        volume = float(music.get("volume", 0.3))
        if not 0 <= volume <= 1:
            raise ValueError("Audio volume must be 0–100%")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def json_reply(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def file_reply(self, path, media=False):
        if not path.is_file():
            self.send_error(404)
            return
        size = path.stat().st_size
        start, end = 0, size - 1
        partial = False
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if media and match:
            start = int(match[1]) if match[1] else 0
            end = min(int(match[2]), end) if match[2] else end
            if start > end or start >= size:
                self.send_error(416)
                return
            partial = True
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with path.open("rb") as stream:
            stream.seek(start)
            remaining = end - start + 1
            while remaining:
                chunk = stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/api/health":
            return self.json_reply(200, {"ok": True, "ffmpeg": FFMPEG})
        if path.startswith("/api/jobs/"):
            with LOCK:
                job = JOBS.get(path.removeprefix("/api/jobs/"))
                return self.json_reply(200 if job else 404, job or {"error": "Job not found"})
        if path.startswith("/media/"):
            name = path.removeprefix("/media/")
            if valid_media_name(name):
                return self.file_reply(UPLOADS / name, media=True)
        if path.startswith("/previews/"):
            name = path.removeprefix("/previews/")
            if re.fullmatch(r"[a-f0-9]{32}\.mp4", name):
                return self.file_reply(PREVIEWS / name, media=True)
        if path.startswith("/audio/"):
            name = path.removeprefix("/audio/")
            if valid_audio_name(name):
                return self.file_reply(AUDIO / name, media=True)
        if path.startswith("/exports/"):
            name = path.removeprefix("/exports/")
            if re.fullmatch(r"ranklocal-[a-zA-Z0-9-]+\.mp4", name):
                return self.file_reply(EXPORTS / name, media=True)
        if path == "/":
            path = "/index.html"
        name = path.lstrip("/")
        if name in {"index.html", "style.css", "app.js"}:
            return self.file_reply(STATIC / name)
        self.send_error(404)


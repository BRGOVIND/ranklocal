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



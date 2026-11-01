"""Open RankLocal without relying on Windows URL file associations."""

import os
import subprocess
from pathlib import Path


def open_browser(url="http://127.0.0.1:8765"):
    program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
    program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    candidates = [
        program_files / "Google/Chrome/Application/chrome.exe",
        program_files_x86 / "Google/Chrome/Application/chrome.exe",
        local_app_data / "Google/Chrome/Application/chrome.exe",
        program_files_x86 / "Microsoft/Edge/Application/msedge.exe",
        program_files / "Microsoft/Edge/Application/msedge.exe",
    ]
    for browser in candidates:
        if browser.is_file():
            subprocess.Popen([str(browser), url], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return True
    print(f"Open {url} in Chrome or Edge.")
    return False


if __name__ == "__main__":
    open_browser()

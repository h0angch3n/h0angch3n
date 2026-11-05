"""Chạy như ứng dụng trên PC: khởi động máy chủ cục bộ rồi mở trình duyệt.

Dữ liệu lưu ở thư mục người dùng (Windows: %APPDATA%\\OffsetMES, nơi khác: ~/.offset_mes).
"""
from __future__ import annotations

import os
import threading
import webbrowser
from pathlib import Path

from .server import make_server
from .service import Service

PREFERRED_PORT = 8765


def default_data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".offset_mes")
    folder = Path(base) / "OffsetMES" if os.environ.get("APPDATA") else Path(base)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def default_db_path() -> str:
    return str(default_data_dir() / "offset_mes.db")


def run_desktop(db_path: str | None = None, open_browser: bool = True) -> None:
    service = Service(db_path or default_db_path())
    try:
        httpd = make_server(service, "127.0.0.1", PREFERRED_PORT)
    except OSError:  # cổng bận: lấy cổng trống bất kỳ
        httpd = make_server(service, "127.0.0.1", 0)
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(f"Offset MES đang chạy tại {url}")
    print("Đóng cửa sổ này hoặc nhấn Ctrl+C để thoát.")
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    if open_browser:
        webbrowser.open(url)
    try:
        thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
        httpd.server_close()

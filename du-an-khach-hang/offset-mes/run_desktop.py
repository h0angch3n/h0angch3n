"""Điểm vào cho ứng dụng PC (dùng để đóng gói thành .exe bằng PyInstaller).

    python run_desktop.py                      # mở ứng dụng, tự mở trình duyệt
    OffsetMES.exe create-admin --user admin    # các lệnh dòng lệnh khác: xem docs/HUONG_DAN_SU_DUNG.md
"""
import sys
from pathlib import Path

# Khi đóng gói PyInstaller, mã nguồn nằm trong thư mục tạm _MEIPASS.
ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
sys.path.insert(0, str(ROOT))

from offset_mes.__main__ import main  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) > 1:
        raise SystemExit(main(sys.argv[1:]))
    raise SystemExit(main(["desktop"]))

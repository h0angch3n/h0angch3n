"""Dòng lệnh Offset MES.

    python3 -m offset_mes                      # máy chủ web (mặc định)
    python3 -m offset_mes desktop              # chạy như ứng dụng PC, tự mở trình duyệt
    python3 -m offset_mes create-admin --user admin   # tạo / đặt lại mật khẩu quản trị
"""
import argparse
import getpass
import sys

from . import auth
from .launcher import default_db_path, run_desktop
from .server import serve
from .service import DomainError, Service


def _create_admin(db: str, username: str, password: str | None, full_name: str) -> int:
    service = Service(db)
    if password is None:
        password = getpass.getpass("Mật khẩu quản trị mới: ")
        if password != getpass.getpass("Nhập lại mật khẩu: "):
            print("Hai mật khẩu không khớp.", file=sys.stderr)
            return 1
    try:
        auth.validate_password(password)
        row = service.db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if row:
            service.update_user(row["id"], role="ADMIN", active=True, password=password)
            print(f"Đã đặt lại mật khẩu và quyền ADMIN cho '{username}'.")
        else:
            service.create_user(username, password, full_name, "ADMIN")
            print(f"Đã tạo tài khoản quản trị '{username}'.")
    except (ValueError, DomainError) as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 1
    return 0


def _add_common(p: argparse.ArgumentParser) -> None:
    # SUPPRESS: không ghi đè giá trị đã truyền ở cấp lệnh chính
    p.add_argument("--host", default=argparse.SUPPRESS)
    p.add_argument("--port", type=int, default=argparse.SUPPRESS)
    p.add_argument("--db", default=argparse.SUPPRESS, help="đường dẫn file SQLite")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Phần mềm quản lý xưởng in offset")
    _add_common(parser)
    parser.set_defaults(host="127.0.0.1", port=8000, db=None)
    sub = parser.add_subparsers(dest="command")

    _add_common(sub.add_parser("serve", help="chạy máy chủ web (mặc định)"))
    _add_common(sub.add_parser("desktop", help="chạy như ứng dụng PC và mở trình duyệt"))
    admin = sub.add_parser("create-admin", help="tạo hoặc đặt lại tài khoản quản trị")
    _add_common(admin)
    admin.add_argument("--user", required=True)
    admin.add_argument("--password", default=None, help="bỏ trống để nhập an toàn")
    admin.add_argument("--full-name", default="")

    args = parser.parse_args(argv)
    db = args.db or default_db_path()
    if args.command == "create-admin":
        return _create_admin(db, args.user, args.password, args.full_name)
    if args.command == "desktop":
        run_desktop(args.db)
        return 0
    serve(args.host, args.port, db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

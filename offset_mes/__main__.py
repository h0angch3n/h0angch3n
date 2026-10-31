import argparse

from .server import serve


def main() -> None:
    parser = argparse.ArgumentParser(description="Phần mềm quản lý xưởng in offset")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default="offset_mes.db", help="đường dẫn file SQLite")
    args = parser.parse_args()
    serve(args.host, args.port, args.db)


if __name__ == "__main__":
    main()

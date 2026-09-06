"""CLI: python -m v2_app --camera-index 0"""

from __future__ import annotations

import argparse

from v2_runtime.policy import LOOPBACK_HOST, validate_bind_host

from .server import PORT, serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classroom Mirror V2 teacher app")
    parser.add_argument("--camera-index", type=int)
    parser.add_argument("--host", default=LOOPBACK_HOST, help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    validate_bind_host(args.host)
    serve(
        args.camera_index,
        host=args.host,
        port=args.port,
        open_browser=not args.no_browser,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

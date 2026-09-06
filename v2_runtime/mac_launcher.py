"""macOS launcher for the shared V2 camera slice and loopback service."""

from __future__ import annotations

import argparse

from .camera import (
    CameraUnavailable,
    inventory_cameras,
    smoke_camera,
    validate_camera_index,
)
from .policy import LOOPBACK_HOST, PolicyViolation, validate_bind_host


DEFAULT_PORT = 8470


def _print_inventory(max_index: int):
    cameras = inventory_cameras(max_index=max_index)
    if not cameras:
        print("No camera opened. Check macOS camera permission and device connection.")
        return []
    print("Available cameras (text metadata only):")
    for camera in cameras:
        print(f"  index={camera.index} backend={camera.backend}")
    return cameras


def _choose_camera(max_index: int) -> int:
    cameras = _print_inventory(max_index)
    if not cameras:
        raise CameraUnavailable("No selectable camera is available.")
    raw = input("Enter the USB camera index shown above: ").strip()
    try:
        selected = validate_camera_index(int(raw))
    except (TypeError, ValueError) as exc:
        raise CameraUnavailable("Enter one of the listed integer camera indexes.") from exc
    if selected not in {camera.index for camera in cameras}:
        raise CameraUnavailable(
            f"Camera {selected} was not in the inventory. No fallback was attempted."
        )
    return selected


def create_app(camera_index: int):
    """Create the V2-only local confirmation surface for the selected camera."""
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse

    index = validate_camera_index(camera_index)
    app = FastAPI(title="Classroom Mirror V2 camera slice", docs_url=None, redoc_url=None)

    @app.middleware("http")
    async def local_security_headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.get("/health")
    def health():
        return {"ok": True, "host": LOOPBACK_HOST, "camera_index": index}

    @app.get("/", response_class=HTMLResponse)
    def home():
        return HTMLResponse(
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Classroom Mirror V2</title><style>body{font:18px system-ui;"
            "max-width:46rem;margin:4rem auto;padding:0 1rem;color:#202124}"
            "section{border:1px solid #ccd2d8;border-radius:12px;padding:1.5rem}"
            "code{background:#f1f3f4;padding:.15rem .35rem}</style></head><body>"
            "<main><h1>Classroom Mirror V2</h1><section>"
            "<h2>Camera connection ready</h2>"
            f"<p>Selected camera index: <code>{index}</code></p>"
            "<p>Local teacher-only camera slice. Frames stay in memory and this "
            "page is available only at <code>127.0.0.1</code>.</p>"
            "</section></main></body></html>"
        )

    return app


def serve(camera_index: int | None, *, host: str = LOOPBACK_HOST, port: int = DEFAULT_PORT,
          open_browser: bool = True) -> None:
    from v2_app.server import serve as serve_product
    from v2_app.vision import pose_stack_error

    validate_bind_host(host)
    if not 1024 <= port <= 65535:
        raise ValueError("port must be between 1024 and 65535")
    missing = pose_stack_error()
    if missing:
        raise RuntimeError(missing)
    serve_product(camera_index, host=host, port=port, open_browser=open_browser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classroom Mirror V2 macOS camera runtime")
    parser.add_argument("--camera-index", type=int)
    parser.add_argument("--list-cameras", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--seconds", type=float, default=3.0)
    parser.add_argument("--max-index", type=int, default=5)
    parser.add_argument("--host", default=LOOPBACK_HOST, help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        validate_bind_host(args.host)
        if args.list_cameras:
            return 0 if _print_inventory(args.max_index) else 3
        if args.smoke_test:
            index = (
                validate_camera_index(args.camera_index)
                if args.camera_index is not None
                else _choose_camera(args.max_index)
            )
            result = smoke_camera(index, seconds=args.seconds)
            print(
                "Camera smoke PASS: "
                f"index={result.camera_index} backend={result.backend} "
                f"frames={result.frame_count} elapsed={result.elapsed_seconds:.2f}s "
                f"host={LOOPBACK_HOST} frame_writes=0"
            )
            return 0
        index = (
            validate_camera_index(args.camera_index)
            if args.camera_index is not None
            else None
        )
        print(f"Teacher-only dashboard: http://{LOOPBACK_HOST}:{args.port}")
        serve(index, host=args.host, port=args.port, open_browser=not args.no_browser)
        return 0
    except CameraUnavailable as exc:
        print(f"Camera runtime FAIL: {exc}")
        print(
            "macOS camera access: open System Settings > Privacy & Security > "
            "Camera, enable Terminal, then quit and reopen Terminal."
        )
        return 2
    except (PolicyViolation, ValueError, RuntimeError) as exc:
        print(f"Camera runtime FAIL: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

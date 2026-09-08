"""Windows launcher for the shared V2 camera slice and loopback service."""

from __future__ import annotations

import argparse
import sys
import threading
import time

from .camera import (
    CameraBusy,
    CameraPermissionDenied,
    CameraUnavailable,
    inventory_cameras,
    smoke_camera,
    validate_camera_index,
)
from .policy import LOOPBACK_HOST, PolicyViolation, RuntimeFilePolicy, RuntimeNetworkPolicy, validate_bind_host


DEFAULT_PORT = 8470
_SERVICE_START_TIMEOUT = 5.0
_SERVICE_STOP_TIMEOUT = 5.0

EXIT_USAGE = 2
EXIT_POLICY = 3
EXIT_CAMERA_DENIED = 4
EXIT_CAMERA_BUSY = 5
EXIT_CAMERA_ABSENT = 6
EXIT_SERVICE_FAILED = 7


def create_app(camera_index: int):
    """Create the V2-only local confirmation surface for the selected camera."""
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse

    index = validate_camera_index(camera_index)
    app = FastAPI(title="Classroom Mirror V2 Windows camera slice", docs_url=None, redoc_url=None)

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


def _run_bounded_service(camera_index: int, host: str, port: int) -> dict:
    """Start the loopback service, confirm health over a real request, then stop it."""
    import json
    import urllib.request

    import uvicorn

    validate_bind_host(host)
    config = uvicorn.Config(create_app(camera_index), host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + _SERVICE_START_TIMEOUT
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        if not server.started:
            raise RuntimeError("loopback service did not start within the bounded window")

        with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=2.0) as response:
            return json.loads(response.read().decode("utf-8"))
    finally:
        server.should_exit = True
        thread.join(timeout=_SERVICE_STOP_TIMEOUT)


def _diagnose_camera_failure(camera_index: int, error: CameraUnavailable, max_index: int) -> tuple[str, int]:
    """Translate a camera failure into a distinct plain-language diagnostic."""
    if isinstance(error, CameraPermissionDenied):
        return (
            f"Camera {camera_index} access was denied by Windows. Open Settings > "
            "Privacy & security > Camera (ms-settings:privacy-webcam), allow "
            "desktop apps to use the camera, then try again. No fallback camera "
            "was attempted.",
            EXIT_CAMERA_DENIED,
        )
    if isinstance(error, CameraBusy):
        return (
            f"Camera {camera_index} is present but appears to be in use by "
            "another application. Close other apps using the camera and try "
            "again. No fallback camera was attempted.",
            EXIT_CAMERA_BUSY,
        )

    try:
        present = {camera.index for camera in inventory_cameras(max_index=max_index)}
    except Exception:
        present = set()
    if camera_index in present:
        return (
            f"Camera {camera_index} was listed but could not be opened. It may "
            "be in use by another application. No fallback camera was "
            "attempted.",
            EXIT_CAMERA_BUSY,
        )
    return (
        f"Camera {camera_index} was not found. Check that it is plugged in and "
        "selected correctly, then try again. No fallback camera was attempted.",
        EXIT_CAMERA_ABSENT,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classroom Mirror V2 Windows launcher")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--camera-index", type=int)
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--max-index", type=int, default=5, help=argparse.SUPPRESS)
    parser.add_argument("--host", default=LOOPBACK_HOST, help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=argparse.SUPPRESS)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if not args.smoke_test:
        print("Refused: this launcher currently supports only --smoke-test.", file=sys.stderr)
        return EXIT_USAGE
    if args.camera_index is None or args.camera_index < 0:
        print("Refused: --camera-index must be a non-negative enumerated index.", file=sys.stderr)
        return EXIT_USAGE
    if args.seconds <= 0:
        print("Refused: --seconds must be greater than zero.", file=sys.stderr)
        return EXIT_USAGE

    try:
        validate_bind_host(args.host)
        files = RuntimeFilePolicy()
        index = validate_camera_index(args.camera_index)
    except (PolicyViolation, ValueError) as exc:
        print(f"Runtime policy error: {exc}", file=sys.stderr)
        return EXIT_POLICY

    network = RuntimeNetworkPolicy()

    try:
        result = smoke_camera(index, seconds=args.seconds)
    except CameraUnavailable as exc:
        message, code = _diagnose_camera_failure(index, exc, args.max_index)
        print(f"Camera runtime FAIL: {message}", file=sys.stderr)
        return code

    print(f"Selected camera index: {result.camera_index}")
    print(f"Camera backend: {result.backend}")
    print(f"Frames read in memory: {result.frame_count}")
    print("Service bind policy: 127.0.0.1 only")
    print(f"Runtime data policy root: %LOCALAPPDATA%\\{files.root.name}")
    print(f"Outbound connection attempts: {len(network.outbound_attempts)}")

    try:
        health = _run_bounded_service(index, args.host, args.port)
    except (OSError, RuntimeError) as exc:
        print(f"Loopback service FAIL: {exc}", file=sys.stderr)
        return EXIT_SERVICE_FAILED

    print(f"Loopback health check: {health}")
    print(
        "Camera smoke PASS: "
        f"index={result.camera_index} backend={result.backend} "
        f"frames={result.frame_count} elapsed={result.elapsed_seconds:.2f}s "
        f"host={args.host} frame_writes=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

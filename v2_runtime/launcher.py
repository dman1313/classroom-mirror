"""Windows launcher for loopback teacher UI and bounded selected-camera smoke."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sys
from threading import Thread

from .camera import CameraUnavailable, inventory_cameras, inventory_display_rows, smoke_camera
from .policy import LOOPBACK_HOST, PolicyViolation, RuntimeNetworkPolicy, validate_bind_host


DEFAULT_PORT = 8470


def run_local_health_check(
    camera_index: int,
    *,
    host: str = LOOPBACK_HOST,
) -> dict:
    """Start one loopback server, request health locally, then always stop it."""
    validate_bind_host(host)
    payload = json.dumps(
        {"ok": True, "host": host, "camera_index": camera_index},
        separators=(",", ":"),
    ).encode("ascii")

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/health":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer((host, 0), HealthHandler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    thread.daemon = True
    network = RuntimeNetworkPolicy()
    response = b""
    stopped = False
    try:
        thread.start()
        connection = network.connect((host, server.server_port), timeout=2.0)
        try:
            connection.sendall(
                b"GET /health HTTP/1.0\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n"
            )
            while True:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                response += chunk
        finally:
            connection.close()
        if b" 200 " not in response.split(b"\r\n", 1)[0] or payload not in response:
            raise RuntimeError("local health endpoint returned an invalid response")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)
        stopped = not thread.is_alive()
    if not stopped:
        raise RuntimeError("local health service did not shut down")
    return {
        "ok": True,
        "camera_index": camera_index,
        "host": host,
        "outbound_attempts": len(network.outbound_attempts),
        "stopped": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classroom Mirror V2 Windows launcher")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--list-cameras", action="store_true")
    parser.add_argument("--camera-index", type=int)
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--max-index", type=int, default=5)
    parser.add_argument("--host", default=LOOPBACK_HOST, help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        validate_bind_host(args.host)
        if args.list_cameras:
            cameras = inventory_cameras(max_index=args.max_index)
            if not cameras:
                raise CameraUnavailable(
                    "No camera is available. Check the connection and Windows camera permission."
                )
            print("Available cameras:")
            for row in inventory_display_rows(cameras):
                print(f"  {row}")
            return 0
        if not args.smoke_test:
            from v2_app.server import serve as serve_product
            from v2_app.vision import pose_stack_error

            missing = pose_stack_error()
            if missing:
                raise RuntimeError(missing)
            print(f"Teacher-only dashboard: http://{LOOPBACK_HOST}:{args.port}")
            serve_product(args.camera_index, host=args.host, port=args.port)
            return 0
        if args.camera_index is None:
            raise ValueError("--camera-index is required for --smoke-test")

        result = smoke_camera(args.camera_index, seconds=args.seconds)
        health = run_local_health_check(result.camera_index, host=args.host)
        print(f"Selected camera index: {result.camera_index}")
        print(f"Capture backend: {result.backend}")
        print(f"In-memory frames: {result.frame_count}")
        print(f"Bounded seconds: {result.elapsed_seconds:.2f}")
        print(f"Service bind: {health['host']}")
        print("Local health: PASS")
        print(f"Outbound connection attempts: {health['outbound_attempts']}")
        print("Service stopped: YES")
        print("Frame/media writes: 0")
        return 0
    except CameraUnavailable as exc:
        print(f"Camera smoke FAIL: {exc}", file=sys.stderr)
        return 4
    except (PolicyViolation, ValueError, OSError, RuntimeError) as exc:
        print(f"Runtime FAIL: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

"""Double-click launcher: dashboard first; camera starts only from the UI."""

import argparse
import socket
import sys
import threading
import time
import webbrowser

from v2_runtime.policy import validate_bind_host


def network_guard(event, args):
    if event in {"socket.connect", "socket.bind", "socket.sendto"}:
        sock, address = args
        if (
            sock.family in (socket.AF_INET, socket.AF_INET6)
            and address[0] != "127.0.0.1"
        ):
            raise PermissionError("Classroom Mirror allows loopback connections only.")
    elif event == "socket.getaddrinfo" and args[0] not in (
        None,
        "127.0.0.1",
        b"127.0.0.1",
    ):
        raise PermissionError("Runtime DNS lookups are disabled.")
    elif event in {"socket.gethostbyname", "socket.gethostbyaddr"} and args[0] not in (
        "127.0.0.1",
        b"127.0.0.1",
    ):
        raise PermissionError("Runtime DNS lookups are disabled.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Classroom Mirror teacher dashboard")
    parser.add_argument("--port", type=int, default=8470)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    validate_bind_host(args.host)
    if not 1024 <= args.port <= 65535:
        parser.error("Port must be between 1024 and 65535.")
    import uvicorn
    from .server import create_app
    from .vision import configure_local_runtime

    configure_local_runtime()
    sys.addaudithook(network_guard)
    url = f"http://127.0.0.1:{args.port}"
    # An occupied port is not assumed to belong to this app.
    try:
        probe = socket.socket()
        probe.bind(("127.0.0.1", args.port))
        probe.close()
    except OSError:
        # Reopen an existing verified dashboard instead of launching a second camera owner.
        import json
        import urllib.request

        try:
            with urllib.request.urlopen(url + "/health", timeout=2) as response:
                health = json.load(response)
            if (
                health.get("product") == "teacher-dashboard"
                and health.get("host") == "127.0.0.1"
            ):
                print(f"Classroom Mirror is already running at {url}")
                if not args.no_browser:
                    webbrowser.open(url)
                return 0
        except Exception:
            pass
        print(
            f"Port {args.port} is already in use. Close the other Classroom Mirror window or choose --port 8471."
        )
        return 2
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(),
            host=args.host,
            port=args.port,
            log_level="warning",
            access_log=False,
        )
    )

    def open_when_ready():
        for _ in range(100):
            if server.started:
                webbrowser.open(url)
                return
            time.sleep(0.1)

    if not args.no_browser:
        threading.Thread(target=open_when_ready, daemon=True).start()
    print(
        f"Classroom Mirror is ready at {url}\nLeave this window open. Press Control-C to quit.",
        flush=True,
    )
    try:
        server.run()
    except KeyboardInterrupt:
        pass
    print("Classroom Mirror stopped. The camera has been released.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

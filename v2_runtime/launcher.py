"""Windows launcher foundation; the real-camera smoke lands in the next slice."""

from __future__ import annotations

import argparse
import sys

from .policy import PolicyViolation, RuntimeFilePolicy, RuntimeNetworkPolicy, validate_bind_host


CAMERA_INCREMENT_REQUIRED = 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classroom Mirror V2 Windows launcher")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--camera-index", type=int)
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--host", default="127.0.0.1", help=argparse.SUPPRESS)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if not args.smoke_test:
        print("Refused: this launcher currently supports only --smoke-test.", file=sys.stderr)
        return 2
    if args.camera_index is None or args.camera_index < 0:
        print("Refused: --camera-index must be a non-negative enumerated index.", file=sys.stderr)
        return 2
    if args.seconds <= 0:
        print("Refused: --seconds must be greater than zero.", file=sys.stderr)
        return 2

    try:
        validate_bind_host(args.host)
        files = RuntimeFilePolicy()
    except PolicyViolation as exc:
        print(f"Runtime policy error: {exc}", file=sys.stderr)
        return 3

    network = RuntimeNetworkPolicy()
    print(f"Selected camera index: {args.camera_index}")
    print(f"Requested bounded smoke seconds: {args.seconds:g}")
    print("Service bind policy: 127.0.0.1 only")
    print(f"Runtime data policy root: %LOCALAPPDATA%\\{files.root.name}")
    print(f"Outbound connection attempts: {len(network.outbound_attempts)}")
    print(
        "NOT RUN: physical-camera open/read/release is owned by the next T1 increment.",
        file=sys.stderr,
    )
    return CAMERA_INCREMENT_REQUIRED


if __name__ == "__main__":
    raise SystemExit(main())

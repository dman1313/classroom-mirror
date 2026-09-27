"""Install-time-only model fetch from the upstream release, with checksum."""

import hashlib
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n-pose.pt"
SHA256 = "869e83fcdffdc7371fa4e34cd8e51c838cc729571d1635e5141e3075e9319dc0"


def main():
    target = ROOT / "yolo11n-pose.pt"
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == SHA256:
        print("Local pose model verified.")
        return
    pending = ROOT / "yolo11n-pose.pt.download"
    print("Downloading the local pose model from its official release (about 6 MB)…")
    try:
        with urllib.request.urlopen(URL, timeout=60) as response:
            data = response.read(10 * 1024 * 1024)
        if hashlib.sha256(data).hexdigest() != SHA256:
            raise RuntimeError(
                "The model checksum did not match. Nothing was installed."
            )
        pending.write_bytes(data)
        pending.replace(target)
    finally:
        pending.unlink(missing_ok=True)
    print("Local pose model installed and verified.")


if __name__ == "__main__":
    main()

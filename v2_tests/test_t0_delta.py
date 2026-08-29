"""T0 checks that keep the V2 handoff honest before runtime work starts."""

from hashlib import sha256
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SIGNED_V1_CONTRACT_SHA256 = (
    "512212808758c2a82b8e14e5a776d7fcc8526e7ed5720e9dd6565c47398ca4b9"
)


class V2DeltaReadinessTests(unittest.TestCase):
    def test_signed_v1_contract_is_preserved_verbatim(self):
        contract = (ROOT / "CONTRACT.md").read_bytes()
        self.assertEqual(sha256(contract).hexdigest(), SIGNED_V1_CONTRACT_SHA256)

    def test_delta_names_the_contract_conflict_and_successor_command(self):
        delta = (ROOT / "V2-DELTA.md").read_text(encoding="utf-8")
        required = (
            "V1 criterion 2",
            "anonymous sticky face numbers",
            "python check-v2.py --stage t0",
            "python check-v2.py --stage t1 --camera-index",
            "No V2 runtime test may be skipped",
        )
        for text in required:
            with self.subTest(text=text):
                self.assertIn(text, delta)

    def test_windows_smoke_is_adult_only_and_checks_no_frame_writes(self):
        smoke = (ROOT / "WINDOWS-V2-SMOKE.md").read_text(encoding="utf-8")
        required = (
            "adult beta only",
            "USB webcam",
            "without administrator rights",
            "No image or video files",
            "127.0.0.1",
            "powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\install.ps1 -CheckOnly",
            ".\\run.bat --smoke-test --camera-index",
        )
        for text in required:
            with self.subTest(text=text):
                self.assertIn(text, smoke)


if __name__ == "__main__":
    unittest.main()

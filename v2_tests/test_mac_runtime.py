"""V2 macOS camera/runtime acceptance tests that do not need real hardware."""

from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class FakeCapture:
    def __init__(self, index, opened=True, frames=None, backend="FAKE"):
        self.index = index
        self._opened = opened
        self._frames = list(frames or ())
        self._backend = backend
        self.released = False

    def isOpened(self):
        return self._opened

    def read(self):
        if not self._frames:
            return False, None
        return self._frames.pop(0)

    def getBackendName(self):
        return self._backend

    def release(self):
        self.released = True


class FakeCaptureFactory:
    def __init__(self, cameras):
        self.cameras = cameras
        self.opened_indexes = []
        self.instances = []

    def __call__(self, index):
        self.opened_indexes.append(index)
        settings = self.cameras.get(index, {})
        capture = FakeCapture(index=index, **settings)
        self.instances.append(capture)
        return capture


class V2SharedCameraRuntimeTests(unittest.TestCase):
    def test_inventory_lists_open_devices_and_releases_every_probe(self):
        from v2_runtime.camera import inventory_cameras

        factory = FakeCaptureFactory(
            {
                0: {"opened": True, "backend": "BUILT-IN"},
                1: {"opened": False},
                2: {"opened": True, "backend": "USB"},
            }
        )

        cameras = inventory_cameras(max_index=2, capture_factory=factory)

        self.assertEqual([camera.index for camera in cameras], [0, 2])
        self.assertEqual([camera.backend for camera in cameras], ["BUILT-IN", "USB"])
        self.assertTrue(all(capture.released for capture in factory.instances))

    def test_smoke_opens_only_the_selected_non_default_camera(self):
        from v2_runtime.camera import smoke_camera

        frame = object()
        factory = FakeCaptureFactory(
            {2: {"opened": True, "frames": [(True, frame)], "backend": "USB"}}
        )
        times = iter((0.0, 0.0, 0.2))

        result = smoke_camera(
            2,
            seconds=0.1,
            capture_factory=factory,
            clock=lambda: next(times),
            sleeper=lambda _: None,
        )

        self.assertEqual(factory.opened_indexes, [2])
        self.assertEqual(result.camera_index, 2)
        self.assertEqual(result.backend, "USB")
        self.assertEqual(result.frame_count, 1)
        self.assertTrue(factory.instances[0].released)

    def test_smoke_releases_camera_when_frame_read_fails(self):
        from v2_runtime.camera import CameraUnavailable, smoke_camera

        factory = FakeCaptureFactory({3: {"opened": True, "frames": []}})
        times = iter((0.0, 0.0))

        with self.assertRaisesRegex(CameraUnavailable, "stopped sending frames"):
            smoke_camera(
                3,
                seconds=0.1,
                capture_factory=factory,
                clock=lambda: next(times),
                sleeper=lambda _: None,
            )

        self.assertTrue(factory.instances[0].released)

    def test_invalid_camera_indexes_fail_closed(self):
        from v2_runtime.camera import validate_camera_index

        for value in (-1, 10, True, "1"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_camera_index(value)

    def test_service_accepts_only_ipv4_loopback(self):
        from v2_runtime.policy import validate_bind_host

        self.assertEqual(validate_bind_host("127.0.0.1"), "127.0.0.1")
        for host in ("0.0.0.0", "::", "localhost", "192.168.1.20"):
            with self.subTest(host=host):
                with self.assertRaises(ValueError):
                    validate_bind_host(host)

    def test_shared_v2_runtime_has_no_frame_write_or_encoding_api(self):
        source = (ROOT / "v2_runtime" / "camera.py").read_text(encoding="utf-8")
        for forbidden in ("imwrite", "VideoWriter", "imencode"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


class MacLauncherContractTests(unittest.TestCase):
    def test_mac_launchers_enter_shared_v2_runtime_not_v1(self):
        installer = (ROOT / "install-v2-mac.sh").read_text(encoding="utf-8")
        launcher = (ROOT / "run-v2.command").read_text(encoding="utf-8")

        self.assertIn(".venv-mac-v2", installer)
        self.assertIn("python3.11", installer)
        self.assertIn("v2_runtime.mac_launcher", launcher)
        self.assertIn(".venv-mac-v2", launcher)
        self.assertNotIn("app.main", launcher)

    def test_mac_smoke_document_names_privacy_and_hardware_outcomes(self):
        smoke = (ROOT / "MAC-V2-SMOKE.md").read_text(encoding="utf-8")
        required = (
            "adult beta only",
            "Privacy & Security > Camera",
            "USB camera",
            "built-in camera",
            "127.0.0.1",
            "No image or video files",
            "PASS",
            "FAIL",
            "NOT RUN",
        )
        for text in required:
            with self.subTest(text=text):
                self.assertIn(text, smoke)

    def test_mac_camera_denial_prints_exact_permission_guidance(self):
        from v2_runtime.camera import CameraUnavailable
        from v2_runtime.mac_launcher import main

        output = StringIO()
        with patch(
            "v2_runtime.mac_launcher.smoke_camera",
            side_effect=CameraUnavailable("selected camera denied; no fallback"),
        ), redirect_stdout(output):
            result = main(
                ["--smoke-test", "--camera-index", "2", "--seconds", "1"]
            )

        self.assertEqual(result, 2)
        self.assertIn("System Settings > Privacy & Security > Camera", output.getvalue())
        self.assertIn("no fallback", output.getvalue())


if __name__ == "__main__":
    unittest.main()

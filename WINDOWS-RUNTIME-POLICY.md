# Windows V2 runtime policy

This policy applies to the V2 launcher and runtime. The historical V1 app is
not a V2 launch path. The current teacher product path on macOS is documented
in [SDD-DASHBOARD.md](SDD-DASHBOARD.md) and [README.md](README.md).

## Network boundary

- The service bind host is exactly `127.0.0.1`.
- Wildcard, LAN, hostname, IPv6-any, and alternate loopback binds are refused.
- Runtime connection requests pass through `RuntimeNetworkPolicy`, which
  rejects any destination other than `127.0.0.1` before calling the socket
  connector. Runtime dependency download, telemetry, update, DNS, and cloud
  requests are prohibited.

## File boundary

The runtime root is `%LOCALAPPDATA%\ClassroomMirror`. Absolute paths, traversal,
symlink escapes, and every path not listed below are refused before opening a
file. These are the complete non-media write paths:

- `state/classroom-mirror.sqlite3`
- `state/classroom-mirror.sqlite3-journal`
- `state/classroom-mirror.sqlite3-wal`
- `state/classroom-mirror.sqlite3-shm`
- `logs/runtime.log`
- `config/runtime.json`

Image, video, crop, screenshot, audio, encoded-frame, model-download, repo,
temporary-directory, Desktop, roaming-profile, and machine-wide writes are not
allowed. The T1 camera-slice launcher does not create even the allowlisted
files; this list is the boundary for later V2 components.

## Launcher status

`run.bat --smoke-test --camera-index <n> --seconds <n>` opens the explicitly
selected camera, reads frames in memory only, starts a loopback-only health
service, and shuts down cleanly. Hardware-dependent acceptance tests are marked
`@pytest.mark.camera` and fail closed without a real selected device. Real
Windows 10/11 x64 + USB webcam smoke remains documented in
[WINDOWS-V2-SMOKE.md](WINDOWS-V2-SMOKE.md). The first beta product path is the
macOS teacher dashboard; Windows remains a planned next target.

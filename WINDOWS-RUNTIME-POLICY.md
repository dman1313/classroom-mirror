# Windows V2 runtime policy

This policy applies to the V2 launcher and runtime. The historical V1 app is
not a V2 launch path.

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
- `state/identities.bin`
- `logs/runtime.log`
- `config/runtime.json`
- `config/template.key`

Image, video, crop, screenshot, audio, encoded-frame, model-download, repo,
temporary-directory, Desktop, roaming-profile, and machine-wide writes are not
allowed. Anonymous templates live in `state/identities.bin`. On Windows they
are sealed with current-user DPAPI and `config/template.key` is not created.
On macOS/Linux the HMAC wrap key is `config/template.key` (mode 600).

## Launcher status

`run.bat --smoke-test --camera-index <n> --seconds <n>` opens the selected
camera, reads bounded in-memory frames, checks a loopback health endpoint, and
exits. `run.bat` with no smoke flags starts the teacher-only V2 dashboard
(`v2_app`) on `127.0.0.1:8470`.

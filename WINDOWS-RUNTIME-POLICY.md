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
- `logs/runtime.log`
- `config/runtime.json`

Image, video, crop, screenshot, audio, encoded-frame, model-download, repo,
temporary-directory, Desktop, roaming-profile, and machine-wide writes are not
allowed. The T1a launcher does not create even the allowlisted files; this list
is the boundary for later V2 components.

## Launcher status

`run.bat --smoke-test --camera-index <n> --seconds <n>` validates arguments and
the runtime policy. It returns a nonzero `NOT RUN` result because physical
camera open/read/release and loopback health startup belong to the following
camera increment. It must not be recorded as a real-camera PASS.

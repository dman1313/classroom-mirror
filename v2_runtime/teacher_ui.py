"""Teacher-only setup and capture controls for the local V2 camera slice."""

from __future__ import annotations

from threading import RLock
from typing import Iterable

from .camera import (
    CameraUnavailable,
    Capture,
    CaptureFactory,
    inventory_cameras,
    inventory_display_rows,
    open_camera,
    read_memory_frame,
    validate_camera_index,
)
from .policy import LOOPBACK_HOST, validate_bind_host


class TeacherCaptureSession:
    """Own one explicit capture and retain preview pixels only in process RAM."""

    def __init__(self, *, capture_factory: CaptureFactory | None = None):
        self._capture_factory = capture_factory
        self._inventory_indexes: set[int] = set()
        self._selected_index: int | None = None
        self._capture: Capture | None = None
        self._preview_frame = None
        self._active = False
        self._teacher_ui_visible = True
        self._lock = RLock()

    @property
    def selected_index(self) -> int | None:
        return self._selected_index

    @property
    def preview_frame(self):
        return self._preview_frame

    @property
    def active(self) -> bool:
        return self._active

    @property
    def teacher_ui_visible(self) -> bool:
        return self._teacher_ui_visible

    def set_inventory_indexes(self, indexes: Iterable[int]) -> None:
        validated = {validate_camera_index(index) for index in indexes}
        with self._lock:
            if self._selected_index not in validated:
                self.stop()
                self._selected_index = None
            self._inventory_indexes = validated

    def refresh_inventory(self, *, max_index: int = 5):
        cameras = inventory_cameras(
            max_index=max_index,
            capture_factory=self._capture_factory,
        )
        self.set_inventory_indexes(camera.index for camera in cameras)
        return tuple(
            {"index": camera.index, "display": display}
            for camera, display in zip(cameras, inventory_display_rows(cameras))
        )

    def select_camera(self, camera_index: int) -> None:
        index = validate_camera_index(camera_index)
        with self._lock:
            if index not in self._inventory_indexes:
                raise CameraUnavailable(
                    f"Camera {index} is not in the current inventory. Refresh the "
                    "list and select a displayed camera; no fallback was attempted."
                )
            if index != self._selected_index:
                self.stop()
                self._selected_index = index

    def _ensure_capture(self) -> Capture:
        if self._selected_index is None:
            raise CameraUnavailable("Select a displayed camera before preview or Start.")
        if self._capture is None:
            self._capture = open_camera(
                self._selected_index,
                capture_factory=self._capture_factory,
            )
        return self._capture

    def read_setup_preview(self):
        with self._lock:
            capture = self._ensure_capture()
            try:
                self._preview_frame = read_memory_frame(capture, self._selected_index)
                return self._preview_frame
            except Exception:
                self.stop()
                raise

    def start(self) -> None:
        with self._lock:
            self._ensure_capture()
            self._active = True

    def stop(self) -> None:
        with self._lock:
            capture, self._capture = self._capture, None
            self._active = False
            self._preview_frame = None
            if capture is not None:
                capture.release()

    def hide(self) -> None:
        with self._lock:
            self._teacher_ui_visible = False

    def show(self) -> None:
        with self._lock:
            self._teacher_ui_visible = True

    def close(self) -> None:
        self.stop()


def render_teacher_page() -> str:
    """Return the private local control surface; it contains no identity input."""
    return """<!doctype html>
<html><head><meta charset="utf-8"><title>Classroom Mirror camera setup</title>
<style>
body{font:16px system-ui;max-width:54rem;margin:2rem auto;padding:0 1rem;color:#17202a}
button,select{font:inherit;margin:.25rem;padding:.55rem}.panel{border:1px solid #ccd2d8;border-radius:12px;padding:1rem}
#setup-preview{display:block;max-width:100%;min-height:12rem;background:#111;margin:1rem 0}
#show-ui{position:fixed;right:1rem;bottom:1rem}
</style></head><body>
<button id="show-ui" hidden>Show teacher controls</button>
<main id="teacher-ui" class="panel">
<h1>Private camera setup</h1><p>Local at 127.0.0.1. Preview frames stay in memory.</p>
<label for="camera-select">Camera</label><select id="camera-select"></select>
<button id="refresh-cameras">Refresh cameras</button>
<img id="setup-preview" alt="Selected camera setup preview">
<button id="preview-camera">Preview</button><button id="start-session">Start</button>
<button id="stop-session">Stop</button><button id="hide-ui">Hide teacher controls</button>
<p id="status" role="status">Choose a camera, then preview.</p>
</main><script>
const ui=document.getElementById('teacher-ui'),show=document.getElementById('show-ui');
const status=document.getElementById('status'),picker=document.getElementById('camera-select');
async function call(path,method='POST'){const r=await fetch(path,{method,cache:'no-store'});const j=await r.json();if(!r.ok)throw Error(j.detail||'Camera action failed');return j}
async function refresh(){const rows=await call('/api/cameras','GET');picker.replaceChildren(...rows.map(x=>new Option(x.display,x.index)));status.textContent=rows.length?'Select a camera.':'No camera is available.'}
async function select(){await call('/api/cameras/'+picker.value+'/select')}
document.getElementById('refresh-cameras').onclick=()=>refresh().catch(e=>status.textContent=e.message);
document.getElementById('preview-camera').onclick=async()=>{try{await select();document.getElementById('setup-preview').src='/api/preview?tick='+Date.now();status.textContent='Setup preview ready.'}catch(e){status.textContent=e.message}};
document.getElementById('start-session').onclick=async()=>{try{await select();await call('/api/session/start');status.textContent='Local session running.'}catch(e){status.textContent=e.message}};
document.getElementById('stop-session').onclick=()=>call('/api/session/stop').then(()=>status.textContent='Session stopped.').catch(e=>status.textContent=e.message);
document.getElementById('hide-ui').onclick=()=>{ui.hidden=true;show.hidden=false;call('/api/ui/hide').catch(()=>{})};
show.onclick=()=>{ui.hidden=false;show.hidden=true;call('/api/ui/show').catch(()=>{})};refresh().catch(e=>status.textContent=e.message);
</script></body></html>"""


def create_teacher_app(*, capture_factory: CaptureFactory | None = None):
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, Response

    session = TeacherCaptureSession(capture_factory=capture_factory)
    app = FastAPI(title="Classroom Mirror camera setup", docs_url=None, redoc_url=None)
    app.state.capture_session = session

    @app.middleware("http")
    async def private_headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self'; style-src 'unsafe-inline'; "
            "script-src 'unsafe-inline'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    def camera_action(action):
        try:
            return action()
        except (CameraUnavailable, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/health")
    def health():
        return {"ok": True, "host": LOOPBACK_HOST}

    @app.get("/", response_class=HTMLResponse)
    def home():
        return HTMLResponse(render_teacher_page())

    @app.get("/api/cameras")
    def cameras():
        return camera_action(session.refresh_inventory)

    @app.post("/api/cameras/{camera_index}/select")
    def select(camera_index: int):
        camera_action(lambda: session.select_camera(camera_index))
        return {"ok": True, "camera_index": camera_index}

    @app.get("/api/preview")
    def preview():
        frame = camera_action(session.read_setup_preview)
        import cv2

        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            raise HTTPException(status_code=500, detail="Setup preview could not be encoded in memory.")
        return Response(content=encoded.tobytes(), media_type="image/jpeg")

    @app.post("/api/session/start")
    def start():
        camera_action(session.start)
        return {"ok": True, "active": True}

    @app.post("/api/session/stop")
    def stop():
        session.stop()
        return {"ok": True, "active": False}

    @app.post("/api/ui/hide")
    def hide():
        session.hide()
        return {"ok": True, "visible": False}

    @app.post("/api/ui/show")
    def show():
        session.show()
        return {"ok": True, "visible": True}

    return app


def serve_teacher_ui(*, host: str = LOOPBACK_HOST, port: int = 8470) -> None:
    import uvicorn

    validate_bind_host(host)
    if not 1024 <= port <= 65535:
        raise ValueError("port must be between 1024 and 65535")
    uvicorn.run(create_teacher_app(), host=host, port=port, log_level="warning")

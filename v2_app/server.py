"""Local teacher-only V2 service. Binds 127.0.0.1 only."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import time

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from v2_runtime.camera import inventory_cameras
from v2_runtime.policy import LOOPBACK_HOST, validate_bind_host

from .capture import CaptureLoop
from .engine import SessionEngine
from .store import Store
from . import ui

HOST, PORT = LOOPBACK_HOST, 8470
PREVIEW_BOUNDARY = "cmv2frame"


class AppState:
    def __init__(self, camera_index: int | None = None):
        self.store = Store()
        self.preset_camera = camera_index
        self.engine: SessionEngine | None = None
        self.loop: CaptureLoop | None = None
        self.session_id: int | None = None
        self.last_recap: dict | None = None
        self.error: str | None = None


def create_app(camera_index: int | None = None) -> FastAPI:
    state = AppState(camera_index)
    app = FastAPI(title="Classroom Mirror V2", docs_url=None, redoc_url=None)

    @app.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self'; style-src 'unsafe-inline'; "
            "script-src 'unsafe-inline'"
        )
        return response

    @app.get("/health")
    def health():
        return {"ok": True, "host": HOST, "product": "v2"}

    @app.get("/", response_class=HTMLResponse)
    def home():
        cameras = [{"index": c.index, "backend": c.backend} for c in inventory_cameras()]
        if state.preset_camera is not None and not any(
            c["index"] == state.preset_camera for c in cameras
        ):
            cameras.insert(0, {"index": state.preset_camera, "backend": "selected"})
        return ui.setup_page(cameras, state.error)

    @app.get("/live", response_class=HTMLResponse)
    def live():
        if state.engine is None:
            return HTMLResponse(ui.setup_page([], "Start a class first."), status_code=400)
        return ui.live_page()

    @app.get("/recap", response_class=HTMLResponse)
    def recap_view():
        return ui.recap_page()

    @app.get("/api/state")
    def api_state():
        if state.engine is None:
            return JSONResponse({"error": "not running"}, status_code=400)
        snap = state.engine.snapshot()
        if state.loop and state.loop.error:
            snap["error"] = state.loop.error
        return snap

    @app.get("/api/preview")
    def api_preview():
        # Teacher-only live view. Available only while a class loop is running.
        if state.engine is None or state.loop is None:
            return JSONResponse({"error": "not running"}, status_code=400)

        boundary = PREVIEW_BOUNDARY.encode()

        def frames():
            while state.engine is not None and state.loop is not None:
                loop = state.loop
                jpeg = loop.latest_jpeg() if loop else None
                if jpeg:
                    yield (
                        b"--" + boundary + b"\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n"
                        + jpeg + b"\r\n"
                    )
                time.sleep(0.1)

        return StreamingResponse(
            frames(),
            media_type=f"multipart/x-mixed-replace; boundary={PREVIEW_BOUNDARY}",
        )

    @app.get("/api/recap")
    def api_recap():
        if state.last_recap is None:
            return JSONResponse({"error": "no recap yet"}, status_code=400)
        return state.last_recap

    @app.post("/api/start")
    async def api_start(request: Request):
        if state.engine is not None:
            return JSONResponse({"error": "A class is already running."}, status_code=400)
        try:
            payload = await request.json()
            index = int(payload.get("camera_index"))
            sensitivity = str(payload.get("sensitivity") or "low")
            engine = SessionEngine(state.store.book, sensitivity)
        except (TypeError, ValueError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        loop = CaptureLoop(engine, index)
        state.engine = engine
        state.loop = loop
        state.last_recap = None
        state.session_id = state.store.record_session(
            datetime.now(timezone.utc).isoformat(), engine.locked_profile_key
        )
        loop.start()
        return {"ok": True}

    @app.post("/api/hide")
    def api_hide():
        if state.engine is None:
            return JSONResponse({"error": "not running"}, status_code=400)
        state.engine.hidden = not state.engine.hidden
        return {"hidden": state.engine.hidden}

    @app.post("/api/stop")
    def api_stop():
        if state.engine is None:
            return JSONResponse({"error": "not running"}, status_code=400)
        if state.loop:
            state.loop.stop()
        recap = state.engine.recap()
        state.last_recap = recap
        if state.session_id is not None:
            state.store.finish_session(
                state.session_id,
                datetime.now(timezone.utc).isoformat(),
                json.dumps(recap),
            )
        state.store.persist_book()
        state.engine = None
        state.loop = None
        state.session_id = None
        return {"ok": True}

    @app.post("/api/delete/{number}")
    def api_delete(number: int):
        ok = state.store.delete_one(number)
        return {"ok": ok}

    @app.post("/api/delete-all")
    def api_delete_all():
        n = state.store.delete_all()
        return {"deleted": n}

    return app


def serve(camera_index: int | None = None, *, host: str = HOST, port: int = PORT,
          open_browser: bool = True) -> None:
    import uvicorn

    validate_bind_host(host)
    if open_browser:
        import webbrowser

        webbrowser.open(f"http://{host}:{port}")
    uvicorn.run(create_app(camera_index), host=host, port=port, log_level="warning")

"""Loopback dashboard with request origin checks, lifecycle cleanup and no cache."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from typing import Literal

from v2_runtime.camera import inventory_cameras
from .store import Store
from .session import Session

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).parent / "static"


class StartConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source: Literal["demo", "camera"]
    camera_index: int = Field(default=0, ge=0, le=9)
    sensitivity: Literal["low", "high"] = "low"
    duration_minutes: int = Field(default=1, ge=1, le=180)
    adult_confirmed: StrictBool = False


class HideConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hidden: StrictBool


def create_app(data_dir=None, *, session_factory=Session, inventory=inventory_cameras):
    store = Store(data_dir or ROOT / "data" / "dashboard")
    session = session_factory(store)

    @asynccontextmanager
    async def lifespan(app):
        yield
        session.shutdown()
        if not session.thread or not session.thread.is_alive():
            store.close()

    app = FastAPI(
        title="Classroom Mirror",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.session = session
    app.state.store = store

    @app.middleware("http")
    async def protect(request: Request, call_next):
        # Stop DNS rebinding and cross-site drive-by camera/session requests.
        host = request.url.hostname
        origin = request.headers.get("origin")
        if host != "127.0.0.1":
            response = JSONResponse(
                {"error": "Open Classroom Mirror at 127.0.0.1."}, status_code=403
            )
        elif origin and origin != f"http://{request.headers.get('host')}":
            response = JSONResponse(
                {"error": "Only the local dashboard can make this request."},
                status_code=403,
            )
        elif (
            request.method != "GET" and request.headers.get("x-classroom-mirror") != "1"
        ):
            response = JSONResponse(
                {"error": "Use the dashboard controls."}, status_code=403
            )
        elif request.headers.get("sec-fetch-site") == "cross-site":
            response = JSONResponse(
                {"error": "Cross-site access is blocked."}, status_code=403
            )
        else:
            response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
                "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            }
        )
        return response

    @app.get("/")
    def home():
        return FileResponse(STATIC / "index.html")

    @app.get("/assets/{name}")
    def asset(name: Literal["app.js", "style.css"]):
        return FileResponse(STATIC / name)

    @app.get("/health")
    def health():
        return {"ok": True, "product": "teacher-dashboard", "host": "127.0.0.1"}

    @app.get("/api/state")
    def state():
        return session.snapshot()

    @app.post("/api/cameras")
    def cameras():
        with session.scan_lock:
            with session.lock:
                if session.thread and session.thread.is_alive():
                    return JSONResponse(
                        {"error": "Stop the session before checking cameras."},
                        status_code=409,
                    )
                # Keep Start from racing the inventory.
                try:
                    rows = [
                        {"index": c.index, "backend": c.backend}
                        for c in inventory(max_index=5)
                    ]
                except Exception:
                    return JSONResponse(
                        {
                            "error": "Camera access failed. Check camera permission in System Settings, close other camera apps, and try again."
                        },
                        status_code=503,
                    )
        return {"cameras": rows}

    @app.post("/api/start")
    def start(config: StartConfig):
        if config.source == "camera" and not config.adult_confirmed:
            return JSONResponse(
                {
                    "error": "Confirm that this is a consenting-adults-only trial before starting the camera."
                },
                status_code=400,
            )
        try:
            session.start(config.model_dump())
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=409)
        return {"ok": True}

    @app.post("/api/stop")
    def stop():
        return session.stop()

    @app.post("/api/hide")
    def hide(config: HideConfig):
        session.hide(config.hidden)
        return {"hidden": config.hidden}

    @app.get("/api/preview.jpg")
    def preview():
        jpeg = session.preview()
        if jpeg is None:
            return Response(status_code=204)
        return Response(jpeg, media_type="image/jpeg")

    @app.get("/api/recaps")
    def recaps():
        if session.hidden:
            return JSONResponse({"error": "Dashboard is hidden."}, status_code=423)
        return {"recaps": store.list()}

    @app.delete("/api/recaps/{number}")
    def delete(number: int):
        store.delete(number)
        if session.last_recap == number:
            session.last_recap = None
        return {"ok": True}

    @app.delete("/api/recaps")
    def delete_all():
        store.delete()
        session.last_recap = None
        return {"ok": True}

    return app

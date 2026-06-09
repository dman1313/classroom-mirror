"""Classroom Mirror — local web app. Binds to 127.0.0.1 only (guardrail 5)."""
import os
import webbrowser

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, PlainTextResponse

from . import pages, reports
from .camera import CameraService
from .db import Database

HOST, PORT = "127.0.0.1", 8470

app = FastAPI()
db = Database()


def _detector_factory():
    from .detector import PoseDetector  # lazy: model loads on first session
    return PoseDetector()


camera = CameraService(_detector_factory)


@app.get("/", response_class=HTMLResponse)
def home():
    return pages.home_page(db.list_sessions(), db.list_mode1_lims(), camera.last_error)


@app.get("/setup", response_class=HTMLResponse)
def setup():
    return pages.setup_page()


@app.get("/live/{session_id}", response_class=HTMLResponse)
def live(session_id: int):
    return pages.live_page(session_id)


@app.get("/preview.mjpg")
def preview():
    try:
        camera.ensure_running()
    except RuntimeError as e:
        return PlainTextResponse(str(e), status_code=503)
    return StreamingResponse(camera.mjpeg(),
                             media_type="multipart/x-mixed-replace; boundary=frame")


@app.post("/api/session/start")
async def session_start(request: Request):
    payload = await request.json()
    try:
        session_id = camera.start_session(
            db,
            mode=payload.get("mode", ""),
            phase=payload.get("phase", "none"),
            class_code=payload.get("class_code", ""),
            designations=payload.get("designations", []),
        )
    except (ValueError, PermissionError, RuntimeError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return {"id": session_id}


@app.post("/api/session/stop")
def session_stop():
    session_id = camera.stop_session(db)
    if session_id is None:
        return JSONResponse({"error": "No session is running."}, status_code=400)
    info = db.get_session(session_id)
    if info and info["mode"] == "mode2":
        url = f"/report/session/{session_id}"
    else:
        lims = db.list_mode1_lims()
        url = f"/report/lims/{lims[0]}" if lims else "/"
    return {"id": session_id, "report_url": url}


@app.get("/report/lims/{code}", response_class=HTMLResponse)
def report_lims(code: str):
    try:
        return reports.mode1_report_html(db, code)
    except ValueError as e:
        return HTMLResponse(f"<p>{e}</p>", status_code=400)


@app.get("/report/session/{session_id}", response_class=HTMLResponse)
def report_session(session_id: int):
    return reports.mode2_summary_html(db, session_id)


@app.get("/compare", response_class=HTMLResponse)
def compare(a: int, b: int):
    return reports.mode2_compare_html(db, a, b)


@app.post("/api/delete/lims/{code}")
def delete_lims(code: str):
    try:
        return {"deleted": db.delete_lims(code)}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.post("/api/delete/session/{session_id}")
def delete_session(session_id: int):
    return {"deleted": db.delete_session(session_id)}


@app.get("/contract", response_class=HTMLResponse)
def contract():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "CONTRACT.md")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return HTMLResponse(f"<pre style='max-width:80ch;margin:2rem auto;"
                        f"white-space:pre-wrap'>{text}</pre>")


def main():
    import uvicorn
    webbrowser.open(f"http://{HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()

"""Local, teacher-only V2 movement dashboard (loopback FastAPI service).

This is the first teacher-visible V2 slice: pick a camera and a High/Low
sensitivity, press Start, watch anonymous position numbers with a calm / yellow
/ red movement cue, hide instantly for privacy, press Stop, and read a neutral
recap. The browser only ever receives abstract marker positions and a colour -
never a camera image. The service binds exclusively to 127.0.0.1.
"""

from __future__ import annotations

import argparse
import html
import threading
import time

from .engine import MovementEngine
from .policy import LOOPBACK_HOST, validate_bind_host
from .sensitivity import PROFILES, profile_for
from .sources import build_source


DEFAULT_PORT = 8471
_FRAME_INTERVAL = 0.1


class SessionController:
    """Owns the capture thread, engine, and privacy/recap state (thread-safe)."""

    def __init__(self, *, frame_interval: float = _FRAME_INTERVAL) -> None:
        self._lock = threading.Lock()
        self._frame_interval = frame_interval
        self._state = "idle"  # idle -> running -> stopped
        self._engine: MovementEngine | None = None
        self._source = None
        self._source_label = ""
        self._sensitivity = ""
        self._hidden = False
        self._views: list = []
        self._overall = "calm"
        self._started_at: float | None = None
        self._recap = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._read_failures = 0

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def start(self, *, source_kind: str, camera_index: int | None, sensitivity: str) -> None:
        profile = profile_for(sensitivity)
        with self._lock:
            if self._state == "running":
                raise RuntimeError("a session is already running")
            source = build_source(source_kind, camera_index=camera_index)
            self._source = source
            self._source_label = source.label
            self._engine = MovementEngine(profile)
            self._sensitivity = profile.name
            self._hidden = False
            self._views = []
            self._overall = "calm"
            self._recap = None
            self._read_failures = 0
            self._started_at = time.monotonic()
            self._state = "running"
            self._stop_event = threading.Event()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            source = self._source
            engine = self._engine
            if source is None or engine is None:
                break
            frame = source.read()
            now = time.monotonic()
            if frame is None:
                self._read_failures += 1
                if self._read_failures > 30:
                    break
                self._stop_event.wait(self._frame_interval)
                continue
            self._read_failures = 0
            views = engine.update(frame, now=now)
            overall = engine.overall_motion(views)
            with self._lock:
                self._views = views
                self._overall = overall
            self._stop_event.wait(self._frame_interval)

    def stop(self) -> None:
        with self._lock:
            if self._state != "running":
                return
            thread = self._thread
            self._stop_event.set()
        if thread is not None:
            thread.join(timeout=2.0)
        with self._lock:
            engine = self._engine
            recap = engine.recap() if engine is not None else None
            if self._source is not None:
                try:
                    self._source.release()
                except Exception:
                    pass
            self._source = None
            self._recap = recap
            self._state = "stopped"

    def set_hidden(self, hidden: bool) -> bool:
        with self._lock:
            self._hidden = bool(hidden)
            return self._hidden

    def toggle_hidden(self) -> bool:
        with self._lock:
            self._hidden = not self._hidden
            return self._hidden

    def delete(self) -> None:
        self.stop()
        with self._lock:
            self._engine = None
            self._recap = None
            self._views = []
            self._overall = "calm"
            self._sensitivity = ""
            self._source_label = ""
            self._started_at = None
            self._state = "idle"

    def snapshot(self) -> dict:
        with self._lock:
            elapsed = 0.0
            if self._started_at is not None:
                elapsed = time.monotonic() - self._started_at
            hidden = self._hidden
            markers = (
                []
                if hidden
                else [
                    {"number": v.number, "x": v.x, "y": v.y, "level": v.level}
                    for v in self._views
                ]
            )
            return {
                "state": self._state,
                "hidden": hidden,
                "sensitivity": self._sensitivity,
                "source": self._source_label,
                "overall": "hidden" if hidden else self._overall,
                "markers": markers,
                "count": 0 if hidden else len(self._views),
                "elapsed_seconds": round(elapsed, 1),
            }

    def recap_lines(self) -> list[str]:
        with self._lock:
            return self._recap.to_lines() if self._recap is not None else []


_PAGE_STYLE = (
    "body{font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;"
    "max-width:52rem;margin:2.5rem auto;padding:0 1rem;color:#1f2933;"
    "background:#f7f9fb}h1{font-size:1.6rem}"
    "main{background:#fff;border:1px solid #d6dde4;border-radius:14px;padding:1.5rem}"
    "button,select{font:inherit}"
    ".btn{border:0;border-radius:10px;padding:.6rem 1.1rem;cursor:pointer;"
    "background:#1f6feb;color:#fff}.btn.secondary{background:#5b6874}"
    ".btn.danger{background:#b42318}"
    "select{padding:.5rem;border-radius:8px;border:1px solid #b6c0cb}"
    "label{display:block;margin:1rem 0 .3rem;font-weight:600}"
    "footer{margin-top:1.2rem;color:#5b6874;font-size:.85rem}"
    "code{background:#eef1f4;padding:.1rem .35rem;border-radius:4px}"
)


def _shell(title: str, body: str) -> str:
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{html.escape(title)}</title><style>{_PAGE_STYLE}</style></head>"
        f"<body><main>{body}</main></body></html>"
    )


def _config_body(controller: SessionController) -> str:
    options = "".join(
        f"<option value='{key}'>{html.escape(profile.name)} sensitivity - "
        f"{'flags sustained movement sooner' if key == 'high' else 'needs longer sustained movement'}"
        "</option>"
        for key, profile in PROFILES.items()
    )
    return (
        "<h1>Classroom Mirror V2</h1>"
        "<p>Private teacher view. Adults only for this alpha. Frames stay in "
        "memory, nothing is saved, and this page is only on "
        f"<code>{LOOPBACK_HOST}</code>.</p>"
        "<form method='post' action='/start'>"
        "<label for='sensitivity'>Sensitivity (locked once you Start)</label>"
        f"<select id='sensitivity' name='sensitivity'>{options}</select>"
        "<label for='source'>Camera</label>"
        "<select id='source' name='source'>"
        "<option value='synthetic'>Demo movers (no camera needed)</option>"
        "<option value='camera'>USB camera index 0</option>"
        "<option value='camera1'>USB camera index 1</option>"
        "</select>"
        "<p><button class='btn' type='submit'>Start</button></p>"
        "</form>"
        "<footer>No faces, no names, no recording. Anonymous numbers are screen "
        "positions only, not identities.</footer>"
    )


def _live_body() -> str:
    return (
        "<h1>Live movement view</h1>"
        "<p id='status'>Starting...</p>"
        "<div style='position:relative'>"
        "<svg id='stage' viewBox='0 0 100 75' width='100%' "
        "style='background:#0f172a;border-radius:12px;aspect-ratio:4/3'></svg>"
        "<div id='veil' style='display:none;position:absolute;inset:0;"
        "background:#0f172a;border-radius:12px;color:#e2e8f0;"
        "align-items:center;justify-content:center;font-size:1.2rem'>"
        "Hidden for privacy</div></div>"
        "<p style='margin-top:1rem'>"
        "<button class='btn secondary' type='button' id='hide'>Hide for privacy</button> "
        "<form method='post' action='/stop' style='display:inline'>"
        "<button class='btn danger' type='submit'>Stop &amp; recap</button></form>"
        "</p>"
        "<p><span style='color:#16a34a'>&#9679; calm</span> &nbsp; "
        "<span style='color:#d29922'>&#9679; yellow (sustained movement)</span> &nbsp; "
        "<span style='color:#e5484d'>&#9679; red (movement stayed high)</span></p>"
        "<footer>Yellow always appears before red. Brief movement settles back "
        "to calm. The picture below is drawn from positions only - no camera "
        "image is ever sent to this page.</footer>"
        "<script>" + _LIVE_SCRIPT + "</script>"
    )


_LIVE_SCRIPT = """
var COLORS = {calm:'#16a34a', yellow:'#d29922', red:'#e5484d'};
var hidden = false;
var stage = document.getElementById('stage');
var veil = document.getElementById('veil');
var status = document.getElementById('status');
document.getElementById('hide').addEventListener('click', function(){
  fetch('/hide', {method:'POST'}).then(function(r){return r.json();}).then(function(d){
    hidden = d.hidden; applyVeil();
  });
});
function applyVeil(){ veil.style.display = hidden ? 'flex' : 'none'; }
function draw(markers){
  while (stage.firstChild) stage.removeChild(stage.firstChild);
  markers.forEach(function(m){
    var g = document.createElementNS('http://www.w3.org/2000/svg','g');
    var c = document.createElementNS('http://www.w3.org/2000/svg','circle');
    c.setAttribute('cx', (m.x*100).toFixed(1));
    c.setAttribute('cy', (m.y*75).toFixed(1));
    c.setAttribute('r', m.level==='red' ? 5.5 : 4.5);
    c.setAttribute('fill', COLORS[m.level] || '#94a3b8');
    c.setAttribute('opacity','0.9');
    var t = document.createElementNS('http://www.w3.org/2000/svg','text');
    t.setAttribute('x', (m.x*100).toFixed(1));
    t.setAttribute('y', (m.y*75+1.4).toFixed(1));
    t.setAttribute('text-anchor','middle');
    t.setAttribute('font-size','3.2');
    t.setAttribute('fill','#0f172a');
    t.textContent = m.number;
    g.appendChild(c); g.appendChild(t); stage.appendChild(g);
  });
}
function tick(){
  fetch('/state').then(function(r){return r.json();}).then(function(d){
    if (d.state === 'stopped') { window.location = '/recap'; return; }
    hidden = d.hidden; applyVeil();
    draw(d.markers || []);
    status.textContent = 'Sensitivity ' + d.sensitivity + ' | source: ' + d.source +
      ' | numbers now: ' + d.count + ' | overall: ' + d.overall +
      ' | ' + d.elapsed_seconds + 's';
  }).catch(function(){}).then(function(){ setTimeout(tick, 250); });
}
tick();
"""


def _recap_body(controller: SessionController) -> str:
    lines = controller.recap_lines()
    if not lines:
        items = "<li>No session has been recorded yet.</li>"
    else:
        items = "".join(f"<li>{html.escape(line)}</li>" for line in lines)
    return (
        "<h1>Session recap</h1>"
        f"<ul>{items}</ul>"
        "<form method='post' action='/delete'>"
        "<button class='btn danger' type='submit'>Delete this session and start over</button>"
        "</form>"
        "<footer>This recap describes movement signals only, with no ranking of "
        "individuals and no stored data. Deleting returns you to the start "
        "screen with nothing retained.</footer>"
    )


def create_app(controller: SessionController | None = None):
    from fastapi import FastAPI, Form
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

    controller = controller or SessionController()
    app = FastAPI(title="Classroom Mirror V2 dashboard", docs_url=None, redoc_url=None)
    app.state.controller = controller

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'unsafe-inline'; "
            "style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; "
            "form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/health")
    def health():
        return {"ok": True, "host": LOOPBACK_HOST, "state": controller.state}

    @app.get("/", response_class=HTMLResponse)
    def home():
        if controller.state == "running":
            return RedirectResponse("/live", status_code=303)
        if controller.state == "stopped":
            return RedirectResponse("/recap", status_code=303)
        return HTMLResponse(_shell("Classroom Mirror V2", _config_body(controller)))

    @app.post("/start")
    def start(sensitivity: str = Form("high"), source: str = Form("synthetic")):
        source_kind = "synthetic"
        camera_index = None
        if source.startswith("camera"):
            source_kind = "camera"
            camera_index = 1 if source == "camera1" else 0
        try:
            controller.start(
                source_kind=source_kind,
                camera_index=camera_index,
                sensitivity=sensitivity,
            )
        except Exception as exc:  # surface a plain message, stay on config
            body = (
                f"<h1>Could not start</h1><p>{html.escape(str(exc))}</p>"
                "<p><a href='/'>Back</a></p>"
            )
            return HTMLResponse(_shell("Could not start", body), status_code=400)
        return RedirectResponse("/live", status_code=303)

    @app.get("/live", response_class=HTMLResponse)
    def live():
        if controller.state == "idle":
            return RedirectResponse("/", status_code=303)
        if controller.state == "stopped":
            return RedirectResponse("/recap", status_code=303)
        return HTMLResponse(_shell("Live movement view", _live_body()))

    @app.get("/state")
    def state():
        return JSONResponse(controller.snapshot())

    @app.post("/hide")
    def hide():
        return JSONResponse({"hidden": controller.toggle_hidden()})

    @app.post("/stop")
    def stop():
        controller.stop()
        return RedirectResponse("/recap", status_code=303)

    @app.get("/recap", response_class=HTMLResponse)
    def recap():
        if controller.state == "idle":
            return RedirectResponse("/", status_code=303)
        return HTMLResponse(_shell("Session recap", _recap_body(controller)))

    @app.post("/delete")
    def delete():
        controller.delete()
        return RedirectResponse("/", status_code=303)

    return app


def serve(
    *,
    host: str = LOOPBACK_HOST,
    port: int = DEFAULT_PORT,
    open_browser: bool = True,
    controller: SessionController | None = None,
) -> None:
    import uvicorn

    validate_bind_host(host)
    if not 1024 <= port <= 65535:
        raise ValueError("port must be between 1024 and 65535")
    if open_browser:
        import webbrowser

        webbrowser.open(f"http://{host}:{port}")
    uvicorn.run(create_app(controller), host=host, port=port, log_level="warning")


def _run_headless_smoke(source_kind: str, camera_index: int | None, sensitivity: str,
                        frames: int) -> int:
    """Run the engine over N frames with no server and print a recap."""
    profile = profile_for(sensitivity)
    source = build_source(source_kind, camera_index=camera_index)
    engine = MovementEngine(profile)
    try:
        clock = 0.0
        for _ in range(frames):
            frame = source.read()
            if frame is None:
                break
            clock += _FRAME_INTERVAL
            engine.update(frame, now=clock)
    finally:
        source.release()
    recap = engine.recap(ended_at=clock)
    print(f"Smoke source: {source.label}")
    for line in recap.to_lines():
        print(f"- {line}")
    print("frame_writes=0 host=127.0.0.1")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classroom Mirror V2 movement dashboard")
    parser.add_argument("--source", choices=("synthetic", "camera"), default="synthetic")
    parser.add_argument("--camera-index", type=int)
    parser.add_argument("--sensitivity", choices=("high", "low"), default="high")
    parser.add_argument("--host", default=LOOPBACK_HOST, help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--smoke-test", action="store_true",
                        help="Run headless over --frames and print a recap only.")
    parser.add_argument("--frames", type=int, default=120)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validate_bind_host(args.host)
    if args.smoke_test:
        return _run_headless_smoke(
            args.source, args.camera_index, args.sensitivity, args.frames
        )
    controller = SessionController()
    print(f"Starting Classroom Mirror V2 dashboard at http://{args.host}:{args.port}")
    print("Private teacher view. Adults only for this alpha. Frames stay in memory.")
    serve(
        host=args.host,
        port=args.port,
        open_browser=not args.no_browser,
        controller=controller,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

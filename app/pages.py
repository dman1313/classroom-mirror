"""UI pages. Plain HTML + a little vanilla JS, served from localhost only.

There is deliberately no free-text input anywhere (guardrail 4): the only
typed fields are LIMS and class codes, pattern-locked in the browser AND
re-validated on the server.
"""
from html import escape

from .validate import CODE_HTML_PATTERN, CODE_MAXLENGTH

_CSS = """
body { font-family: -apple-system, sans-serif; margin: 2rem auto; max-width: 860px;
       color: #222; line-height: 1.5; }
h1 { font-size: 1.5rem; } h2 { font-size: 1.15rem; margin-top: 1.8rem; }
.btn { display: inline-block; padding: .55rem 1.1rem; border-radius: 8px; border: 0;
       background: #3a6ea5; color: #fff; font-size: 1rem; cursor: pointer;
       text-decoration: none; }
.btn.quiet { background: #e8edf3; color: #234; }
.banner { background: #fdf3d7; border: 1px solid #e0c060; padding: .6rem .9rem;
          border-radius: 8px; margin: .8rem 0; }
table { border-collapse: collapse; width: 100%; margin: .6rem 0; }
th, td { border: 1px solid #ccc; padding: .35rem .6rem; font-size: .95rem; text-align: left; }
th { background: #f3f5f7; }
input, select { font-size: 1rem; padding: .35rem; }
.note { color: #555; font-size: .9rem; }
#wrap { position: relative; display: inline-block; }
#overlay { position: absolute; left: 0; top: 0; cursor: crosshair; }
label { margin-right: .8rem; }
.row { margin: .7rem 0; }
"""


def _page(title: str, body: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{escape(title)}</title><style>{_CSS}</style></head>"
        f"<body><h1>{escape(title)}</h1>{body}</body></html>"
    )


def home_page(sessions, lims_codes, camera_error=None) -> str:
    banner = (f"<div class='banner'>{escape(camera_error)}</div>" if camera_error else "")

    rows = []
    for s in sessions:
        if s["mode"] == "mode2":
            link = f"<a href='/report/session/{s['id']}'>summary</a>"
        else:
            link = "see strategy reports below"
        rows.append(
            f"<tr><td>{s['id']}</td><td>{escape(s['mode'])}</td>"
            f"<td>{escape(s['phase'])}</td><td>{escape(s['class_code'])}</td>"
            f"<td>{escape(s['started_at'])}</td><td>{link}</td>"
            f"<td><button class='btn quiet' onclick=\"del('/api/delete/session/{s['id']}')\">"
            "delete</button></td></tr>"
        )
    session_table = (
        "<table><tr><th>#</th><th>Mode</th><th>Phase</th><th>Class</th>"
        "<th>Started</th><th>Report</th><th></th></tr>"
        + ("".join(rows) or "<tr><td colspan='7'>No sessions yet.</td></tr>")
        + "</table>"
    )

    lims_links = " ".join(
        f"<a class='btn quiet' href='/report/lims/{escape(c)}'>LIMS {escape(c)}</a> "
        f"<button class='btn quiet' onclick=\"del('/api/delete/lims/{escape(c)}')\">"
        f"erase {escape(c)}</button>"
        for c in lims_codes
    ) or "<span class='note'>No designated children recorded yet.</span>"

    compare = """
    <form onsubmit="event.preventDefault();
        location='/compare?a='+this.a.value+'&b='+this.b.value;">
      <label>Session <input name='a' size='3' required pattern='[0-9]+'></label>
      <label>vs <input name='b' size='3' required pattern='[0-9]+'></label>
      <button class='btn quiet'>Compare</button>
    </form>"""

    body = f"""
    {banner}
    <p>A mirror for your classroom practice. Two modes — whole-class numbers are
    always anonymous; individual tracking exists only for a designated child
    with recorded consent.</p>
    <div class='row'>
      <a class='btn' href='/setup'>Start an individual session (Mode 1)</a>
      <button class='btn' onclick='startMode2()'>Start a whole-class session (Mode 2)</button>
      <label>class code <input id='m2class' size='8' required
        pattern='{CODE_HTML_PATTERN}' maxlength='{CODE_MAXLENGTH}' placeholder='6B'></label>
    </div>
    <h2>Sessions</h2>{session_table}
    <h2>Whole-class comparison</h2>{compare}
    <h2>Strategy reports (designated children)</h2><p>{lims_links}</p>
    <p class='note'>To re-check everything this app promises, run <code>./check</code>
    in the app folder — see <a href='/contract'>the contract</a>.</p>
    <script>
    async function startMode2() {{
      const cls = document.getElementById('m2class').value;
      const r = await fetch('/api/session/start', {{method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body: JSON.stringify({{mode:'mode2', phase:'none', class_code: cls,
                               designations: []}})}});
      const j = await r.json();
      if (!r.ok) {{ alert(j.error); return; }}
      location = '/live/' + j.id;
    }}
    async function del(url) {{
      if (!confirm('Delete this data? This cannot be undone.')) return;
      await fetch(url, {{method:'POST'}});
      location.reload();
    }}
    </script>"""
    return _page("Classroom Mirror", body)


def setup_page() -> str:
    body = f"""
    <p><b>1.</b> Drag a box over the designated child's usual spot.
    <b>2.</b> Type their LIMS code (never a name). <b>3.</b> Tick consent
    only if consent is really recorded. <b>4.</b> Start.</p>
    <div id='wrap'>
      <img id='cam' src='/preview.mjpg' width='640' height='480'>
      <canvas id='overlay' width='640' height='480'></canvas>
    </div>
    <div class='row'>
      <label>LIMS code <input id='lims' size='10' pattern='{CODE_HTML_PATTERN}'
             maxlength='{CODE_MAXLENGTH}' placeholder='L-1042'></label>
      <label><input type='checkbox' id='consent'> consent is recorded for this child</label>
      <button class='btn quiet' onclick='addChild()'>Add this child</button>
    </div>
    <ul id='children'></ul>
    <div class='row'>
      <label>Phase
        <select id='phase'>
          <option value='baseline'>baseline (before the strategy)</option>
          <option value='strategy'>strategy (the strategy is in use)</option>
        </select></label>
      <label>class code <input id='cls' size='8' pattern='{CODE_HTML_PATTERN}'
             maxlength='{CODE_MAXLENGTH}' placeholder='6B'></label>
      <button class='btn' onclick='startSession()'>Start session</button>
      <a class='btn quiet' href='/'>Cancel</a>
    </div>
    <script>
    const canvas = document.getElementById('overlay'), ctx = canvas.getContext('2d');
    let drag = null, rect = null, children = [];
    canvas.onmousedown = e => {{ drag = [e.offsetX, e.offsetY]; }};
    canvas.onmousemove = e => {{
      if (!drag) return;
      rect = [Math.min(drag[0], e.offsetX), Math.min(drag[1], e.offsetY),
              Math.abs(e.offsetX - drag[0]), Math.abs(e.offsetY - drag[1])];
      draw();
    }};
    canvas.onmouseup = () => {{ drag = null; }};
    function draw() {{
      ctx.clearRect(0, 0, 640, 480);
      ctx.lineWidth = 2; ctx.strokeStyle = '#3a6ea5'; ctx.font = '14px sans-serif';
      ctx.fillStyle = '#3a6ea5';
      for (const c of children) {{
        ctx.strokeRect(...c.px); ctx.fillText(c.lims, c.px[0], c.px[1] - 4);
      }}
      if (rect) {{ ctx.strokeStyle = '#e0a040'; ctx.strokeRect(...rect); }}
    }}
    function addChild() {{
      const lims = document.getElementById('lims').value.trim();
      const consent = document.getElementById('consent').checked;
      if (!rect || rect[2] < 10) {{ alert('Drag a box over the child\\'s spot first.'); return; }}
      if (!lims.match(/^{CODE_HTML_PATTERN}$/)) {{
        alert('A LIMS code is 1-12 letters, digits or hyphens - never a name.'); return; }}
      children.push({{ lims: lims, consent: consent, px: rect,
        zone: [rect[0]/640, rect[1]/480, rect[2]/640, rect[3]/480] }});
      document.getElementById('children').innerHTML = children.map(c =>
        '<li>LIMS ' + c.lims + (c.consent ? ' (consent recorded)' : ' (NO CONSENT)') + '</li>'
      ).join('');
      rect = null; document.getElementById('lims').value = '';
      document.getElementById('consent').checked = false; draw();
    }}
    async function startSession() {{
      const r = await fetch('/api/session/start', {{method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body: JSON.stringify({{
          mode: 'mode1',
          phase: document.getElementById('phase').value,
          class_code: document.getElementById('cls').value,
          designations: children.map(c => ({{lims: c.lims, zone: c.zone,
                                            consent: c.consent}}))
        }})}});
      const j = await r.json();
      if (!r.ok) {{ alert(j.error); return; }}
      location = '/live/' + j.id;
    }}
    </script>"""
    return _page("Individual session setup", body)


def live_page(session_id: int) -> str:
    body = f"""
    <p>Session {session_id} is recording <b>numbers only</b> — no video is
    being saved. Watch the live view to confirm the right spot is tracked.</p>
    <img src='/preview.mjpg' width='640' height='480'>
    <div class='row'>
      <button class='btn' onclick='stopSession()'>Stop session</button>
    </div>
    <script>
    async function stopSession() {{
      const r = await fetch('/api/session/stop', {{method:'POST'}});
      const j = await r.json();
      location = j.report_url || '/';
    }}
    </script>"""
    return _page("Session running", body)

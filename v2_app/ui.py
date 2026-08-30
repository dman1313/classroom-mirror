"""Teacher-only HTML. No class-facing video. No name fields."""

from html import escape

CSS = """
:root { --bg:#0f1419; --card:#1a222c; --ink:#e8eef4; --mute:#9aa7b5; --line:#2a3542;
        --yellow:#c9a227; --red:#c44; --ok:#3d9b6a; }
* { box-sizing:border-box; }
body { margin:0; font:18px/1.45 ui-sans-serif,system-ui; background:var(--bg); color:var(--ink); }
main { max-width:52rem; margin:0 auto; padding:1.5rem; }
h1 { font-size:1.6rem; margin:0 0 .4rem; }
p.mute { color:var(--mute); }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(9rem,1fr)); gap:.8rem; }
.card { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:1rem; text-align:center; }
.card.yellow { border-color:var(--yellow); box-shadow:0 0 0 2px var(--yellow); }
.card.red { border-color:var(--red); box-shadow:0 0 0 2px var(--red); }
.num { font-size:3rem; font-weight:700; }
.btn { font:inherit; padding:.7rem 1.1rem; border:0; border-radius:10px; background:#3a6ea5; color:#fff; cursor:pointer; }
.btn.stop { background:var(--red); font-size:1.3rem; padding:1rem 1.6rem; }
.btn.quiet { background:#2a3542; }
.row { display:flex; gap:.6rem; flex-wrap:wrap; margin:1rem 0; }
label { display:block; margin:.6rem 0 .2rem; }
select { font:inherit; padding:.4rem; }
.banner { background:#2a2416; border:1px solid var(--yellow); padding:.8rem 1rem; border-radius:10px; }
"""


def _page(title: str, body: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{escape(title)}</title><style>{CSS}</style></head>"
        f"<body><main>{body}</main></body></html>"
    )


def setup_page(cameras: list[dict], error: str | None = None) -> str:
    opts = "".join(
        f"<option value='{c['index']}'>Camera {c['index']} ({escape(c['backend'])})</option>"
        for c in cameras
    ) or "<option value=''>No camera found</option>"
    banner = f"<div class='banner'>{escape(error)}</div>" if error else ""
    return _page(
        "Classroom Mirror",
        f"""
        <h1>Classroom Mirror</h1>
        <p class="mute">Teacher-only. Students must not see this screen. Adult beta only.</p>
        {banner}
        <p>USB camera at the desk, aimed down the class. No names. Flags mean
        <strong>possible support needed</strong>, not a judgment.</p>
        <form id="start">
          <label>Camera</label>
          <select name="camera_index">{opts}</select>
          <label>Sensitivity</label>
          <select name="sensitivity">
            <option value="low">Low</option>
            <option value="high">High</option>
          </select>
          <div class="row">
            <button class="btn" type="submit">Start class</button>
          </div>
        </form>
        <script>
        document.getElementById('start').onsubmit = async (e) => {{
          e.preventDefault();
          const fd = new FormData(e.target);
          const r = await fetch('/api/start', {{
            method:'POST',
            headers:{{'Content-Type':'application/json'}},
            body: JSON.stringify({{
              camera_index: Number(fd.get('camera_index')),
              sensitivity: fd.get('sensitivity')
            }})
          }});
          const j = await r.json();
          if (!r.ok) {{ alert(j.error || 'Could not start'); return; }}
          location.href = '/live';
        }};
        </script>
        """,
    )


def live_page() -> str:
    return _page(
        "Classroom Mirror — live",
        """
        <h1>Live — teacher only</h1>
        <p class="mute" id="copy"></p>
        <div class="row">
          <button class="btn quiet" id="hide">Hide numbers</button>
          <button class="btn stop" id="stop">Stop</button>
        </div>
        <div class="grid" id="grid"></div>
        <script>
        const grid = document.getElementById('grid');
        const copy = document.getElementById('copy');
        async function tick() {
          const r = await fetch('/api/state');
          const j = await r.json();
          copy.textContent = j.support_copy || '';
          grid.innerHTML = '';
          if (j.hidden) {
            grid.innerHTML = '<p class="mute">Numbers hidden.</p>';
            return;
          }
          for (const s of (j.students || [])) {
            const el = document.createElement('div');
            el.className = 'card ' + (s.band === 'none' ? '' : s.band);
            el.innerHTML = '<div class="num">' + s.number + '</div>'
              + '<div>' + (s.cue || 'ok') + '</div>'
              + '<div class="mute">raises ' + s.raises + '</div>';
            grid.appendChild(el);
          }
        }
        document.getElementById('hide').onclick = async () => {
          await fetch('/api/hide', {method:'POST'});
          tick();
        };
        document.getElementById('stop').onclick = async () => {
          const r = await fetch('/api/stop', {method:'POST'});
          if (r.ok) location.href = '/recap';
        };
        setInterval(tick, 700);
        tick();
        </script>
        """,
    )


def recap_page() -> str:
    return _page(
        "Classroom Mirror — recap",
        """
        <h1>End of class recap</h1>
        <p class="mute" id="copy"></p>
        <div id="rows"></div>
        <div class="row">
          <a class="btn quiet" href="/">Back</a>
          <button class="btn quiet" id="wipe">Delete all anonymous numbers</button>
        </div>
        <script>
        async function load() {
          const r = await fetch('/api/recap');
          const j = await r.json();
          document.getElementById('copy').textContent = j.support_copy || '';
          const rows = document.getElementById('rows');
          rows.innerHTML = (j.students || []).map(s =>
            '<div class="card ' + (s.peak_band||'') + '"><div class="num">' + s.number + '</div>'
            + '<div>' + (s.cue || 'no cue') + '</div>'
            + '<div class="mute">hand-raises ' + s.raises + '</div>'
            + '<button class="btn quiet" data-n="' + s.number + '">Delete this number</button></div>'
          ).join('') || '<p>No numbered people this session.</p>';
          rows.querySelectorAll('button[data-n]').forEach(btn => {
            btn.onclick = async () => {
              await fetch('/api/delete/' + btn.dataset.n, {method:'POST'});
              load();
            };
          });
        }
        document.getElementById('wipe').onclick = async () => {
          if (!confirm('Delete every anonymous number stored on this laptop?')) return;
          await fetch('/api/delete-all', {method:'POST'});
          load();
        };
        load();
        </script>
        """,
    )

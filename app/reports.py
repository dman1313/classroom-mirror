"""Report rendering. Every sentence a report can contain lives in this file
as a fixed template — the guardrail test renders sample reports and scans
them against a banned-terms list, so no judgment language can creep in.

Reports state counted events and how they changed. Nothing more.
"""
from collections import Counter
from html import escape
from typing import List

DISCLAIMER = (
    "These numbers describe counted events only. "
    "They are not a judgment of any child."
)

_CSS = """
body { font-family: -apple-system, sans-serif; margin: 2rem auto; max-width: 760px;
       color: #222; line-height: 1.5; }
h1 { font-size: 1.4rem; } h2 { font-size: 1.1rem; margin-top: 1.6rem; }
table { border-collapse: collapse; width: 100%; margin: .6rem 0; }
th, td { border: 1px solid #ccc; padding: .35rem .6rem; text-align: left; font-size: .95rem; }
th { background: #f3f5f7; }
.note { color: #555; font-size: .9rem; border-left: 3px solid #8fb0d8;
        padding-left: .7rem; margin: 1rem 0; }
.compare { font-size: 1.05rem; margin: .3rem 0; }
.cols { display: flex; gap: 2rem; } .cols > div { flex: 1; }
a { color: #3a6ea5; }
"""

_MOVE_SHADE = {"low": "#dde6f0", "medium": "#8fb0d8", "high": "#3a6ea5"}


def _page(title: str, body: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{escape(title)}</title><style>{_CSS}</style></head><body>"
        f"<h1>{escape(title)}</h1>"
        f"<p class='note'>{DISCLAIMER}</p>"
        f"{body}"
        "<p><a href='/'>Back to home</a></p>"
        "</body></html>"
    )


def _bars_svg(values: List[float], labels: List[str], width: int = 640) -> str:
    if not values:
        return ""
    top = max(max(values), 1e-9)
    n = len(values)
    bw = max(int(width / n) - 8, 12)
    h = 120
    parts = [f"<svg width='{width}' height='{h + 22}' role='img'>"]
    for i, (v, lab) in enumerate(zip(values, labels)):
        bh = int(h * v / top)
        x = i * (bw + 8)
        parts.append(
            f"<rect x='{x}' y='{h - bh}' width='{bw}' height='{bh}' fill='#8fb0d8'/>"
            f"<text x='{x + bw / 2}' y='{h + 14}' font-size='10' "
            f"text-anchor='middle'>{escape(lab)}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def _movement_strip(buckets: List[str]) -> str:
    cell = 18
    parts = [f"<svg width='{cell * max(len(buckets), 1)}' height='26' role='img'>"]
    for i, b in enumerate(buckets):
        parts.append(
            f"<rect x='{i * cell}' y='0' width='{cell - 2}' height='18' "
            f"fill='{_MOVE_SHADE.get(b, '#dde6f0')}'/>"
        )
    parts.append("</svg>")
    return ("".join(parts)
            + "<div class='note'>Movement level per minute: light = low, "
              "mid-blue = medium, dark = high.</div>")


# -- mode 1: before / after ---------------------------------------------------

def _session_stats(s) -> dict:
    minutes = s["minutes"]
    n = len(minutes)
    if n == 0:
        return {"minutes": 0, "raises_per_10": 0.0, "at_spot": 0.0, "movement": "low"}
    raises_per_10 = s["hand_raises"] / n * 10
    at_spot = sum(m["at_spot_pct"] for m in minutes) / n
    movement = Counter(m["movement_bucket"] for m in minutes).most_common(1)[0][0]
    return {"minutes": n, "raises_per_10": raises_per_10,
            "at_spot": at_spot, "movement": movement}


def _phase_average(sessions) -> dict:
    stats = [_session_stats(s) for s in sessions if s["minutes"]]
    if not stats:
        return {}
    return {
        "raises_per_10": sum(x["raises_per_10"] for x in stats) / len(stats),
        "at_spot": sum(x["at_spot"] for x in stats) / len(stats),
        "movement": Counter(x["movement"] for x in stats).most_common(1)[0][0],
        "n": len(stats),
    }


def mode1_report_html(db, lims_code: str) -> str:
    sessions = db.mode1_data(lims_code)
    title = f"Strategy report — LIMS {lims_code}"
    if not sessions:
        return _page(title, "<p>No sessions recorded for this LIMS code yet.</p>")

    rows = []
    for s in sessions:
        st = _session_stats(s)
        rows.append(
            f"<tr><td>{s['id']}</td><td>{escape(s['started_at'])}</td>"
            f"<td>{escape(s['phase'])}</td><td>{escape(s['class_code'])}</td>"
            f"<td>{s['hand_raises']}</td><td>{st['at_spot']:.0f}%</td>"
            f"<td>{escape(st['movement'])}</td></tr>"
        )
    table = (
        "<h2>Sessions</h2><table><tr><th>#</th><th>Started</th><th>Phase</th>"
        "<th>Class</th><th>Hand raises</th><th>Time at their spot</th>"
        "<th>Movement level</th></tr>" + "".join(rows) + "</table>"
    )

    base = _phase_average([s for s in sessions if s["phase"] == "baseline"])
    strat = _phase_average([s for s in sessions if s["phase"] == "strategy"])
    if base and strat:
        d_r = strat["raises_per_10"] - base["raises_per_10"]
        d_a = strat["at_spot"] - base["at_spot"]
        compare = (
            "<h2>Before and after the strategy</h2>"
            f"<p class='compare'>Hand raises per 10 minutes: baseline "
            f"{base['raises_per_10']:.1f} &rarr; strategy {strat['raises_per_10']:.1f} "
            f"({d_r:+.1f})</p>"
            f"<p class='compare'>Time at their spot: baseline {base['at_spot']:.0f}% "
            f"&rarr; strategy {strat['at_spot']:.0f}% ({d_a:+.0f} points)</p>"
            f"<p class='compare'>Most common movement level: baseline "
            f"{escape(base['movement'])} &rarr; strategy {escape(strat['movement'])}</p>"
            f"<p class='note'>Averages of {base['n']} baseline and {strat['n']} "
            "strategy session(s).</p>"
        )
    else:
        compare = (
            "<h2>Before and after the strategy</h2>"
            "<p>Not enough sessions to compare yet — record at least one "
            "baseline session and one strategy session.</p>"
        )

    chart = _bars_svg(
        [s["hand_raises"] for s in sessions],
        [f"#{s['id']} {s['phase'][:4]}" for s in sessions],
    )
    return _page(title, compare + table + "<h2>Hand raises per session</h2>" + chart)


# -- mode 2: whole-class ------------------------------------------------------

def _mode2_block(db, session_id: int) -> str:
    info = db.get_session(session_id)
    minutes = db.mode2_data(session_id)
    if info is None:
        return f"<p>Session {session_id} was not found.</p>"
    total_raises = sum(m["hand_raises"] for m in minutes)
    typical_bodies = 0
    if minutes:
        counts = sorted(m["bodies_detected"] for m in minutes)
        typical_bodies = counts[len(counts) // 2]
    strip = _movement_strip([m["movement_bucket"] for m in minutes])
    return (
        f"<h2>Session {session_id} — class {escape(info['class_code'])}, "
        f"{escape(info['started_at'])}</h2>"
        f"<p class='compare'>Hand raises (class total): {total_raises}</p>"
        f"<p class='compare'>People in view (typical): {typical_bodies}</p>"
        f"<p class='compare'>Minutes observed: {len(minutes)}</p>"
        + strip
    )


def mode2_summary_html(db, session_id: int) -> str:
    return _page("Whole-class session summary", _mode2_block(db, session_id))


def mode2_compare_html(db, session_a: int, session_b: int) -> str:
    body = (
        "<div class='cols'><div>" + _mode2_block(db, session_a) + "</div>"
        "<div>" + _mode2_block(db, session_b) + "</div></div>"
    )
    return _page("Whole-class comparison", body)

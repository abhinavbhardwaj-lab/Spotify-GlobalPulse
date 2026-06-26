"""
Static dashboard generator for the global daily tracks chart.

Reads data/latest.json and data/history.json, writes docs/index.html.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = REPO_ROOT / "docs"


def _format_streams(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _format_duration(ms: int | None) -> str:
    if not ms:
        return ""
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"


def _rank_delta_badge(track_key: str, history: dict[str, Any], today: str) -> str:
    per = history.get("tracks", {}).get(track_key, {}).get("days", {})
    days = sorted(per.keys())
    if today not in days or len(days) < 2:
        return '<span class="badge neutral">NEW</span>'
    idx = days.index(today)
    if idx == 0:
        return '<span class="badge neutral">—</span>'
    prev = per[days[idx - 1]]["rank"]
    curr = per[today]["rank"]
    diff = prev - curr
    if diff > 0:
        return f'<span class="badge up">▲ {diff}</span>'
    if diff < 0:
        return f'<span class="badge down">▼ {abs(diff)}</span>'
    return '<span class="badge neutral">—</span>'


def _track_key(entry: dict[str, Any]) -> str:
    return entry.get("track_id") or entry.get("display_title", "")


def _track_card(entry: dict[str, Any], history: dict[str, Any], today: str, prominent: bool) -> str:
    sp = entry.get("spotify") or {}
    image = sp.get("album_image") or ""
    title = entry.get("display_title") or entry.get("title", "")
    artist = entry.get("display_artist") or entry.get("artist", "")
    popularity = sp.get("popularity") or 0
    duration = _format_duration(sp.get("duration_ms"))
    explicit = sp.get("explicit", False)
    url = sp.get("spotify_url") or "#"
    delta = _rank_delta_badge(_track_key(entry), history, today)
    streams = _format_streams(entry["daily_streams"])

    explicit_badge = '<span class="explicit">E</span>' if explicit else ""
    duration_badge = f'<span class="stat-chip" title="Track length">{duration}</span>' if duration else ""
    pop_badge = (
        f'<span class="stat-chip" title="Spotify popularity (0-100)">★ {popularity}</span>'
        if popularity else ""
    )

    klass = "card prominent" if prominent else "card compact"
    return f"""
    <a class="{klass}" href="{url}" target="_blank" rel="noopener">
      <div class="rank">#{entry['rank']}</div>
      <div class="art" style="background-image:url('{image}')"></div>
      <div class="meta">
        <div class="title">{title} {explicit_badge}</div>
        <div class="artist">{artist}</div>
        <div class="stats">
          <span class="stat-chip primary" title="Daily streams">{streams} streams</span>
          {pop_badge}
          {duration_badge}
        </div>
        <div class="delta">{delta}</div>
      </div>
    </a>
    """


def _movers(snapshot: list[dict[str, Any]], history: dict[str, Any], today: str) -> tuple[list[dict], list[dict]]:
    deltas: list[dict[str, Any]] = []
    for entry in snapshot:
        per = history.get("tracks", {}).get(_track_key(entry), {}).get("days", {})
        days = sorted(per.keys())
        if today not in days or len(days) < 2:
            continue
        idx = days.index(today)
        if idx == 0:
            continue
        prev_rank = per[days[idx - 1]]["rank"]
        diff = prev_rank - entry["rank"]
        if diff != 0:
            deltas.append({**entry, "delta": diff})
    risers = sorted(deltas, key=lambda x: -x["delta"])[:5]
    fallers = sorted(deltas, key=lambda x: x["delta"])[:5]
    return risers, fallers


def _mover_row(entry: dict[str, Any], kind: str) -> str:
    arrow = "▲" if kind == "up" else "▼"
    return f"""
      <li class="mover-row">
        <span class="mover-name">{entry.get('display_title', '')} <span class="mover-artist">— {entry.get('display_artist', '')}</span></span>
        <span class="mover-delta {kind}">{arrow} {abs(entry['delta'])}</span>
        <span class="mover-rank">#{entry['rank']}</span>
      </li>
    """



def _stream_climbers(snapshot, history, today, limit=20, min_streams=1_000_000):
    """Tracks with the biggest day-over-day percentage growth in daily streams."""
    climbers = []
    for entry in snapshot:
        key = _track_key(entry)
        per = history.get("tracks", {}).get(key, {}).get("days", {})
        days = sorted(per.keys())
        if today not in days or len(days) < 2:
            continue
        idx = days.index(today)
        if idx == 0:
            continue
        prev = per[days[idx - 1]]["daily_streams"]
        curr = per[today]["daily_streams"]
        if prev < 100_000 or curr < min_streams:
            continue
        pct = (curr - prev) / prev * 100
        if pct <= 0:
            continue
        climbers.append({**entry, "pct_change": pct, "stream_delta": curr - prev, "prev_streams": prev})
    return sorted(climbers, key=lambda x: -x["pct_change"])[:limit]


def _climber_card(entry):
    sp = entry.get("spotify") or {}
    image = sp.get("album_image") or ""
    title = entry.get("display_title") or entry.get("title", "")
    artist = entry.get("display_artist") or entry.get("artist", "")
    url = sp.get("spotify_url") or "#"
    pct = entry["pct_change"]
    streams = _format_streams(entry["daily_streams"])
    delta = _format_streams(entry["stream_delta"])
    return f"""
    <a class="climber-card" href="{url}" target="_blank" rel="noopener">
      <div class="climber-rank">#{entry['rank']}</div>
      <div class="climber-art" style="background-image:url('{image}')"></div>
      <div class="climber-meta">
        <div class="climber-title">{title}</div>
        <div class="climber-artist">{artist}</div>
      </div>
      <div class="climber-stats">
        <div class="climber-pct">+{pct:.0f}%</div>
        <div class="climber-sub">{streams} <span>(+{delta})</span></div>
      </div>
    </a>
    """


def build(snapshot_path: Path | None = None) -> Path:
    snapshot_path = snapshot_path or (DATA_DIR / "latest.json")
    history_path = DATA_DIR / "history.json"
    snapshot = json.loads(snapshot_path.read_text())
    history = (
        json.loads(history_path.read_text())
        if history_path.exists()
        else {"days": [], "tracks": {}}
    )

    today = snapshot["date"]
    tracks = snapshot.get("tracks") or snapshot.get("artists") or []
    top10 = tracks[:10]
    rest = tracks[10:50]

    risers, fallers = _movers(tracks, history, today)
    climbers = _stream_climbers(tracks, history, today)
    total_streams = sum(t["daily_streams"] for t in tracks)

    # avg track length from enriched tracks
    durations = [(t.get("spotify") or {}).get("duration_ms") for t in tracks]
    valid_durations = [d for d in durations if d]
    avg_duration_ms = sum(valid_durations) / len(valid_durations) if valid_durations else 0
    if avg_duration_ms:
        total_s = int(avg_duration_ms / 1000)
        avg_duration_label = f"{total_s // 60}:{total_s % 60:02d}"
    else:
        avg_duration_label = "\u2014"

    chart_labels = [t.get("display_title", "")[:24] for t in top10]
    chart_values = [t["daily_streams"] for t in top10]

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    html = TEMPLATE.format(
        date=today,
        generated=dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        track_count=len(tracks),
        total_streams=_format_streams(total_streams),
        avg_popularity=avg_duration_label,
        days_tracked=len(history.get("days", [])),
        top_cards="\n".join(_track_card(t, history, today, prominent=True) for t in top10),
        rest_cards="\n".join(_track_card(t, history, today, prominent=False) for t in rest),
        risers_list="\n".join(_mover_row(r, "up") for r in risers)
        or '<li class="empty">Need more days of data.</li>',
        fallers_list="\n".join(_mover_row(f, "down") for f in fallers)
        or '<li class="empty">Need more days of data.</li>',
        chart_labels=json.dumps(chart_labels),
        chart_values=json.dumps(chart_values),
        climber_cards="\n".join(_climber_card(c) for c in climbers) or '<div class="empty">Need at least 2 days of data to compute climbers.</div>',
    )
    out_path = DOCS_DIR / "index.html"
    out_path.write_text(html)
    logger.info("Dashboard written to %s", out_path)
    return out_path


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Spotify Global Pulse — Daily Top Tracks & Climbers</title>
<meta name="description" content="Daily snapshot of the world's top Spotify tracks. Track music streaming trends here. Top global streaming tracks and top global streaming climbers." />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0a0a0f;
    --surface: #12121a;
    --surface-2: #1a1a26;
    --border: #2a2a3a;
    --text: #f5f5f7;
    --muted: #8a8a9a;
    --accent: #1db954;
    --accent-glow: rgba(29, 185, 84, 0.25);
    --up: #1db954;
    --down: #ff4d6d;
    --neutral: #8a8a9a;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background:
      radial-gradient(1200px 600px at 80% -10%, rgba(29,185,84,0.15), transparent 60%),
      radial-gradient(800px 500px at -10% 30%, rgba(99,102,241,0.10), transparent 60%),
      var(--bg);
    color: var(--text);
    min-height: 100vh;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }}
  .wrap {{ max-width: 1280px; margin: 0 auto; padding: 48px 32px 96px; }}

  header {{ display: flex; justify-content: space-between; align-items: end; margin-bottom: 56px; gap: 32px; flex-wrap: wrap; }}
  .brand {{ display: flex; align-items: center; gap: 14px; }}
  .logo {{
    width: 44px; height: 44px; border-radius: 12px;
    background: linear-gradient(135deg, var(--accent), #14823a);
    display: grid; place-items: center; font-weight: 800; font-size: 22px;
    box-shadow: 0 8px 24px var(--accent-glow);
  }}
  h1 {{ font-size: 28px; font-weight: 800; letter-spacing: -0.02em; }}
  .tagline {{ color: var(--muted); font-size: 14px; margin-top: 2px; }}
  .meta-pill {{
    display: inline-flex; align-items: center; gap: 8px;
    padding: 8px 14px; border-radius: 999px;
    background: var(--surface); border: 1px solid var(--border);
    font-size: 13px; color: var(--muted);
  }}
  .dot {{ width: 8px; height: 8px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 12px var(--accent); animation: pulse 2s infinite; }}
  @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.4; }} }}

  .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 48px; }}
  .stat {{ background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 22px; }}
  .stat .label {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; }}
  .stat .value {{ font-size: 32px; font-weight: 800; margin-top: 6px; letter-spacing: -0.02em; }}
  .stat .sub {{ font-size: 12px; color: var(--muted); margin-top: 2px; }}

  section {{ margin-bottom: 56px; }}
  .section-header {{ display: flex; justify-content: space-between; align-items: end; margin-bottom: 20px; }}
  h2 {{ font-size: 20px; font-weight: 700; letter-spacing: -0.01em; }}
  h2 .hash {{ color: var(--accent); margin-right: 8px; }}
  .section-sub {{ font-size: 13px; color: var(--muted); }}

  .chart-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 28px; }}
  .chart-wrap {{ position: relative; height: 340px; }}

  .top-grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; }}
  .rest-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 16px; }}
  .card {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
    text-decoration: none; color: var(--text); position: relative; overflow: hidden;
    transition: transform .15s ease, border-color .15s ease, background .15s ease;
  }}
  .card.prominent {{ display: flex; flex-direction: column; }}
  .card.compact {{ display: flex; flex-direction: row; padding: 14px; gap: 14px; align-items: center; }}
  .card:hover {{ transform: translateY(-3px); border-color: var(--accent); background: var(--surface-2); }}
  .rank {{
    position: absolute; top: 10px; left: 10px; z-index: 2;
    background: rgba(0,0,0,0.7); backdrop-filter: blur(8px);
    padding: 4px 10px; border-radius: 8px; font-weight: 700; font-size: 13px;
  }}
  .card.compact .rank {{ position: static; background: transparent; padding: 0; min-width: 38px; text-align: center; color: var(--muted); }}
  .art {{
    background-size: cover; background-position: center; background-color: var(--surface-2);
  }}
  .card.prominent .art {{ width: 100%; padding-top: 100%; }}
  .card.compact .art {{ width: 56px; height: 56px; border-radius: 10px; flex-shrink: 0; }}
  .meta {{ display: flex; flex-direction: column; gap: 4px; min-width: 0; flex: 1; position: relative; }}
  .card.prominent .meta {{ padding: 14px 16px 18px; }}
  .title {{ font-weight: 700; font-size: 15px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .artist {{ font-size: 12px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .explicit {{ display: inline-block; font-size: 9px; font-weight: 700; padding: 1px 4px; background: var(--surface-2); border: 1px solid var(--border); border-radius: 3px; color: var(--muted); vertical-align: middle; }}
  .stats {{ display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px; }}
  .stat-chip {{
    font-size: 11px; padding: 3px 8px; border-radius: 6px;
    background: var(--surface-2); color: var(--muted);
    font-variant-numeric: tabular-nums; border: 1px solid var(--border);
    white-space: nowrap;
  }}
  .stat-chip.primary {{ color: var(--text); background: rgba(29,185,84,0.1); border-color: rgba(29,185,84,0.3); }}
  .delta {{ position: absolute; top: 0; right: 0; }}
  .card.prominent .delta {{ position: absolute; top: 12px; right: 12px; }}
  .card.compact .delta {{ position: static; }}
  .badge {{ font-size: 11px; padding: 3px 8px; border-radius: 999px; font-weight: 600; font-variant-numeric: tabular-nums; }}
  .badge.up {{ background: rgba(29,185,84,0.15); color: var(--up); }}
  .badge.down {{ background: rgba(255,77,109,0.15); color: var(--down); }}
  .badge.neutral {{ background: var(--surface-2); color: var(--neutral); }}

  .movers {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  .mover-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 24px; }}
  .mover-card h3 {{ font-size: 14px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 14px; }}
  .mover-row {{ display: grid; grid-template-columns: 1fr auto auto; gap: 12px; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--border); list-style: none; }}
  .mover-row:last-child {{ border-bottom: none; }}
  .mover-name {{ font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .mover-artist {{ color: var(--muted); font-weight: 400; }}
  .mover-delta.up {{ color: var(--up); font-weight: 600; font-variant-numeric: tabular-nums; }}
  .mover-delta.down {{ color: var(--down); font-weight: 600; font-variant-numeric: tabular-nums; }}
  .mover-rank {{ color: var(--muted); font-variant-numeric: tabular-nums; }}
  .empty {{ list-style: none; color: var(--muted); font-size: 13px; padding: 8px 0; }}

  footer {{ margin-top: 64px; padding-top: 32px; border-top: 1px solid var(--border); color: var(--muted); font-size: 13px; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 12px; }}
  footer a {{ color: var(--text); text-decoration: none; border-bottom: 1px dotted var(--border); }}
  footer a:hover {{ border-color: var(--accent); }}


  .climbers-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }}
  .climber-card {{
    display: grid; grid-template-columns: 40px 56px 1fr auto; gap: 14px; align-items: center;
    padding: 12px 16px; background: var(--surface); border: 1px solid var(--border);
    border-radius: 14px; text-decoration: none; color: var(--text);
    transition: transform .15s ease, border-color .15s ease, background .15s ease;
  }}
  .climber-card:hover {{ transform: translateY(-2px); border-color: var(--accent); background: var(--surface-2); }}
  .climber-rank {{ font-size: 13px; color: var(--muted); font-variant-numeric: tabular-nums; }}
  .climber-art {{ width: 56px; height: 56px; border-radius: 10px; background-size: cover; background-position: center; background-color: var(--surface-2); }}
  .climber-meta {{ min-width: 0; }}
  .climber-title {{ font-weight: 600; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .climber-artist {{ font-size: 12px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .climber-stats {{ text-align: right; }}
  .climber-pct {{ font-size: 18px; font-weight: 800; color: var(--accent); font-variant-numeric: tabular-nums; letter-spacing: -0.01em; }}
  .climber-sub {{ font-size: 11px; color: var(--muted); font-variant-numeric: tabular-nums; }}
  .climber-sub span {{ color: var(--accent); }}
  @media (max-width: 900px) {{ .climbers-grid {{ grid-template-columns: 1fr; }} }}

  @media (max-width: 900px) {{
    .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .top-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .rest-grid {{ grid-template-columns: 1fr; }}
    .movers {{ grid-template-columns: 1fr; }}
    .wrap {{ padding: 32px 20px 64px; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="brand">
      <div class="logo">P</div>
      <div>
        <h1>Spotify Global Pulse</h1>
        <div class="tagline">Daily snapshot of the world's top Spotify tracks. Track music streaming trends here. Top global streaming tracks and top global streaming climbers.</div>
      </div>
    </div>
    <div class="meta-pill"><span class="dot"></span> Updated {generated}</div>
  </header>

  <div class="stats-grid">
    <div class="stat">
      <div class="label">Snapshot Date</div>
      <div class="value">{date}</div>
      <div class="sub">Refreshed daily via GitHub Actions</div>
    </div>
    <div class="stat">
      <div class="label">Tracks Tracked</div>
      <div class="value">{track_count}</div>
      <div class="sub">Global daily chart, top {track_count}</div>
    </div>
    <div class="stat">
      <div class="label">Total Daily Streams</div>
      <div class="value">{total_streams}</div>
      <div class="sub">Across top {track_count} tracks</div>
    </div>
    <div class="stat">
      <div class="label">Avg. Track Length</div>
      <div class="value">{avg_popularity}</div>
      <div class="sub">Across top 50 · {days_tracked}d history</div>
    </div>
  </div>

  <section>
    <div class="section-header">
      <h2><span class="hash">#</span>Top 10 Tracks</h2>
      <span class="section-sub">Tap a card to play on Spotify</span>
    </div>
    <div class="top-grid">{top_cards}</div>
  </section>

  <section>
    <div class="section-header">
      <h2><span class="hash">#</span>Streams Distribution</h2>
      <span class="section-sub">Top 10 · daily streams</span>
    </div>
    <div class="chart-card">
      <div class="chart-wrap"><canvas id="streamsChart"></canvas></div>
    </div>
  </section>

  <section>
    <div class="section-header">
      <h2><span class="hash">#</span>Biggest Movers</h2>
      <span class="section-sub">Rank change vs. previous day</span>
    </div>
    <div class="movers">
      <div class="mover-card">
        <h3>↗ Climbing</h3>
        <ul>{risers_list}</ul>
      </div>
      <div class="mover-card">
        <h3>↘ Dropping</h3>
        <ul>{fallers_list}</ul>
      </div>
    </div>
  </section>

  <section>
    <div class="section-header">
      <h2><span class="hash">#</span>Top 20 Stream Climbers</h2>
      <span class="section-sub">Day-over-day growth in daily streams &middot; min 1M streams</span>
    </div>
    <div class="climbers-grid">{climber_cards}</div>
  </section>

  <section>
    <div class="section-header">
      <h2><span class="hash">#</span>Ranks 11–50</h2>
      <span class="section-sub">The long tail of today's chart</span>
    </div>
    <div class="rest-grid">{rest_cards}</div>
  </section>

  <footer>
    <div>Built by Spotify Pulse · Data from kworb.net & Spotify Web API · Refreshed at 06:00 UTC</div>
    <div><a href="https://github.com" target="_blank" rel="noopener">View on GitHub</a></div>
  </footer>
</div>

<script>
  const ctx = document.getElementById('streamsChart');
  new Chart(ctx, {{
    type: 'bar',
    data: {{
      labels: {chart_labels},
      datasets: [{{
        label: 'Daily Streams',
        data: {chart_values},
        backgroundColor: 'rgba(29, 185, 84, 0.85)',
        hoverBackgroundColor: '#1db954',
        borderRadius: 8,
        borderSkipped: false,
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          backgroundColor: '#1a1a26',
          borderColor: '#2a2a3a',
          borderWidth: 1,
          titleColor: '#f5f5f7',
          bodyColor: '#f5f5f7',
          padding: 12,
          callbacks: {{
            label: (c) => {{
              const v = c.parsed.y;
              if (v >= 1e9) return (v/1e9).toFixed(2) + 'B streams';
              if (v >= 1e6) return (v/1e6).toFixed(1) + 'M streams';
              return v.toLocaleString() + ' streams';
            }}
          }}
        }}
      }},
      scales: {{
        x: {{ grid: {{ display: false }}, ticks: {{ color: '#8a8a9a', font: {{ size: 10 }}, maxRotation: 45, minRotation: 45 }} }},
        y: {{
          grid: {{ color: 'rgba(255,255,255,0.05)' }},
          ticks: {{
            color: '#8a8a9a',
            callback: (v) => {{
              if (v >= 1e9) return (v/1e9).toFixed(1) + 'B';
              if (v >= 1e6) return (v/1e6).toFixed(0) + 'M';
              return v;
            }}
          }}
        }}
      }}
    }}
  }});
</script>
</body>
</html>
"""


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=None)
    args = parser.parse_args()
    try:
        build(args.snapshot)
    except Exception as exc:
        logger.exception("Dashboard generation failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

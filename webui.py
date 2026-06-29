import threading
import webbrowser
from http import HTTPStatus

from storage import get_summary, get_active_session, get_daily_breakdown


def _fmt(seconds):
    h, r = divmod(int(seconds), 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}h {m}m" if m else f"{h}h"
    return f"{m}m {s}s" if m else f"{s}s"


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Focus Tracker</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background: #f5f0eb; color: #3a3530;
    min-height: 100vh; padding: 32px 16px;
  }
  .container {
    width: 100%; max-width: 640px; margin: 0 auto;
    background: #fcf9f6; border-radius: 12px;
    border: 1px solid #e8e0d6; padding: 28px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  }
  .header {
    display: flex; justify-content: space-between; align-items: flex-start;
    margin-bottom: 16px;
  }
  .header-left { display: flex; align-items: center; gap: 10px; }
  .header-left h1 { font-size: 17px; font-weight: 600; color: #2c2824; }
  .header-left .sub { font-size: 12px; color: #9a8e82; margin-top: 1px; }
  .total-row { font-size: 13px; color: #7a7268; margin-bottom: 16px; padding: 8px 12px; background: #f5f0eb; border-radius: 8px; }
  .total-row strong { color: #3a3530; }
  .status-badge {
    display: inline-flex; align-items: center; gap: 5px;
    font-size: 11px; background: #f5f0eb; padding: 3px 10px;
    border-radius: 12px; border: 1px solid #e8e0d6; white-space: nowrap;
  }
  .dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
  .dot.active { background: #4a8; }
  .dot.inactive { background: #d4cdc4; }
  .sort-bar {
    display: flex; gap: 4px; margin-bottom: 10px; flex-wrap: wrap;
  }
  .sort-btn {
    font-size: 11px; padding: 4px 10px; border-radius: 6px;
    border: 1px solid #e8e0d6; background: #f5f0eb; color: #7a7268;
    cursor: pointer; font-family: inherit; transition: all .15s;
  }
  .sort-btn:hover { border-color: #d4cdc4; background: #ede7e0; }
  .sort-btn.active { background: #3a3530; color: #fcf9f6; border-color: #3a3530; }
  .sort-btn .arrow { margin-left: 3px; }
  .empty-state { text-align: center; padding: 48px 0; color: #b5aaa0; }
  .empty-state p { font-size: 14px; }
  .cards { display: flex; flex-direction: column; gap: 5px; }
  .card {
    background: #fcf9f6; border-radius: 10px;
    border: 1px solid #ede7e0; padding: 14px 16px;
    display: flex; align-items: center; gap: 14px;
    cursor: pointer; user-select: none;
    transition: border-color .15s;
  }
  .card:hover { border-color: #ddd4ca; }
  .app-icon {
    width: 36px; height: 36px; border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 16px; flex-shrink: 0; border: 1px solid #e8e0d6;
  }
  .card-body { flex: 1; min-width: 0; }
  .app-name { font-size: 14px; font-weight: 500; color: #3a3530; }
  .time-row { display: flex; gap: 14px; margin-top: 5px; flex-wrap: wrap; }
  .time-label { font-size: 10px; color: #b5aaa0; text-transform: uppercase; letter-spacing: .03em; }
  .time-value { font-size: 13px; color: #5a534b; }
  .bar-track { margin-top: 7px; height: 3px; background: #ede7e0; border-radius: 4px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 4px; transition: width .5s ease; }
  .daily-detail {
    display: none; margin: 4px 12px 2px 64px; padding: 10px 14px;
    background: #f5f0eb; border-radius: 8px;
  }
  .daily-detail.open { display: block; }
  .daily-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 4px 0; font-size: 12px;
  }
  .daily-row + .daily-row { border-top: 1px solid #ede7e0; }
  .daily-row .day { color: #5a534b; font-weight: 500; }
  .daily-row .dur { color: #7a7268; }
  .daily-bar-track { height: 3px; background: #ede7e0; border-radius: 4px; overflow: hidden; margin-top: 2px; }
  .daily-bar-fill { height: 100%; border-radius: 4px; }
  .footer { margin-top: 16px; display: flex; justify-content: space-between; align-items: center; }
  .live-label { font-size: 11px; color: #b5aaa0; }
  .live-label.active { color: #4a8; }
  .db-label { font-size: 10px; color: #d4cdc4; }
  @media (max-width: 420px) {
    .container { padding: 16px; }
    .header { flex-direction: column; gap: 10px; }
    .time-row { gap: 10px; }
    .daily-detail { margin-left: 50px; }
  }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="header-left">
      <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="10" r="8" stroke="#b5aaa0" stroke-width="1.5"/>
        <path d="M10 5.5V10l3 2.5" stroke="#b5aaa0" stroke-width="1.5" stroke-linecap="round"/>
      </svg>
      <div>
        <h1>Focus Tracker</h1>
        <div class="sub">which apps have your attention</div>
      </div>
    </div>
    <div id="status-badge" class="status-badge">
      <span class="dot" id="status-dot"></span>
      <span id="status-text">Loading...</span>
    </div>
  </div>

  <div id="total-row" class="total-row"></div>

  <div class="sort-bar" id="sort-bar">
    <button class="sort-btn active" data-sort="total">Total <span class="arrow">↓</span></button>
    <button class="sort-btn" data-sort="today">Today <span class="arrow"></span></button>
    <button class="sort-btn" data-sort="week">Week <span class="arrow"></span></button>
  </div>

  <div id="content">
    <div class="empty-state" id="empty-state">
      <p>No tracking data yet — start tracking first</p>
    </div>
    <div id="cards-container"></div>
  </div>

  <div class="footer">
    <span id="live-label" class="live-label">○ Checking...</span>
    <span id="db-label" class="db-label"></span>
  </div>
</div>

<script>
const COLORS = ["#d48c6b","#7aa89f","#b892c4","#c48a7a","#8fb0c7","#c4a57a","#9ab87a","#c47a94","#7ab8a8","#b8a07a"];
const ICONS = ["⚡","✨","\U0001f4c1","\U0001f4ac","\U0001f310","\U0001f4dd","\U0001f3b5","\U0001f4f7","\U0001f3ae","\U0001f527","\U0001f4ca","\U0001f4e7","⚙️","\U0001f50d","\U0001f4f0","\U0001f3ac","\U0001f4a1","\U0001f4bb","\U0001f4f1","\U0001f4c8"];
const PALETTE = new Map();
const DAY_NAMES = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];

let sortKey = "total";
let sortDesc = true;
let appsData = [];
let breakdownData = {};
let openApp = null;

function pickColor(app) {
  if (!PALETTE.has(app)) {
    let i = PALETTE.size % COLORS.length;
    PALETTE.set(app, { bg: "#f0eae4", fg: COLORS[i], icon: ICONS[PALETTE.size % ICONS.length] });
  }
  return PALETTE.get(app);
}

function fmt(s) {
  const h = Math.floor(s / 3600), r = s % 3600, m = Math.floor(r / 60), sec = Math.floor(r % 60);
  let parts = [];
  if (h) parts.push(h + "h");
  if (m) parts.push(m + "m");
  parts.push(sec + "s");
  return parts.join(" ");
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function maxTime(apps) {
  let m = 0;
  const key = sortKey === "today" ? "today" : sortKey === "week" ? "week" : "total";
  for (const a of apps) if (a[key] > m) m = a[key];
  return m || 1;
}

function render() {
  const apps = [...appsData];
  const key = sortKey === "today" ? "today" : sortKey === "week" ? "week" : "total";
  apps.sort((a, b) => sortDesc ? b[key] - a[key] : a[key] - b[key]);

  const status = window._status;
  const dot = document.getElementById("status-dot");
  const stxt = document.getElementById("status-text");
  const live = document.getElementById("live-label");
  if (status?.tracking) {
    dot.className = "dot active";
    stxt.textContent = status.app_name;
    live.className = "live-label active";
    live.textContent = "● Live";
  } else {
    dot.className = "dot inactive";
    stxt.textContent = "Idle";
    live.className = "live-label";
    live.textContent = "○ Idle";
  }

  const totalSecs = apps.reduce((s, a) => s + a.total, 0);
  document.getElementById("total-row").innerHTML = "<strong>" + fmt(totalSecs) + "</strong> tracked across " + apps.length + " app" + (apps.length !== 1 ? "s" : "");

  const empty = document.getElementById("empty-state");
  const container = document.getElementById("cards-container");
  if (!apps.length) {
    empty.style.display = "block";
    container.innerHTML = "";
    return;
  }
  empty.style.display = "none";

  const max = maxTime(apps);
  container.innerHTML = apps.map(a => {
    const c = pickColor(a.app);
    const pct = Math.max(3, (a[key] / max) * 100);
    const isOpen = openApp === a.app;
    const daily = breakdownData[a.app] || [];
    const dailyMax = daily.length ? Math.max(...daily.map(d => d.secs)) : 1;
    const detailRows = daily.length ? daily.map(d => {
      const dpct = Math.max(3, (d.secs / dailyMax) * 100);
      return '<div class="daily-row">' +
        '<span class="day">' + d.day + '</span>' +
        '<span class="dur">' + fmt(d.secs) + '</span>' +
        '</div><div class="daily-bar-track"><div class="daily-bar-fill" style="width:' + dpct + '%;background:' + c.fg + '"></div></div>';
    }).join("") : '<div class="daily-row"><span class="day" style="color:#b5aaa0">No data for last 7 days</span></div>';

    return '<div class="card" onclick="toggleDetail(' + JSON.stringify(a.app) + ')">' +
      '<div class="app-icon" style="background:' + c.bg + ';color:' + c.fg + '">' + c.icon + '</div>' +
      '<div class="card-body">' +
        '<div class="app-name">' + esc(a.app) + '</div>' +
        '<div class="time-row">' +
          '<div><div class="time-label">Today</div><div class="time-value">' + fmt(a.today) + '</div></div>' +
          '<div><div class="time-label">Week</div><div class="time-value">' + fmt(a.week) + '</div></div>' +
          '<div><div class="time-label">All time</div><div class="time-value">' + fmt(a.total) + '</div></div>' +
        '</div>' +
        '<div class="bar-track"><div class="bar-fill" style="width:' + pct + '%;background:' + c.fg + '"></div></div>' +
      '</div></div>' +
      '<div class="daily-detail' + (isOpen ? ' open' : '') + '" id="detail-' + a.app.replace(/ /g, '_') + '">' + detailRows + '</div>';
  }).join("");
}

function toggleDetail(app) {
  openApp = openApp === app ? null : app;
  render();
}

async function fetchData() {
  try {
    const [sr, br] = await Promise.all([
      fetch("/api/summary").then(r => r.json()),
      fetch("/api/breakdown").then(r => r.json()),
    ]);
    appsData = sr.apps;
    window._status = sr.status;
    breakdownData = {};
    for (const [day, app, secs] of br.breakdown) {
      if (!breakdownData[app]) breakdownData[app] = [];
      breakdownData[app].push({ day, secs });
    }
    for (const app of Object.keys(breakdownData)) {
      breakdownData[app].sort((a, b) => a.day.localeCompare(b.day));
    }
    render();
  } catch {}
}

document.getElementById("sort-bar").addEventListener("click", function(e) {
  const btn = e.target.closest(".sort-btn");
  if (!btn) return;
  const key = btn.dataset.sort;
  if (key === sortKey) {
    sortDesc = !sortDesc;
  } else {
    sortKey = key;
    sortDesc = true;
  }
  document.querySelectorAll(".sort-btn").forEach(b => {
    b.classList.toggle("active", b.dataset.sort === sortKey);
    b.querySelector(".arrow").textContent = b.dataset.sort === sortKey ? (sortDesc ? "↓" : "↑") : "";
  });
  render();
});

const dbLabel = document.getElementById("db-label");
fetch("/api/info").then(r => r.json()).then(d => { dbLabel.textContent = d.db; }).catch(() => {});
fetchData();
setInterval(fetchData, 3000);
</script>
</body>
</html>"""


def make_app():
    from flask import Flask, jsonify

    app = Flask(__name__)

    @app.route("/")
    def index():
        return HTML, HTTPStatus.OK, {"Content-Type": "text/html; charset=utf-8"}

    @app.route("/api/summary")
    def api_summary():
        summary = get_summary()
        all_apps = sorted(
            set(list(summary["today"].keys()) + list(summary["week"].keys()) + list(summary["all_time"].keys()))
        )
        apps = []
        for app in all_apps:
            apps.append({
                "app": app,
                "today": summary["today"].get(app, 0),
                "week": summary["week"].get(app, 0),
                "total": summary["all_time"].get(app, 0),
            })

        session = get_active_session()
        status = {"tracking": False}
        if session:
            status = {"tracking": True, "app_name": session["app_name"], "window_title": session.get("window_title")}

        return jsonify({"apps": apps, "status": status})

    @app.route("/api/breakdown")
    def api_breakdown():
        return jsonify({"breakdown": get_daily_breakdown(7)})

    @app.route("/api/info")
    def api_info():
        from config import DB_PATH
        from storage import _connect
        conn = _connect()
        cur = conn.execute("SELECT COUNT(*), COALESCE(SUM(duration_seconds),0) FROM sessions")
        count, total = cur.fetchone()
        conn.close()
        return jsonify({"db": str(DB_PATH), "sessions": count, "total_seconds": round(total)})

    return app


def start_webui():
    app = make_app()
    port = 5792
    url = f"http://127.0.0.1:{port}"

    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    print(f"Opening report at {url}")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    start_webui()

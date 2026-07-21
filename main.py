import argparse
import os
import subprocess
import sys

import tracker
from detector import get_active_window
from storage import get_active_session

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def cmd_start():
    if tracker.is_tracking():
        print("Already tracking.")
        return
    proc = subprocess.Popen(
        [sys.executable, "-m", "tracker"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        cwd=_PROJECT_DIR,
    )
    print(f"Started tracking (pid {proc.pid}).")


def cmd_stop():
    if not tracker.is_tracking():
        print("Not tracking.")
        return
    tracker.stop_tracking()
    print("Stopped tracking.")


def cmd_status():
    if not tracker.is_tracking():
        print("Not tracking.")
        return
    session = get_active_session()
    if session:
        print(f"Currently tracking: {session['app_name']}")
        if session["window_title"]:
            print(f"Window: {session['window_title']}")
    else:
        app_name, title = get_active_window()
        if app_name:
            print(f"Current active app: {app_name}")
        else:
            print("Tracking active, waiting for window focus.")


def cmd_report():
    from webui import start_webui
    start_webui()


def cmd_display():
    from storage import get_summary, get_active_session

    summary = get_summary()
    all_apps = sorted(
        set(
            list(summary["today"].keys())
            + list(summary["fortnight"].keys())
            + list(summary["week"].keys())
            + list(summary["month"].keys())
            + list(summary["all_time"].keys())
        )
    )

    if not all_apps:
        print("No tracking data yet.")
        return

    today_totals = summary["today"]

    def _fmt(seconds):
        h, r = divmod(int(seconds), 3600)
        m, s = divmod(r, 60)
        return f"{h}:{m:02d}:{s:02d}"

    rows = []
    for app in all_apps:
        today_secs = today_totals.get(app, 0)
        if not today_secs:
            continue
        rows.append(
            (
                app,
                today_secs,
                today_secs,
                summary["fortnight"].get(app, 0),
                summary["all_time"].get(app, 0),
            )
        )

    rows.sort(key=lambda r: (-r[1], r[0]))

    if not rows:
        print("Nothing tracked today.")
        return

    tot_today = sum(r[2] for r in rows)
    tot_fortnight = sum(r[3] for r in rows)
    tot_all = sum(r[4] for r in rows)

    pad = max(len(r[0]) for r in rows) + 1

    print()
    print("  Focus Tracker")
    print()
    fmt_hdr = "  {:<{pad}}  {:>9}  {:>9}  {:>9}"
    sep = "  " + "─" * (pad + 33)
    print(fmt_hdr.format("App", "Today", "2 Weeks", "All", pad=pad))
    print(sep)
    for app, _, td, fn, al in rows:
        print(fmt_hdr.format(app, _fmt(td), _fmt(fn), _fmt(al), pad=pad))
    print(sep)
    print(fmt_hdr.format("Total", _fmt(tot_today), _fmt(tot_fortnight), _fmt(tot_all), pad=pad))

    session = get_active_session()
    if session:
        print(f"\n  Currently tracking: {session['app_name']}")
    else:
        print("\n  Not tracking.")
    print()


def main():
    parser = argparse.ArgumentParser(description="Focus Time Tracker")
    parser.add_argument("command", choices=["start", "stop", "status", "report", "display"])
    args = parser.parse_args()

    commands = {
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "report": cmd_report,
        "display": cmd_display,
    }
    commands[args.command]()


if __name__ == "__main__":
    main()

import argparse
import contextlib
import io
import os
import subprocess
import sys
import time

import tracker
from detector import get_active_window
from storage import get_active_session

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Console code pages on Windows (e.g. cp932) cannot encode window titles with
# non-ASCII characters, so replace what the stream cannot represent.
try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, OSError):
    pass


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


def cmd_display(all_mode=False):
    from datetime import datetime
    from storage import get_summary, get_active_session, get_today_start

    summary = get_summary()
    session = get_active_session()

    def _active_footer():
        if session:
            return f"Currently tracking: {session['app_name']}"
        return "Not tracking."

    def _fmt(seconds):
        h, r = divmod(int(seconds), 3600)
        m, s = divmod(r, 60)
        return f"{h}:{m:02d}:{s:02d}"

    if all_mode:
        all_apps = sorted(
            set(
                list(summary["today"].keys())
                + list(summary["fortnight"].keys())
                + list(summary["week"].keys())
                + list(summary["month"].keys())
                + list(summary["all_time"].keys())
            )
        )

        today_totals = summary["today"]

        rows = []
        for app in all_apps:
            today_secs = today_totals.get(app, 0)
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
            print("No tracking data yet.")
            return

        tot_today = sum(r[2] for r in rows)
        tot_fortnight = sum(r[3] for r in rows)
        tot_all = sum(r[4] for r in rows)

        pad = max(len(r[0]) for r in rows) + 1

        print()
        print(f"  {_active_footer()}")
        print()
        fmt_hdr = "  {:<{pad}}  {:>9}  {:>9}  {:>9}"
        sep = "  " + "─" * (pad + 33)
        print(fmt_hdr.format("App", "Today", "2 Weeks", "All", pad=pad))
        print(sep)
        for app, _, td, fn, al in rows:
            print(fmt_hdr.format(app, _fmt(td), _fmt(fn), _fmt(al), pad=pad))
        print(sep)
        print(fmt_hdr.format("Total", _fmt(tot_today), _fmt(tot_fortnight), _fmt(tot_all), pad=pad))
        print()
        return

    all_apps = sorted(
        set(list(summary["today"].keys()) + list(summary["yesterday"].keys()))
    )

    if not all_apps:
        print("No tracking data yet.")
        return

    today_totals = summary["today"]
    yesterday_totals = summary["yesterday"]

    # Only show apps opened today in this view; yesterday-only apps are hidden.
    all_apps = [a for a in all_apps if today_totals.get(a, 0)]

    if not all_apps:
        print("Nothing tracked today.")
        return

    rows = []
    for app in all_apps:
        today_secs = today_totals.get(app, 0)
        yesterday_secs = yesterday_totals.get(app, 0)
        rows.append((app, today_secs, yesterday_secs))

    rows.sort(key=lambda r: (-r[1], -r[2], r[0]))

    tot_today = sum(r[1] for r in rows)
    tot_yesterday = sum(r[2] for r in rows)

    first_ts = get_today_start()
    since_label = "App"
    if first_ts:
        since_label = "Since " + datetime.fromtimestamp(first_ts).strftime("%H:%M")

    pad = max(len(r[0]) for r in rows + [("", since_label)]) + 1

    print()
    print(f"  {_active_footer()}")
    print()
    fmt_hdr = "  {:<{pad}}  {:>9}  {:>9}"
    sep = "  " + "─" * (pad + 22)
    print(fmt_hdr.format(since_label, "Today", "Yesterday", pad=pad))
    print(sep)
    for app, td, yd in rows:
        print(fmt_hdr.format(app, _fmt(td), _fmt(yd), pad=pad))
    print(sep)
    print(fmt_hdr.format("Total", _fmt(tot_today), _fmt(tot_yesterday), pad=pad))
    print()


def _live_frame(use_all):
    """Render one frame to a string. Must not print: the caller owns the alt screen."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cmd_display(all_mode=use_all)
    return buf.getvalue()


def cmd_live(use_all=False, interval=1.0):
    if not sys.stdout.isatty():
        print("Live view needs an interactive terminal.")
        return

    # Redirecting the render instead of clearing the visible screen means we only
    # ever write inside the alternate screen buffer; the user's scrollback and
    # previous output are restored untouched on exit.
    sys.stdout.write("\033[?1049h")
    sys.stdout.flush()

    try:
        prev_rows = 0
        cols = 0
        while True:
            frame = _live_frame(use_all)
            now = time.strftime("%H:%M:%S")
            header = f"  live  {now}   ctrl-c to exit"
            lines = [header] + frame.splitlines()

            # Cursor-position each row and erase to end of line instead of
            # clearing the screen: a full \033[2J redraw blanks the window and
            # repaints it, which reads as a flicker. Writing over the previous
            # frame in place leaves stale cells untouched, so each line is
            # padded to the previous frame's width and truncated to it.
            out = []
            for i, line in enumerate(lines):
                row = "\033[%d;1H" % (i + 1)
                text = line[:max(cols, len(line))] if cols else line
                out.append(row + text + "\033[K")
            # Clear rows left over from a frame that had more lines.
            for i in range(len(lines), prev_rows):
                out.append("\033[%d;1H\033[K" % (i + 1))

            sys.stdout.write("\033[H" + "".join(out))
            sys.stdout.flush()

            prev_rows = len(lines)
            cols = max(len(line) for line in lines)
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?1049l")
        sys.stdout.flush()

    # ctrl-c in the live view should drop the user back to an interactive shell
    # with tracking running, so start it again here. This deliberately does not
    # touch a tracker the user stopped on purpose: cmd_start() no-ops when one
    # is already running, and a stop *while live* is a git-bash-only path where
    # the pid file and process are still there for is_tracking() to find.
    print()
    cmd_start()


def main():
    parser = argparse.ArgumentParser(description="Focus Time Tracker")
    parser.add_argument(
        "command", choices=["start", "stop", "status", "report", "display", "live"]
    )
    parser.add_argument("--all", action="store_true", help="display: show the full multi-period view")
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="live: seconds between refreshes (default 1.0)",
    )
    args = parser.parse_args()

    commands = {
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "report": cmd_report,
        "display": lambda: cmd_display(all_mode=args.all),
        "live": lambda: cmd_live(use_all=args.all, interval=args.interval),
    }
    commands[args.command]()


if __name__ == "__main__":
    main()

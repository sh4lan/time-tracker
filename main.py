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
    from report import show_report
    show_report()


def main():
    parser = argparse.ArgumentParser(description="Focus Time Tracker")
    parser.add_argument("command", choices=["start", "stop", "status", "report"])
    args = parser.parse_args()

    commands = {
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "report": cmd_report,
    }
    commands[args.command]()


if __name__ == "__main__":
    main()

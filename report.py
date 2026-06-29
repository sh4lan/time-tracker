import tkinter as tk
import tkinter.ttk as ttk
from storage import get_summary, DB_PATH


def _fmt(seconds):
    h, r = divmod(int(seconds), 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}h {m}m"
    return f"{m}m {s}s"


def show_report():
    summary = get_summary()

    root = tk.Tk()
    root.title("Focus Time Tracker")
    root.geometry("600x400")

    frame = ttk.Frame(root, padding=10)
    frame.pack(fill=tk.BOTH, expand=True)

    tree = ttk.Treeview(frame, columns=("today", "week", "all"), show="tree headings")
    tree.heading("#0", text="Application")
    tree.heading("today", text="Today")
    tree.heading("week", text="This Week")
    tree.heading("all", text="All Time")
    tree.column("#0", width=200)
    tree.column("today", width=120, anchor=tk.CENTER)
    tree.column("week", width=120, anchor=tk.CENTER)
    tree.column("all", width=120, anchor=tk.CENTER)

    apps = sorted(
        set(list(summary["today"].keys()) + list(summary["week"].keys()) + list(summary["all_time"].keys()))
    )

    for app in apps:
        tree.insert(
            "",
            tk.END,
            text=app,
            values=(
                _fmt(summary["today"].get(app, 0)),
                _fmt(summary["week"].get(app, 0)),
                _fmt(summary["all_time"].get(app, 0)),
            ),
        )

    tree.pack(fill=tk.BOTH, expand=True)

    btn_frame = ttk.Frame(frame)
    btn_frame.pack(fill=tk.X, pady=(10, 0))

    ttk.Label(btn_frame, text=f"DB: {DB_PATH}", font=("", 8)).pack(side=tk.LEFT)

    def refresh():
        for row in tree.get_children():
            tree.delete(row)
        summary = get_summary()
        apps = sorted(
            set(list(summary["today"].keys()) + list(summary["week"].keys()) + list(summary["all_time"].keys()))
        )
        for app in apps:
            tree.insert(
                "",
                tk.END,
                text=app,
                values=(
                    _fmt(summary["today"].get(app, 0)),
                    _fmt(summary["week"].get(app, 0)),
                    _fmt(summary["all_time"].get(app, 0)),
                ),
            )

    ttk.Button(btn_frame, text="Refresh", command=refresh).pack(side=tk.RIGHT, padx=(5, 0))
    ttk.Button(btn_frame, text="Quit", command=root.destroy).pack(side=tk.RIGHT)

    root.mainloop()

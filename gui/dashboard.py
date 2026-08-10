"""Day 14: Tkinter dashboard that doubles as an IOChannel.

The Tk root and all widgets live on the main thread. The interaction session
runs on a worker thread and talks to this channel through a queue (input) and
root.after callbacks (output), so nothing touches Tk off the main thread.
Optional pystray tray icon is used only if pystray + Pillow are installed.
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import scrolledtext

from config.settings import Settings
from core.base import BaseModule
from core.io.base import IOChannel


class GuiDashboard(BaseModule, IOChannel):
    def __init__(self, settings: Settings, brain=None, memory=None) -> None:
        BaseModule.__init__(self, name="gui")
        self.settings = settings
        self.cfg = settings.gui
        self.brain = brain
        self.memory = memory

        self._input_q: "queue.Queue[str | None]" = queue.Queue()
        self._answer_event = threading.Event()
        self._answer: str = ""
        self._awaiting = False
        self._closed = False

        self._root: tk.Tk | None = None
        self._transcript: scrolledtext.ScrolledText | None = None
        self._entry: tk.Entry | None = None
        self._status_var: tk.StringVar | None = None
        self._recent_box: tk.Text | None = None
        self._tray = None

    # ---- lifecycle (main thread) ------------------------------------------

    def initialize(self) -> None:
        self._build_ui()
        self.mark_ready()
        self.log.info("GUI dashboard ready.")

    def _build_ui(self) -> None:
        c = self.cfg
        root = tk.Tk()
        root.title(c.title)
        root.geometry(f"{c.width}x{c.height}")
        root.configure(bg=c.bg)
        root.minsize(560, 420)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        header = tk.Frame(root, bg=c.panel)
        header.pack(fill="x", side="top")
        tk.Label(
            header, text=f"{self.settings.app_name}",
            bg=c.panel, fg=c.accent,
            font=(c.font_family, c.font_size + 6, "bold"),
        ).pack(side="left", padx=12, pady=8)
        self._status_var = tk.StringVar(value="starting ...")
        tk.Label(
            header, textvariable=self._status_var, bg=c.panel, fg=c.muted,
            font=(c.font_family, c.font_size - 1),
        ).pack(side="right", padx=12)

        body = tk.Frame(root, bg=c.bg)
        body.pack(fill="both", expand=True, padx=10, pady=(8, 4))

        self._transcript = scrolledtext.ScrolledText(
            body, wrap="word", bg=c.panel, fg=c.text, insertbackground=c.text,
            font=(c.font_family, c.font_size), relief="flat", borderwidth=0, padx=10, pady=8,
        )
        self._transcript.pack(side="left", fill="both", expand=True)
        self._transcript.tag_config("user", foreground=c.user_color,
                                    font=(c.font_family, c.font_size, "bold"))
        self._transcript.tag_config("jarvis", foreground=c.accent)
        self._transcript.tag_config("error", foreground=c.error_color)
        self._transcript.tag_config("muted", foreground=c.muted)
        self._transcript.configure(state="disabled")

        side = tk.Frame(body, bg=c.bg, width=190)
        side.pack(side="right", fill="y", padx=(8, 0))
        side.pack_propagate(False)
        tk.Label(side, text="Recent actions", bg=c.bg, fg=c.muted,
                 font=(c.font_family, c.font_size - 1, "bold")).pack(anchor="w", pady=(2, 4))
        self._recent_box = tk.Text(side, bg=c.panel, fg=c.muted, relief="flat",
                                   font=(c.font_family, c.font_size - 2), width=24)
        self._recent_box.pack(fill="both", expand=True)
        self._recent_box.configure(state="disabled")

        bottom = tk.Frame(root, bg=c.bg)
        bottom.pack(fill="x", side="bottom", padx=10, pady=(0, 10))
        self._entry = tk.Entry(bottom, bg=c.panel, fg=c.text, insertbackground=c.accent,
                               relief="flat", font=(c.font_family, c.font_size + 1))
        self._entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 8))
        self._entry.bind("<Return>", lambda _e: self._on_send())
        self._entry.focus_set()
        tk.Button(bottom, text="Send", command=self._on_send, bg=c.accent, fg=c.bg,
                  activebackground=c.accent, relief="flat",
                  font=(c.font_family, c.font_size, "bold"), padx=16).pack(side="right")

        self._root = root
        self._refresh()

    # ---- IOChannel (worker thread) ----------------------------------------

    def get_command(self) -> str | None:
        return self._input_q.get()

    def send(self, text: str) -> None:
        if self._root is not None and not self._closed:
            self._root.after(0, lambda: self._append("JARVIS", text, "jarvis"))

    def ask(self, prompt: str) -> str:
        if self._root is None or self._closed:
            return ""
        self._answer = ""
        self._awaiting = True
        self._answer_event.clear()
        self._root.after(0, lambda: self._append("JARVIS", prompt, "jarvis"))
        self._answer_event.wait()
        return self._answer

    # ---- UI callbacks (main thread) ---------------------------------------

    def _on_send(self) -> None:
        if self._entry is None:
            return
        text = self._entry.get().strip()
        self._entry.delete(0, "end")
        if not text:
            return
        self._append("You", text, "user")
        if self._awaiting:
            self._answer = text
            self._awaiting = False
            self._answer_event.set()
        else:
            self._input_q.put(text)

    def _append(self, sender: str, text: str, tag: str) -> None:
        box = self._transcript
        if box is None:
            return
        box.configure(state="normal")
        box.insert("end", f"{sender}  ", (tag,))
        body_tag = "error" if tag == "error" else "muted" if tag == "muted" else ""
        box.insert("end", f"{text}\n", (body_tag,) if body_tag else ())
        box.configure(state="disabled")
        box.see("end")

    def _refresh(self) -> None:
        if self._root is None or self._closed:
            return
        ai = "on" if (self.brain and self.brain.is_ready) else "off"
        mem = "on" if (self.memory and self.memory.is_ready) else "off"
        if self._status_var is not None:
            self._status_var.set(f"v{self.settings.version}   AI: {ai}   Memory: {mem}")
        self._render_recent()
        self._root.after(self.cfg.refresh_ms, self._refresh)

    def _render_recent(self) -> None:
        if self._recent_box is None:
            return
        lines: list[str] = []
        if self.memory is not None and self.memory.is_ready:
            try:
                for record in self.memory.store.recent_actions(10):
                    target = f" {record.target}" if record.target else ""
                    lines.append(f"• {record.command}{target}")
            except Exception:  # noqa: BLE001
                pass
        self._recent_box.configure(state="normal")
        self._recent_box.delete("1.0", "end")
        self._recent_box.insert("end", "\n".join(lines) if lines else "—")
        self._recent_box.configure(state="disabled")

    # ---- close / tray ------------------------------------------------------

    def _on_close(self) -> None:
        if self._tray is not None:
            self._root.withdraw()  # minimize to tray, keep session alive
        else:
            self._quit()

    def _quit(self) -> None:
        self._closed = True
        self._input_q.put(None)
        if self._awaiting:
            self._answer = ""
            self._awaiting = False
            self._answer_event.set()
        self._stop_tray()
        if self._root is not None:
            try:
                self._root.quit()
                self._root.destroy()
            except tk.TclError:
                pass

    def signal_close(self) -> None:
        self._closed = True
        self._input_q.put(None)
        if self._awaiting:
            self._answer_event.set()

    def _build_tray(self):
        if not self.cfg.enable_tray:
            return None
        try:
            import pystray
            from PIL import Image, ImageDraw
        except Exception:  # noqa: BLE001
            self.log.info("pystray/Pillow not installed; running without tray icon.")
            return None

        image = Image.new("RGB", (64, 64), self.cfg.bg.lstrip("#") and self.cfg.bg)
        draw = ImageDraw.Draw(image)
        draw.ellipse((14, 14, 50, 50), fill=self.cfg.accent)

        def _show(_icon=None, _item=None) -> None:
            if self._root is not None:
                self._root.after(0, self._root.deiconify)

        def _hide(_icon=None, _item=None) -> None:
            if self._root is not None:
                self._root.after(0, self._root.withdraw)

        def _exit(_icon=None, _item=None) -> None:
            if self._root is not None:
                self._root.after(0, self._quit)

        menu = pystray.Menu(
            pystray.MenuItem("Show", _show, default=True),
            pystray.MenuItem("Hide", _hide),
            pystray.MenuItem("Quit", _exit),
        )
        return pystray.Icon("jarvis", image, self.settings.app_name, menu)

    def _start_tray(self) -> None:
        self._tray = self._build_tray()
        if self._tray is not None:
            threading.Thread(target=self._tray.run, daemon=True).start()
            self.log.info("System tray icon active.")

    def _stop_tray(self) -> None:
        if self._tray is not None:
            try:
                self._tray.stop()
            except Exception:  # noqa: BLE001
                pass
            self._tray = None

    # ---- main-thread loop --------------------------------------------------

    def run_mainloop(self) -> None:
        if self._root is None:
            raise RuntimeError("GuiDashboard.initialize() not called.")
        self._start_tray()
        try:
            self._root.mainloop()
        finally:
            self._stop_tray()

    def shutdown(self) -> None:
        self.mark_stopped()

from __future__ import annotations

import ctypes
import os
import re
import subprocess
import threading
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox

try:
    import winreg
except ImportError:  # pragma: no cover - this app targets Windows.
    winreg = None


APP_TITLE = "JDK Switcher"
ENV_KEY = r"Environment"
JAVA_HOME = "JAVA_HOME"
PATH_NAME = "Path"
JAVA_BIN_TOKEN = r"%JAVA_HOME%\bin"


@dataclass(frozen=True)
class JdkInstall:
    home: Path
    version: str
    vendor: str

    @property
    def label(self) -> str:
        return f"JDK {self.version}"


def normalize_path(value: str | Path) -> str:
    return str(Path(os.path.expandvars(str(value))).resolve()).casefold()


def is_jdk_home(path: Path) -> bool:
    return (path / "bin" / "java.exe").is_file() and (path / "bin" / "javac.exe").is_file()


def run_java_version(java_exe: Path) -> str:
    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    result = subprocess.run(
        [str(java_exe), "-version"],
        capture_output=True,
        text=True,
        timeout=6,
        startupinfo=startupinfo,
        check=False,
    )
    return (result.stderr or result.stdout).strip()


def parse_version(version_output: str) -> str:
    match = re.search(r'version "([^"]+)"', version_output)
    if not match:
        return "unknown"
    raw = match.group(1)
    if raw.startswith("1."):
        parts = raw.split(".")
        return parts[1] if len(parts) > 1 else raw
    return raw.split(".")[0]


def parse_vendor(version_output: str, home: Path) -> str:
    lowered = version_output.lower()
    if "temurin" in lowered or "adoptium" in lowered:
        return "Eclipse Temurin"
    if "corretto" in lowered:
        return "Amazon Corretto"
    if "microsoft" in lowered:
        return "Microsoft Build"
    if "oracle" in lowered or "java(tm)" in lowered:
        return "Oracle"
    if "zulu" in lowered:
        return "Azul Zulu"
    return home.parent.name if home.parent.name else "Unknown vendor"


def candidate_roots() -> list[Path]:
    roots = [
        Path(r"C:\Program Files\Java"),
        Path(r"C:\Program Files\Eclipse Adoptium"),
        Path(r"C:\Program Files\Amazon Corretto"),
        Path(r"C:\Program Files\Microsoft"),
        Path(r"C:\Program Files\Zulu"),
        Path(r"C:\Program Files (x86)\Java"),
    ]

    env_home = os.environ.get(JAVA_HOME)
    if env_home:
        roots.append(Path(env_home))

    for segment in os.environ.get("PATH", "").split(os.pathsep):
        if not segment:
            continue
        path = Path(os.path.expandvars(segment.strip('"')))
        if path.name.lower() == "bin":
            roots.append(path.parent)

    return roots


def discover_jdks() -> list[JdkInstall]:
    seen: set[str] = set()
    homes: list[Path] = []

    for root in candidate_roots():
        expanded = Path(os.path.expandvars(str(root)))
        if is_jdk_home(expanded):
            homes.append(expanded)
        if expanded.is_dir():
            try:
                homes.extend(child for child in expanded.iterdir() if child.is_dir() and is_jdk_home(child))
            except PermissionError:
                continue

    jdks: list[JdkInstall] = []
    for home in homes:
        key = normalize_path(home)
        if key in seen:
            continue
        seen.add(key)
        try:
            output = run_java_version(home / "bin" / "java.exe")
        except (subprocess.SubprocessError, OSError):
            continue
        jdks.append(JdkInstall(home=home, version=parse_version(output), vendor=parse_vendor(output, home)))

    return sorted(jdks, key=lambda jdk: (version_sort_key(jdk.version), str(jdk.home)), reverse=True)


def version_sort_key(value: str) -> tuple[int, str]:
    try:
        return int(value), value
    except ValueError:
        return -1, value


def get_user_env(name: str) -> str:
    if winreg is None:
        raise RuntimeError("This app requires Windows.")
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, ENV_KEY) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value)
    except FileNotFoundError:
        return ""


def set_user_env(name: str, value: str) -> None:
    if winreg is None:
        raise RuntimeError("This app requires Windows.")
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, ENV_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_EXPAND_SZ, value)


def path_looks_like_jdk_bin(segment: str) -> bool:
    expanded = Path(os.path.expandvars(segment.strip().strip('"')))
    return expanded.name.lower() == "bin" and is_jdk_home(expanded.parent)


def build_user_path(current_path: str) -> str:
    kept: list[str] = []
    seen: set[str] = set()

    for segment in current_path.split(os.pathsep):
        clean = segment.strip()
        if not clean:
            continue
        if clean.casefold() == JAVA_BIN_TOKEN.casefold() or path_looks_like_jdk_bin(clean):
            continue
        key = clean.casefold()
        if key in seen:
            continue
        seen.add(key)
        kept.append(clean)

    return os.pathsep.join([JAVA_BIN_TOKEN, *kept])


def broadcast_env_change() -> None:
    hwnd_broadcast = 0xFFFF
    wm_settingchange = 0x001A
    smto_abortifhung = 0x0002
    ctypes.windll.user32.SendMessageTimeoutW(
        hwnd_broadcast,
        wm_settingchange,
        0,
        "Environment",
        smto_abortifhung,
        5000,
        None,
    )


def switch_jdk(jdk: JdkInstall) -> None:
    set_user_env(JAVA_HOME, str(jdk.home))
    set_user_env(PATH_NAME, build_user_path(get_user_env(PATH_NAME)))
    os.environ[JAVA_HOME] = str(jdk.home)
    os.environ["PATH"] = os.pathsep.join([str(jdk.home / "bin"), os.environ.get("PATH", "")])
    broadcast_env_change()


def current_java_home() -> str:
    return get_user_env(JAVA_HOME) or os.environ.get(JAVA_HOME, "")


class JdkSwitcherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("980x640")
        self.minsize(880, 560)
        self.configure(bg="#0e1116")

        self.jdks: list[JdkInstall] = []
        self.selected_index: int | None = None
        self.card_frames: list[tk.Frame] = []
        self.fonts: dict[tuple[str, int, str], tkfont.Font] = {}
        self.colors = {
            "bg": "#0e1116",
            "panel": "#151922",
            "panel_2": "#11151d",
            "card": "#181d27",
            "card_active": "#1e2a2f",
            "card_selected": "#202a3a",
            "ink": "#eef2f7",
            "muted": "#8f9aaa",
            "subtle": "#647084",
            "line": "#252d3a",
            "line_active": "#36d399",
            "accent": "#36d399",
            "accent_dark": "#2abb82",
            "warning": "#f2b84b",
            "danger": "#ff6b6b",
        }

        self._configure_style()
        self._build_ui()
        self.refresh_jdks()

    def _configure_style(self) -> None:
        return

    def font(self, size: int, weight: str = "normal", family: str = "Segoe UI") -> tkfont.Font:
        key = (family, size, weight)
        if key not in self.fonts:
            self.fonts[key] = tkfont.Font(family=family, size=size, weight=weight)
        return self.fonts[key]

    def _build_ui(self) -> None:
        shell = tk.Frame(self, bg=self.colors["bg"], padx=30, pady=26)
        shell.pack(fill="both", expand=True)

        header = tk.Frame(shell, bg=self.colors["bg"])
        header.pack(fill="x")

        title_block = tk.Frame(header, bg=self.colors["bg"])
        title_block.pack(side="left", fill="x", expand=True)

        tk.Label(title_block, text="JDK Switcher", bg=self.colors["bg"], fg=self.colors["ink"], font=self.font(26, "bold")).pack(anchor="w")
        tk.Label(title_block, text="Cambia JAVA_HOME entre tus instalaciones locales sin tocar variables a mano.", bg=self.colors["bg"], fg=self.colors["muted"], font=self.font(10)).pack(anchor="w", pady=(4, 0))

        self.refresh_button = tk.Button(header, text="Actualizar", command=self.refresh_jdks, bg=self.colors["panel"], fg=self.colors["ink"], activebackground=self.colors["card"], activeforeground=self.colors["ink"], relief="flat", bd=0, padx=18, pady=10, cursor="hand2", font=self.font(10, "bold"))
        self.refresh_button.pack(side="right", anchor="n")

        body = tk.Frame(shell, bg=self.colors["bg"])
        body.pack(fill="both", expand=True, pady=(24, 0))

        left = tk.Frame(body, bg=self.colors["panel"], highlightbackground=self.colors["line"], highlightthickness=1)
        left.pack(side="left", fill="both", expand=True)

        list_header = tk.Frame(left, bg=self.colors["panel"], padx=20, pady=18)
        list_header.pack(fill="x")
        tk.Label(list_header, text="JDK detectados", bg=self.colors["panel"], fg=self.colors["ink"], font=self.font(13, "bold")).pack(side="left")
        self.count_label = tk.Label(list_header, text="", bg=self.colors["panel"], fg=self.colors["muted"], font=self.font(10))
        self.count_label.pack(side="right")

        self.canvas = tk.Canvas(left, bg=self.colors["panel"], highlightthickness=0, bd=0)
        self.cards_container = tk.Frame(self.canvas, bg=self.colors["panel"])
        self.canvas_window = self.canvas.create_window((0, 0), window=self.cards_container, anchor="nw")
        self.canvas.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.cards_container.bind("<Configure>", self._sync_scroll_region)
        self.canvas.bind("<Configure>", self._sync_canvas_width)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        right = tk.Frame(body, bg=self.colors["bg"], width=320)
        right.pack(side="right", fill="y", padx=(18, 0))
        right.pack_propagate(False)

        card = tk.Frame(right, bg=self.colors["panel"], highlightbackground=self.colors["line"], highlightthickness=1, padx=20, pady=20)
        card.pack(fill="x")

        tk.Label(card, text="JDK activo", bg=self.colors["panel"], fg=self.colors["muted"], font=self.font(9, "bold")).pack(anchor="w")
        self.active_label = tk.Label(card, text="-", bg=self.colors["panel"], fg=self.colors["ink"], font=self.font(11, "bold"), wraplength=270, justify="left")
        self.active_label.pack(anchor="w", fill="x", pady=(8, 18))

        tk.Label(card, text="Selección", bg=self.colors["panel"], fg=self.colors["muted"], font=self.font(9, "bold")).pack(anchor="w")
        self.selected_label = tk.Label(card, text="Selecciona un JDK", bg=self.colors["panel"], fg=self.colors["ink"], font=self.font(11), wraplength=270, justify="left")
        self.selected_label.pack(anchor="w", fill="x", pady=(8, 18))

        self.switch_button = tk.Button(card, text="Activar JDK", command=self.activate_selected, bg=self.colors["accent"], fg="#06100b", activebackground=self.colors["accent_dark"], activeforeground="#06100b", relief="flat", bd=0, padx=18, pady=12, cursor="hand2", font=self.font(11, "bold"), state="disabled", disabledforeground=self.colors["subtle"])
        self.switch_button.pack(fill="x")

        note_card = tk.Frame(right, bg=self.colors["panel_2"], highlightbackground=self.colors["line"], highlightthickness=1, padx=16, pady=14)
        note_card.pack(fill="x", pady=(16, 0))
        note = tk.Label(note_card, text="El cambio aplica a terminales e IDEs nuevos. Si algo ya estaba abierto, reinícialo para que tome JAVA_HOME.", bg=self.colors["panel_2"], fg=self.colors["muted"], font=self.font(9), wraplength=270, justify="left")
        note.pack(anchor="w", pady=(16, 0))

        self.status = tk.Label(shell, text="", bg=self.colors["bg"], fg=self.colors["muted"], font=self.font(9), anchor="w")
        self.status.pack(fill="x", pady=(16, 0))

    def _sync_scroll_region(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_canvas_width(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        widget = self.canvas.winfo_containing(event.x_root, event.y_root)
        if widget is not None and self._is_child_of(widget, self.canvas):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _is_child_of(self, widget: tk.Widget, parent: tk.Widget) -> bool:
        current: tk.Widget | None = widget
        while current is not None:
            if current is parent:
                return True
            current = current.master
        return False

    def set_status(self, text: str, warning: bool = False) -> None:
        self.status.configure(text=text, fg=self.colors["warning"] if warning else self.colors["muted"])

    def refresh_jdks(self) -> None:
        self.refresh_button.configure(state="disabled")
        self.set_status("Buscando instalaciones de JDK...")
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self) -> None:
        try:
            jdks = discover_jdks()
            self.after(0, lambda: self._render_jdks(jdks))
        except Exception as exc:  # noqa: BLE001 - UI should surface unexpected failures.
            self.after(0, lambda: self._show_error("No se pudo buscar JDK", exc))

    def _render_jdks(self, jdks: list[JdkInstall]) -> None:
        self.jdks = jdks
        self.selected_index = None
        self.card_frames = []
        for child in self.cards_container.winfo_children():
            child.destroy()
        active = normalize_path(current_java_home()) if current_java_home() else ""

        for index, jdk in enumerate(jdks):
            self._create_jdk_card(index, jdk, normalize_path(jdk.home) == active)

        self.count_label.configure(text=f"{len(jdks)} encontrados")
        self.active_label.configure(text=current_java_home() or "JAVA_HOME no definido")
        self.selected_label.configure(text="Selecciona un JDK")
        self.switch_button.configure(state="disabled")
        self.refresh_button.configure(state="normal")

        if jdks:
            self.set_status("Listo. Selecciona una versión y pulsa Activar JDK.")
        else:
            self.set_status("No encontré JDK instalados en las rutas comunes ni en PATH.", warning=True)

    def _create_jdk_card(self, index: int, jdk: JdkInstall, is_active: bool) -> None:
        bg = self.colors["card_active"] if is_active else self.colors["card"]
        border = self.colors["line_active"] if is_active else self.colors["line"]
        card = tk.Frame(self.cards_container, bg=bg, highlightbackground=border, highlightthickness=1, padx=16, pady=14, cursor="hand2")
        card.pack(fill="x", pady=(0, 12))
        self.card_frames.append(card)

        top = tk.Frame(card, bg=bg)
        top.pack(fill="x")

        version = tk.Label(top, text=f"JDK {jdk.version}", bg=bg, fg=self.colors["ink"], font=self.font(18, "bold"), cursor="hand2")
        version.pack(side="left")

        if is_active:
            pill = tk.Label(top, text="ACTUAL", bg=self.colors["accent"], fg="#06100b", font=self.font(8, "bold"), padx=9, pady=3, cursor="hand2")
            pill.pack(side="right")

        tk.Label(card, text=jdk.vendor, bg=bg, fg=self.colors["muted"], font=self.font(10), cursor="hand2").pack(anchor="w", pady=(8, 0))
        tk.Label(card, text=str(jdk.home), bg=bg, fg=self.colors["subtle"], font=self.font(9, family="Consolas"), wraplength=560, justify="left", cursor="hand2").pack(anchor="w", fill="x", pady=(10, 0))

        self._bind_card_click(card, index)

    def _bind_card_click(self, widget: tk.Widget, index: int) -> None:
        widget.bind("<Button-1>", lambda _event, idx=index: self.select_jdk(idx))
        for child in widget.winfo_children():
            self._bind_card_click(child, index)

    def select_jdk(self, index: int) -> None:
        self.selected_index = index
        jdk = self.jdks[self.selected_index]
        self.selected_label.configure(text=f"JDK {jdk.version}\n{jdk.vendor}\n{jdk.home}")
        self.switch_button.configure(state="normal")
        self._paint_cards()

    def _paint_cards(self) -> None:
        active = normalize_path(current_java_home()) if current_java_home() else ""
        for index, card in enumerate(self.card_frames):
            is_active = normalize_path(self.jdks[index].home) == active
            is_selected = index == self.selected_index
            bg = self.colors["card_selected"] if is_selected else self.colors["card_active"] if is_active else self.colors["card"]
            border = self.colors["accent"] if is_selected or is_active else self.colors["line"]
            self._recolor_widget_tree(card, bg)
            card.configure(highlightbackground=border)

    def _recolor_widget_tree(self, widget: tk.Widget, bg: str) -> None:
        try:
            widget.configure(bg=bg)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            if isinstance(child, tk.Label) and child.cget("text") == "ACTUAL":
                continue
            self._recolor_widget_tree(child, bg)

    def activate_selected(self) -> None:
        if self.selected_index is None:
            return
        jdk = self.jdks[self.selected_index]
        self.switch_button.configure(state="disabled")
        self.set_status(f"Activando JDK {jdk.version}...")
        threading.Thread(target=self._activate_worker, args=(jdk,), daemon=True).start()

    def _activate_worker(self, jdk: JdkInstall) -> None:
        try:
            switch_jdk(jdk)
            version = run_java_version(jdk.home / "bin" / "java.exe").splitlines()[0]
            self.after(0, lambda: self._activation_done(jdk, version))
        except Exception as exc:  # noqa: BLE001 - UI should surface unexpected failures.
            self.after(0, lambda: self._show_error("No se pudo activar el JDK", exc))

    def _activation_done(self, jdk: JdkInstall, version_line: str) -> None:
        self.active_label.configure(text=str(jdk.home))
        self.switch_button.configure(state="normal")
        self.set_status(f"Activo: {version_line}. Abre una nueva terminal para usarlo.")
        self._render_jdks(self.jdks)

    def _show_error(self, title: str, exc: Exception) -> None:
        self.refresh_button.configure(state="normal")
        self.switch_button.configure(state="normal" if self.selected_index is not None else "disabled")
        self.set_status(str(exc), warning=True)
        messagebox.showerror(title, str(exc))


if __name__ == "__main__":
    if os.name != "nt":
        raise SystemExit("JDK Switcher currently supports Windows only.")
    JdkSwitcherApp().mainloop()

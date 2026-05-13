from __future__ import annotations

import ctypes
import locale
import os
import platform
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
except ImportError:
    winreg = None


APP_TITLE = "JDK Switcher"
JAVA_HOME_VAR = "JAVA_HOME"

SYSTEM = platform.system()

LANG = "en"
try:
    code, _ = locale.getdefaultlocale()
    if code and code.startswith("es"):
        LANG = "es"
except Exception:
    pass

STRINGS = {
    "en": {
        "subtitle": "Automatically detects installed JDKs and switches JAVA_HOME.",
        "refresh": "Refresh",
        "detected_jdks": "Detected JDKs",
        "n_found": "{} found",
        "active_jdk": "Active JDK",
        "selection": "Selection",
        "select_jdk": "Select a JDK",
        "activate": "Activate JDK",
        "note": "The change applies to new terminals and IDEs. Restart any already open applications for them to pick up JAVA_HOME.",
        "scanning": "Scanning for JDK installations...",
        "ready": "Ready. Select a version and click Activate JDK.",
        "not_found": "No JDK installations found in common locations or PATH.",
        "activating": "Activating JDK {}...",
        "active_line": "Active: {}. Open a new terminal to use it.",
        "fail_scan": "Failed to scan JDKs",
        "fail_activate": "Failed to activate JDK",
        "home_not_set": "JAVA_HOME not set",
        "badge_active": "ACTIVE",
        "unknown_vendor": "Unknown",
    },
    "es": {
        "subtitle": "Detecta automáticamente los JDK instalados y cambia JAVA_HOME.",
        "refresh": "Actualizar",
        "detected_jdks": "JDK detectados",
        "n_found": "{} encontrados",
        "active_jdk": "JDK activo",
        "selection": "Selección",
        "select_jdk": "Selecciona un JDK",
        "activate": "Activar JDK",
        "note": "El cambio aplica a terminales e IDEs nuevos. Reinicia las aplicaciones abiertas para que tomen JAVA_HOME.",
        "scanning": "Buscando instalaciones de JDK...",
        "ready": "Listo. Selecciona una versión y pulsa Activar JDK.",
        "not_found": "No se encontraron JDK instalados en ubicaciones comunes ni en PATH.",
        "activating": "Activando JDK {}...",
        "active_line": "Activo: {}. Abre una terminal nueva para usarlo.",
        "fail_scan": "Error al buscar JDK",
        "fail_activate": "Error al activar JDK",
        "home_not_set": "JAVA_HOME no definido",
        "badge_active": "ACTUAL",
        "unknown_vendor": "Desconocido",
    },
}


def _(key: str) -> str:
    return STRINGS.get(LANG, STRINGS["en"]).get(key, key)


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
    java = path / "bin" / "java"
    javac = path / "bin" / "javac"
    java_exe = path / "bin" / "java.exe"
    javac_exe = path / "bin" / "javac.exe"
    return (java.is_file() or java_exe.is_file()) and (javac.is_file() or javac_exe.is_file())


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
    return home.parent.name if home.parent.name else _("unknown_vendor")


def version_sort_key(value: str) -> tuple[int, str]:
    try:
        return int(value), value
    except ValueError:
        return -1, value


# ── Platform: Windows ──────────────────────────────────────────────────

def _candidate_roots_windows() -> list[Path]:
    roots = [
        Path(r"C:\Program Files\Java"),
        Path(r"C:\Program Files\Eclipse Adoptium"),
        Path(r"C:\Program Files\Amazon Corretto"),
        Path(r"C:\Program Files\Microsoft"),
        Path(r"C:\Program Files\Zulu"),
        Path(r"C:\Program Files (x86)\Java"),
    ]
    env_home = os.environ.get(JAVA_HOME_VAR)
    if env_home:
        roots.append(Path(env_home))
    for segment in os.environ.get("PATH", "").split(os.pathsep):
        if not segment:
            continue
        path = Path(os.path.expandvars(segment.strip('"')))
        if path.name.lower() == "bin":
            roots.append(path.parent)
    return roots


def _discover_windows() -> list[JdkInstall]:
    seen: set[str] = set()
    homes: list[Path] = []
    for root in _candidate_roots_windows():
        expanded = Path(os.path.expandvars(str(root)))
        if is_jdk_home(expanded):
            homes.append(expanded)
        if expanded.is_dir():
            try:
                homes.extend(
                    child for child in expanded.iterdir()
                    if child.is_dir() and is_jdk_home(child)
                )
            except PermissionError:
                continue
    return _build_jdks(homes, seen)


def _get_user_env_windows(name: str) -> str:
    if winreg is None:
        return ""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value)
    except FileNotFoundError:
        return ""


def _set_user_env_windows(name: str, value: str) -> None:
    if winreg is None:
        raise RuntimeError("winreg is not available")
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_EXPAND_SZ, value)


def _path_looks_like_jdk_bin(segment: str) -> bool:
    expanded = Path(os.path.expandvars(segment.strip().strip('"')))
    return expanded.name.lower() == "bin" and is_jdk_home(expanded.parent)


def _build_user_path_windows(current_path: str) -> str:
    kept: list[str] = []
    seen: set[str] = set()
    for segment in current_path.split(os.pathsep):
        clean = segment.strip()
        if not clean:
            continue
        if clean.casefold() == r"%JAVA_HOME%\bin".casefold() or _path_looks_like_jdk_bin(clean):
            continue
        key = clean.casefold()
        if key in seen:
            continue
        seen.add(key)
        kept.append(clean)
    return os.pathsep.join([r"%JAVA_HOME%\bin", *kept])


def _broadcast_env_change() -> None:
    hwnd_broadcast = 0xFFFF
    wm_settingchange = 0x001A
    smto_abortifhung = 0x0002
    ctypes.windll.user32.SendMessageTimeoutW(
        hwnd_broadcast, wm_settingchange, 0, "Environment", smto_abortifhung, 5000, None,
    )


def _switch_windows(jdk: JdkInstall) -> None:
    _set_user_env_windows(JAVA_HOME_VAR, str(jdk.home))
    _set_user_env_windows("Path", _build_user_path_windows(_get_user_env_windows("Path")))
    os.environ[JAVA_HOME_VAR] = str(jdk.home)
    os.environ["PATH"] = os.pathsep.join([str(jdk.home / "bin"), os.environ.get("PATH", "")])
    _broadcast_env_change()


def _current_java_home_windows() -> str:
    return _get_user_env_windows(JAVA_HOME_VAR) or os.environ.get(JAVA_HOME_VAR, "")


# ── Platform: macOS ────────────────────────────────────────────────────

def _candidate_roots_macos() -> list[Path]:
    roots = [
        Path("/Library/Java/JavaVirtualMachines"),
        Path.home() / "Library/Java/JavaVirtualMachines",
        Path("/opt/homebrew/Cellar/openjdk"),
    ]
    env_home = os.environ.get(JAVA_HOME_VAR)
    if env_home:
        roots.append(Path(env_home))
    try:
        result = subprocess.run(
            ["/usr/libexec/java_home"],
            capture_output=True, text=True, timeout=6, check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            roots.append(Path(result.stdout.strip()))
    except (subprocess.SubprocessError, OSError):
        pass
    return roots


def _discover_macos() -> list[JdkInstall]:
    seen: set[str] = set()
    homes: list[Path] = []
    for root in _candidate_roots_macos():
        if is_jdk_home(root):
            homes.append(root)
        if root.is_dir():
            try:
                for child in root.iterdir():
                    if child.name.endswith(".jdk") and child.is_dir():
                        candidate = child / "Contents" / "Home"
                        if is_jdk_home(candidate):
                            homes.append(candidate)
                    elif child.is_dir() and is_jdk_home(child):
                        homes.append(child)
            except PermissionError:
                continue
    return _build_jdks(homes, seen)


def _mac_env_file() -> Path:
    return Path.home() / ".jdk_switcher_env.sh"


def _mac_ensure_shell_config() -> None:
    line = '\n[ -f "$HOME/.jdk_switcher_env.sh" ] && . "$HOME/.jdk_switcher_env.sh"\n'
    for rc_name in (".zshrc", ".zprofile", ".bashrc", ".bash_profile"):
        rc = Path.home() / rc_name
        exists = rc.is_file()
        if exists:
            content = rc.read_text(encoding="utf-8")
            if "$HOME/.jdk_switcher_env.sh" in content:
                continue
            rc.write_text(content + line, encoding="utf-8")
        elif rc_name in (".zshrc", ".bash_profile"):
            rc.write_text(line, encoding="utf-8")


def _get_user_env_macos(name: str) -> str:
    if name == JAVA_HOME_VAR:
        env_file = _mac_env_file()
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith(f"export {JAVA_HOME_VAR}="):
                    parts = line.split("=", 1)
                    return parts[1].strip().strip('"')
        return os.environ.get(JAVA_HOME_VAR, "")
    return ""


def _set_user_env_macos(name: str, value: str) -> None:
    if name == JAVA_HOME_VAR:
        env_file = _mac_env_file()
        content = f'export {JAVA_HOME_VAR}="{value}"\n'
        content += f'export PATH="{value}/bin:$PATH"\n'
        env_file.parent.mkdir(parents=True, exist_ok=True)
        env_file.write_text(content, encoding="utf-8")
        _mac_ensure_shell_config()


def _switch_macos(jdk: JdkInstall) -> None:
    _set_user_env_macos(JAVA_HOME_VAR, str(jdk.home))
    os.environ[JAVA_HOME_VAR] = str(jdk.home)
    os.environ["PATH"] = f"{jdk.home / 'bin'}:{os.environ.get('PATH', '')}"
    try:
        subprocess.run(
            ["launchctl", "setenv", JAVA_HOME_VAR, str(jdk.home)],
            capture_output=True, timeout=6, check=False,
        )
    except (subprocess.SubprocessError, OSError):
        pass


def _current_java_home_macos() -> str:
    return _get_user_env_macos(JAVA_HOME_VAR)


# ── Platform dispatch ──────────────────────────────────────────────────

def _build_jdks(homes: list[Path], seen: set[str]) -> list[JdkInstall]:
    jdks: list[JdkInstall] = []
    for home in homes:
        key = normalize_path(home)
        if key in seen:
            continue
        seen.add(key)
        java_exe = home / "bin" / "java"
        try:
            output = run_java_version(java_exe)
        except (subprocess.SubprocessError, OSError):
            continue
        jdks.append(JdkInstall(home=home, version=parse_version(output), vendor=parse_vendor(output, home)))
    return sorted(jdks, key=lambda jdk: (version_sort_key(jdk.version), str(jdk.home)), reverse=True)


def discover_jdks() -> list[JdkInstall]:
    if SYSTEM == "Windows":
        return _discover_windows()
    elif SYSTEM == "Darwin":
        return _discover_macos()
    raise RuntimeError(f"Unsupported platform: {SYSTEM}")


def switch_jdk(jdk: JdkInstall) -> None:
    if SYSTEM == "Windows":
        _switch_windows(jdk)
    elif SYSTEM == "Darwin":
        _switch_macos(jdk)
    else:
        raise RuntimeError(f"Unsupported platform: {SYSTEM}")


def current_java_home() -> str:
    if SYSTEM == "Windows":
        return _current_java_home_windows()
    elif SYSTEM == "Darwin":
        return _current_java_home_macos()
    return os.environ.get(JAVA_HOME_VAR, "")


# ── UI ─────────────────────────────────────────────────────────────────

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
        }

        self._build_ui()
        self.refresh_jdks()

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

        tk.Label(
            title_block, text="JDK Switcher",
            bg=self.colors["bg"], fg=self.colors["ink"],
            font=self.font(26, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title_block, text=_("subtitle"),
            bg=self.colors["bg"], fg=self.colors["muted"],
            font=self.font(10),
        ).pack(anchor="w", pady=(4, 0))

        self.refresh_button = tk.Button(
            header, text=_("refresh"),
            command=self.refresh_jdks,
            bg=self.colors["panel"], fg=self.colors["ink"],
            activebackground=self.colors["card"], activeforeground=self.colors["ink"],
            relief="flat", bd=0, padx=18, pady=10, cursor="hand2",
            font=self.font(10, "bold"),
        )
        self.refresh_button.pack(side="right", anchor="n")

        body = tk.Frame(shell, bg=self.colors["bg"])
        body.pack(fill="both", expand=True, pady=(24, 0))

        left = tk.Frame(body, bg=self.colors["panel"], highlightbackground=self.colors["line"], highlightthickness=1)
        left.pack(side="left", fill="both", expand=True)

        list_header = tk.Frame(left, bg=self.colors["panel"], padx=20, pady=18)
        list_header.pack(fill="x")
        tk.Label(
            list_header, text=_("detected_jdks"),
            bg=self.colors["panel"], fg=self.colors["ink"],
            font=self.font(13, "bold"),
        ).pack(side="left")
        self.count_label = tk.Label(
            list_header, text="",
            bg=self.colors["panel"], fg=self.colors["muted"],
            font=self.font(10),
        )
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

        tk.Label(card, text=_("active_jdk"), bg=self.colors["panel"], fg=self.colors["muted"], font=self.font(9, "bold")).pack(anchor="w")
        self.active_label = tk.Label(
            card, text="-",
            bg=self.colors["panel"], fg=self.colors["ink"],
            font=self.font(11, "bold"), wraplength=270, justify="left",
        )
        self.active_label.pack(anchor="w", fill="x", pady=(8, 18))

        tk.Label(card, text=_("selection"), bg=self.colors["panel"], fg=self.colors["muted"], font=self.font(9, "bold")).pack(anchor="w")
        self.selected_label = tk.Label(
            card, text=_("select_jdk"),
            bg=self.colors["panel"], fg=self.colors["ink"],
            font=self.font(11), wraplength=270, justify="left",
        )
        self.selected_label.pack(anchor="w", fill="x", pady=(8, 18))

        self.switch_button = tk.Button(
            card, text=_("activate"),
            command=self.activate_selected,
            bg=self.colors["accent"], fg="#06100b",
            activebackground=self.colors["accent_dark"], activeforeground="#06100b",
            relief="flat", bd=0, padx=18, pady=12, cursor="hand2",
            font=self.font(11, "bold"),
            state="disabled", disabledforeground=self.colors["subtle"],
        )
        self.switch_button.pack(fill="x")

        note_card = tk.Frame(right, bg=self.colors["panel_2"], highlightbackground=self.colors["line"], highlightthickness=1, padx=16, pady=14)
        note_card.pack(fill="x", pady=(16, 0))
        note = tk.Label(
            note_card,
            text=_("note"),
            bg=self.colors["panel_2"], fg=self.colors["muted"],
            font=self.font(9), wraplength=270, justify="left",
        )
        note.pack(anchor="w", pady=(16, 0))

        self.status = tk.Label(
            shell, text="",
            bg=self.colors["bg"], fg=self.colors["muted"],
            font=self.font(9), anchor="w",
        )
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
        self.set_status(_("scanning"))
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self) -> None:
        try:
            jdks = discover_jdks()
            self.after(0, lambda: self._render_jdks(jdks))
        except Exception as exc:
            self.after(0, lambda: self._show_error(_("fail_scan"), exc))

    def _render_jdks(self, jdks: list[JdkInstall]) -> None:
        self.jdks = jdks
        self.selected_index = None
        self.card_frames = []
        for child in self.cards_container.winfo_children():
            child.destroy()
        active = normalize_path(current_java_home()) if current_java_home() else ""

        for index, jdk in enumerate(jdks):
            self._create_jdk_card(index, jdk, normalize_path(jdk.home) == active)

        self.count_label.configure(text=_("n_found").format(len(jdks)))
        self.active_label.configure(text=current_java_home() or _("home_not_set"))
        self.selected_label.configure(text=_("select_jdk"))
        self.switch_button.configure(state="disabled")
        self.refresh_button.configure(state="normal")

        if jdks:
            self.set_status(_("ready"))
        else:
            self.set_status(_("not_found"), warning=True)

    def _create_jdk_card(self, index: int, jdk: JdkInstall, is_active: bool) -> None:
        bg = self.colors["card_active"] if is_active else self.colors["card"]
        border = self.colors["line_active"] if is_active else self.colors["line"]
        card = tk.Frame(
            self.cards_container, bg=bg,
            highlightbackground=border, highlightthickness=1,
            padx=16, pady=14, cursor="hand2",
        )
        card.pack(fill="x", pady=(0, 12))
        self.card_frames.append(card)

        top = tk.Frame(card, bg=bg)
        top.pack(fill="x")

        version = tk.Label(
            top, text=f"JDK {jdk.version}",
            bg=bg, fg=self.colors["ink"],
            font=self.font(18, "bold"), cursor="hand2",
        )
        version.pack(side="left")

        if is_active:
            pill = tk.Label(
                top, text=_("badge_active"),
                bg=self.colors["accent"], fg="#06100b",
                font=self.font(8, "bold"), padx=9, pady=3, cursor="hand2",
            )
            pill.pack(side="right")

        tk.Label(
            card, text=jdk.vendor,
            bg=bg, fg=self.colors["muted"],
            font=self.font(10), cursor="hand2",
        ).pack(anchor="w", pady=(8, 0))
        tk.Label(
            card, text=str(jdk.home),
            bg=bg, fg=self.colors["subtle"],
            font=self.font(9, family="Consolas" if SYSTEM == "Windows" else "Menlo"),
            wraplength=560, justify="left", cursor="hand2",
        ).pack(anchor="w", fill="x", pady=(10, 0))

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
            bg = (
                self.colors["card_selected"] if is_selected else
                self.colors["card_active"] if is_active else
                self.colors["card"]
            )
            border = self.colors["accent"] if is_selected or is_active else self.colors["line"]
            self._recolor_widget_tree(card, bg)
            card.configure(highlightbackground=border)

    def _recolor_widget_tree(self, widget: tk.Widget, bg: str) -> None:
        try:
            widget.configure(bg=bg)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            if isinstance(child, tk.Label) and child.cget("text") == _("badge_active"):
                continue
            self._recolor_widget_tree(child, bg)

    def activate_selected(self) -> None:
        if self.selected_index is None:
            return
        jdk = self.jdks[self.selected_index]
        self.switch_button.configure(state="disabled")
        self.set_status(_("activating").format(jdk.version))
        threading.Thread(target=self._activate_worker, args=(jdk,), daemon=True).start()

    def _activate_worker(self, jdk: JdkInstall) -> None:
        try:
            switch_jdk(jdk)
            version = run_java_version(jdk.home / "bin" / "java").splitlines()[0]
            self.after(0, lambda: self._activation_done(jdk, version))
        except Exception as exc:
            self.after(0, lambda: self._show_error(_("fail_activate"), exc))

    def _activation_done(self, jdk: JdkInstall, version_line: str) -> None:
        self.active_label.configure(text=str(jdk.home))
        self.switch_button.configure(state="normal")
        self.set_status(_("active_line").format(version_line))
        self._render_jdks(self.jdks)

    def _show_error(self, title: str, exc: Exception) -> None:
        self.refresh_button.configure(state="normal")
        self.switch_button.configure(state="normal" if self.selected_index is not None else "disabled")
        self.set_status(str(exc), warning=True)
        messagebox.showerror(title, str(exc))


if __name__ == "__main__":
    if SYSTEM not in ("Windows", "Darwin"):
        raise SystemExit(f"JDK Switcher supports Windows and macOS only (detected: {SYSTEM}).")
    JdkSwitcherApp().mainloop()

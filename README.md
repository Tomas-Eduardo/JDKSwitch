# JDK Switcher

JDK Switcher is a desktop application that detects installed JDKs and lets you switch `JAVA_HOME` with one click.

It supports **Windows** and **macOS (Apple Silicon / Intel)**.

## Download

### Windows

Download `JDKSwitcher.exe` from the [Releases](https://github.com/TU_USUARIO/JDKSwitch/releases) page and run it. No installation required.

### macOS

**Option 1 — Run from source (no build needed):**

```bash
python3 jdk_switcher.py
```

Or double-click `JDKSwitcher.command` from Finder:

```bash
chmod +x JDKSwitcher.command
```

**Option 2 — Build a native .app bundle:**

Run the helper script on your Mac:

```bash
chmod +x build_macos.sh
./build_macos.sh
```

This generates `dist/JDKSwitcher`. You can wrap it as a proper `.app`:

```bash
mkdir -p "JDKSwitcher.app/Contents/MacOS"
cp dist/JDKSwitcher "JDKSwitcher.app/Contents/MacOS/JDKSwitcher"
```

Requires Python 3 with Tkinter support. The official Python installer from [python.org](https://www.python.org/downloads/) includes Tkinter.

## Features

- Automatically detects local JDK installations.
- Switches `JAVA_HOME` from a minimal desktop UI.
- Updates the `Path` to prioritize the selected JDK.
- Does not require administrator permissions.
- Dark minimal interface.

## How To Use

1. Open the application.
2. Select the JDK you want to activate.
3. Click **Activate JDK**.
4. Open a new terminal.
5. Verify the active version:

```bash
java -version
echo $JAVA_HOME
```

## Important

Environment variable changes only apply to **new** processes. Restart terminals, IDEs, or build tools after switching.

## How It Works

### Windows

- `JAVA_HOME` is set in user environment variables (registry).
- User `Path` is updated to include `%JAVA_HOME%\bin` first.
- Previous JDK entries are removed from the user `Path`.
- Does not modify system environment variables.

### macOS

- A file `~/.jdk_switcher_env.sh` is created with the `JAVA_HOME` and `PATH` exports.
- Your shell config (`.zshrc`, `.bashrc`, `.bash_profile`, `.zprofile`) is updated to source this file.
- `launchctl setenv` is called so GUI apps also receive the new `JAVA_HOME`.
- New terminals will automatically pick up the selected JDK.

## Detection

The app searches for JDK installations in standard locations:

### Windows
- `C:\Program Files\Java`
- `C:\Program Files\Eclipse Adoptium`
- `C:\Program Files\Amazon Corretto`
- `C:\Program Files\Microsoft`
- `C:\Program Files\Zulu`
- Current `JAVA_HOME` and `Path`

### macOS
- `/Library/Java/JavaVirtualMachines/`
- `~/Library/Java/JavaVirtualMachines/`
- `/opt/homebrew/Cellar/openjdk/`
- Current `JAVA_HOME`

A folder is considered a valid JDK if it contains `bin/java` and `bin/javac`.

## Build From Source

### Requirements

- Python 3.11 or newer
- PyInstaller (for executable build)

### Run directly

```bash
python jdk_switcher.py      # Windows
python3 jdk_switcher.py     # macOS
```

### Build executable

```powershell
# Windows
python -m pip install pyinstaller
python -m PyInstaller --onefile --windowed --name "JDKSwitcher" "jdk_switcher.py"
```

```bash
# macOS
pip3 install pyinstaller
python3 -m PyInstaller --onefile --windowed --name "JDKSwitcher" "jdk_switcher.py"
```

The executable will be generated at `dist/JDKSwitcher.exe` (Windows) or `dist/JDKSwitcher` (macOS).

## Repository Structure

```
JDKSwitcher/
├── jdk_switcher.py          # Main application (cross-platform)
├── JDKSwitcher.command      # macOS launcher (double-click)
├── run_jdk_switcher.bat     # Windows launcher (double-click)
├── build_macos.sh           # macOS build helper
├── README.md
├── LICENSE
└── .gitignore
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

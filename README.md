# JDK Switcher

JDK Switcher is a small Windows desktop app that automatically detects installed JDKs and lets you switch `JAVA_HOME` with one click.

It is designed for developers who work with multiple Java versions and want a simple UI instead of manually editing environment variables.

## Download

Download `JDKSwitcher.exe` from the repository release page and run it.

No installation is required.

## Features

- Automatically detects local JDK installations.
- Switches `JAVA_HOME` from a minimal desktop UI.
- Updates the current user's `Path` to prioritize `%JAVA_HOME%\bin`.
- Does not modify system-wide environment variables.
- Does not require administrator permissions.
- Works with JDK distributions installed in common Windows locations.

## How To Use

1. Open `JDKSwitcher.exe`.
2. Select the JDK you want to activate.
3. Click `Activate JDK`.
4. Open a new terminal.
5. Verify the active version:

```powershell
java -version
```

## Important Note

Environment variable changes only apply to new processes.

If you already had a terminal, IDE, build tool, or editor open, restart it after switching JDKs.

## What It Changes

JDK Switcher modifies user-level environment variables only:

- `JAVA_HOME`: set to the selected JDK path.
- `Path`: updates the user's `Path` so `%JAVA_HOME%\bin` is prioritized.

It does not modify machine-level variables.

## Detection

The app searches for valid JDK installations in common locations such as:

- `C:\Program Files\Java`
- `C:\Program Files\Eclipse Adoptium`
- `C:\Program Files\Amazon Corretto`
- `C:\Program Files\Microsoft`
- `C:\Program Files\Zulu`
- the current `JAVA_HOME`
- existing `PATH` entries

A folder is considered a valid JDK if it contains:

- `bin\java.exe`
- `bin\javac.exe`

## Limitations

- Existing terminals and IDEs must be restarted after switching.
- If a system-level Java path has higher priority in some process context, that process may still resolve `java` differently.
- Tools that respect `JAVA_HOME` will use the selected JDK.

## Build From Source

Requirements:

- Windows
- Python 3.11 or newer
- PyInstaller

Run from source:

```powershell
python jdk_switcher.py
```

Build the executable:

```powershell
python -m pip install pyinstaller
python -m PyInstaller --onefile --windowed --name "JDKSwitcher" "jdk_switcher.py"
```

The executable will be generated at:

```text
dist\JDKSwitcher.exe
```

## Repository Notes

Recommended files to keep in source control:

- `jdk_switcher.py`
- `run_jdk_switcher.bat`
- `README.md`
- `LICENSE`
- `.gitignore`

Build outputs should generally not be committed:

- `dist/`
- `build/`
- `*.spec`
- `__pycache__/`

If you only want to distribute the app, publish `JDKSwitcher.exe` as a GitHub Release asset.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

#!/bin/bash
# Build JDKSwitcher.app for macOS
# Run this on your Mac: chmod +x build_macos.sh && ./build_macos.sh

set -e

echo "Installing PyInstaller..."
pip3 install pyinstaller

echo "Building JDKSwitcher.app..."
cd "$(dirname "$0")"
python3 -m PyInstaller --onefile --windowed --name "JDKSwitcher" "jdk_switcher.py"

echo ""
echo "Done! App bundle created at: dist/JDKSwitcher"
echo "You can also find the standalone executable at: dist/JDKSwitcher"
echo ""
echo "To create a proper .app wrapper manually:"
echo '  mkdir -p "JDKSwitcher.app/Contents/MacOS"'
echo '  cp dist/JDKSwitcher "JDKSwitcher.app/Contents/MacOS/JDKSwitcher"'
echo '  # Then create Info.plist inside Contents/'

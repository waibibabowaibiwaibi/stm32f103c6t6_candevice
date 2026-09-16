#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "Build this executable on Linux; PyInstaller does not cross-compile." >&2
    exit 1
fi

host_app_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
task_python="${PYTHON:-python3}"
virtual_python="$host_app_root/.venv/bin/python"
export PIP_CACHE_DIR="$host_app_root/build/pip-cache"
export PYINSTALLER_CONFIG_DIR="$host_app_root/build/pyinstaller-cache"

if [[ ! -x "$virtual_python" ]]; then
    "$task_python" -m venv "$host_app_root/.venv"
fi
"$virtual_python" -m pip install --disable-pip-version-check -r "$host_app_root/requirements-release.txt"

cd -- "$host_app_root"
"$virtual_python" -m PyInstaller --noconfirm --clean UART-CAN-Host.spec
./dist/UART-CAN-Host --smoke-test

# Include the license material alongside the standalone executable.
task_arch="$(uname -m)"
case "$task_arch" in
    x86_64) task_arch="x64" ;;
    aarch64) task_arch="arm64" ;;
esac
package_name="UART-CAN-Host-linux-$task_arch"
package_root="$host_app_root/dist/$package_name"
mkdir -p -- "$package_root/licenses"
cp -- dist/UART-CAN-Host "$package_root/"
cp -- "$host_app_root/../LICENSE" "$package_root/LICENSE.txt"
cp -- "$host_app_root/../THIRD_PARTY_NOTICES.md" "$package_root/"
cp -- "$host_app_root/README.md" "$package_root/README.md"
cp -- "$host_app_root/../licenses/"{LGPL-3.0,GPL-3.0,PYTHON-LICENSE,PYSERIAL-LICENSE,PYINSTALLER-LICENSE}.txt "$package_root/licenses/"
task_glibc="$(getconf GNU_LIBC_VERSION)"
task_python_version="$("$virtual_python" --version)"
printf 'Architecture: %s\nBuild system: %s\nPython: %s\n' "$task_arch" "$task_glibc" "$task_python_version" > "$package_root/BUILD-INFO.txt"
tar -czf "dist/$package_name.tar.gz" -C dist "$package_name"
(cd dist && sha256sum "$package_name.tar.gz" > "$package_name.tar.gz.sha256")

echo "Executable: $host_app_root/dist/UART-CAN-Host"
echo "Package: $host_app_root/dist/$package_name.tar.gz"

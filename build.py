"""
Build script for creating binary release packages.

Usage:
    python build.py                 # Build for current platform
    python build.py --skip-frontend # Skip frontend build (use existing dist)
    python build.py --clean         # Clean build artifacts before building

Requirements:
    pip install pyinstaller
    Node.js and npm (for frontend build)
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
RELEASE_DIR = ROOT / "release"
FRONTEND_DIR = ROOT / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"


def run(cmd: list[str], cwd: Path | None = None, check: bool = True):
    """Run a subprocess command and print output."""
    print(f"  > {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, check=check)
    return result.returncode


def clean():
    """Remove previous build artifacts."""
    print("\n[1] Cleaning previous build artifacts...")
    for d in [DIST_DIR, BUILD_DIR, RELEASE_DIR]:
        if d.exists():
            shutil.rmtree(d)
            print(f"  Removed {d}")


def build_frontend():
    """Build the React frontend."""
    print("\n[2] Building frontend...")

    if not (FRONTEND_DIR / "package.json").exists():
        print("  ERROR: frontend/package.json not found")
        sys.exit(1)

    # Install dependencies
    npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"
    run([npm_cmd, "install"], cwd=FRONTEND_DIR)
    run([npm_cmd, "run", "build"], cwd=FRONTEND_DIR)

    if not FRONTEND_DIST.exists():
        print("  ERROR: Frontend build failed, dist/ not created")
        sys.exit(1)

    print("  Frontend build complete.")


def build_backend():
    """Build the Python backend with PyInstaller."""
    print("\n[3] Building backend with PyInstaller...")

    # Check PyInstaller is installed
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("  PyInstaller not found. Installing...")
        run([sys.executable, "-m", "pip", "install", "pyinstaller"])

    spec_file = ROOT / "server.spec"
    run([sys.executable, "-m", "PyInstaller", "--clean", str(spec_file)], cwd=ROOT)

    server_dir = DIST_DIR / "server"
    if not server_dir.exists():
        print("  ERROR: PyInstaller build failed")
        sys.exit(1)

    print("  Backend build complete.")


def assemble_release():
    """Assemble all components into a release package."""
    print("\n[4] Assembling release package...")

    system = platform.system().lower()
    machine = platform.machine().lower()
    if machine in ("amd64", "x86_64"):
        machine = "x64"
    elif machine in ("aarch64", "arm64"):
        machine = "arm64"

    release_name = f"auto_MV_generater-{system}-{machine}"
    release_path = RELEASE_DIR / release_name
    release_path.mkdir(parents=True, exist_ok=True)

    # 1. Copy PyInstaller output (server executable and dependencies)
    server_src = DIST_DIR / "server"
    server_dst = release_path / "server"
    print(f"  Copying server binary to {server_dst}...")
    shutil.copytree(server_src, server_dst)

    # 2. Copy frontend build output
    frontend_dst = release_path / "frontend" / "dist"
    print(f"  Copying frontend dist to {frontend_dst}...")
    shutil.copytree(FRONTEND_DIST, frontend_dst)

    # 3. Create necessary directories
    (release_path / "output").mkdir(exist_ok=True)
    (release_path / "logs").mkdir(exist_ok=True)

    # 4. Copy supporting files
    for f in ["README.md", "LICENSE"]:
        src = ROOT / f
        if src.exists():
            shutil.copy2(src, release_path / f)

    # 5. Create launcher scripts
    _create_launcher_scripts(release_path, system)

    # 6. Create .env.example
    _create_env_example(release_path)

    # 7. Create zip archive
    zip_name = f"{release_name}.zip"
    zip_path = RELEASE_DIR / zip_name
    print(f"  Creating archive: {zip_path}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in release_path.rglob("*"):
            if file.is_file():
                arcname = file.relative_to(RELEASE_DIR)
                zf.write(file, arcname)

    print(f"\n  Release package created: {zip_path}")
    print(f"  Size: {zip_path.stat().st_size / 1024 / 1024:.1f} MB")
    return zip_path


def _create_launcher_scripts(release_path: Path, system: str):
    """Create platform-specific launcher scripts."""

    if system == "windows":
        # start.bat for Windows
        start_bat = release_path / "start.bat"
        start_bat.write_text(
            '@echo off\r\n'
            'chcp 65001 >nul\r\n'
            'title AI Music Agent\r\n'
            'echo ============================================================\r\n'
            'echo   AI Music Agent - Binary Release\r\n'
            'echo ============================================================\r\n'
            'echo.\r\n'
            '\r\n'
            ':: Check .env file\r\n'
            'if not exist "%~dp0.env" (\r\n'
            '    echo [WARN] .env file not found!\r\n'
            '    echo        Copy .env.example to .env and fill in your API keys.\r\n'
            '    pause\r\n'
            '    exit /b 1\r\n'
            ')\r\n'
            '\r\n'
            ':: Start server\r\n'
            'echo Starting server...\r\n'
            'cd /d "%~dp0"\r\n'
            'start "AI-Music-Server" server\\server.exe\r\n'
            '\r\n'
            'timeout /t 3 /nobreak >nul\r\n'
            '\r\n'
            ':: Open browser\r\n'
            'echo Opening browser...\r\n'
            'start http://localhost:5000\r\n'
            '\r\n'
            'echo.\r\n'
            'echo   Server running at http://localhost:5000\r\n'
            'echo   Press Ctrl+C in the server window to stop.\r\n'
            'echo ============================================================\r\n',
            encoding="utf-8",
        )

        # stop.bat for Windows
        stop_bat = release_path / "stop.bat"
        stop_bat.write_text(
            '@echo off\r\n'
            'chcp 65001 >nul\r\n'
            'echo Stopping AI Music Agent...\r\n'
            'taskkill /IM server.exe /F >nul 2>&1\r\n'
            'echo Done.\r\n',
            encoding="utf-8",
        )
    else:
        # start.sh for Linux/macOS
        start_sh = release_path / "start.sh"
        start_sh.write_text(
            '#!/bin/bash\n'
            'echo "============================================================"\n'
            'echo "  AI Music Agent - Binary Release"\n'
            'echo "============================================================"\n'
            '\n'
            'SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"\n'
            'cd "$SCRIPT_DIR"\n'
            '\n'
            'if [ ! -f .env ]; then\n'
            '    echo "[WARN] .env file not found!"\n'
            '    echo "       Copy .env.example to .env and fill in your API keys."\n'
            '    exit 1\n'
            'fi\n'
            '\n'
            'echo "Starting server..."\n'
            './server/server &\n'
            'SERVER_PID=$!\n'
            'echo "Server PID: $SERVER_PID"\n'
            'echo $SERVER_PID > .server.pid\n'
            '\n'
            'sleep 3\n'
            'echo "Server running at http://localhost:5000"\n'
            'echo "Run ./stop.sh to stop the server."\n',
            encoding="utf-8",
        )
        start_sh.chmod(0o755)

        stop_sh = release_path / "stop.sh"
        stop_sh.write_text(
            '#!/bin/bash\n'
            'SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"\n'
            'if [ -f "$SCRIPT_DIR/.server.pid" ]; then\n'
            '    kill $(cat "$SCRIPT_DIR/.server.pid") 2>/dev/null\n'
            '    rm "$SCRIPT_DIR/.server.pid"\n'
            '    echo "Server stopped."\n'
            'else\n'
            '    echo "No PID file found. Server may not be running."\n'
            'fi\n',
            encoding="utf-8",
        )
        stop_sh.chmod(0o755)


def _create_env_example(release_path: Path):
    """Create a .env.example file."""
    env_example = release_path / ".env.example"
    env_example.write_text(
        '# ===========================================\n'
        '# AI Music Agent - Configuration\n'
        '# Copy this file to .env and fill in values\n'
        '# ===========================================\n'
        '\n'
        '# --- Gemini LLM ---\n'
        'GEMINI_BACKEND=ai_studio\n'
        'GOOGLE_AI_STUDIO_KEY=your_key_here\n'
        'GEMINI_MODEL=gemini-2.5-flash\n'
        '\n'
        '# --- Vertex AI (optional, alternative to AI Studio) ---\n'
        '# GEMINI_BACKEND=vertex_ai\n'
        '# VERTEX_AI_PROJECT_ID=\n'
        '# VERTEX_AI_LOCATION=us-central1\n'
        '# VERTEX_AI_ACCESS_TOKEN=\n'
        '\n'
        '# --- Suno Music Generation ---\n'
        'SUNO_API_KEY=your_key_here\n'
        'SUNO_BASE_URL=https://api.vectorengine.ai\n'
        'SUNO_MODEL=chirp-v5\n'
        '\n'
        '# --- Veo Video Generation ---\n'
        'VEO_MODEL=veo-3.0-fast-generate-preview\n'
        'VEO_SCENE_DURATION=8\n'
        'VEO_RESOLUTION=1080p\n'
        '\n'
        '# --- Gemini Image ---\n'
        'GEMINI_IMAGE_MODEL=gemini-2.5-flash-image\n'
        '\n'
        '# --- Agent ---\n'
        'MAX_AGENT_STEPS=15\n'
        'AGENT_TEMPERATURE=0.7\n'
        'MAX_OUTPUT_TOKENS=8192\n'
        '\n'
        '# --- General ---\n'
        'LOG_LEVEL=INFO\n',
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description="Build binary release package")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip frontend build")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts first")
    args = parser.parse_args()

    print("=" * 56)
    print("  AI Music Agent - Build Binary Release")
    print(f"  Platform: {platform.system()} {platform.machine()}")
    print("=" * 56)

    if args.clean:
        clean()

    if not args.skip_frontend:
        build_frontend()
    elif not FRONTEND_DIST.exists():
        print("  ERROR: --skip-frontend specified but frontend/dist/ not found.")
        print("         Run 'npm run build' in frontend/ first.")
        sys.exit(1)

    build_backend()
    zip_path = assemble_release()

    print("\n" + "=" * 56)
    print("  BUILD COMPLETE!")
    print(f"  Output: {zip_path}")
    print("=" * 56)


if __name__ == "__main__":
    main()

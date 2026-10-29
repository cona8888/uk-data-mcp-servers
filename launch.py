"""Start Groundwork from a downloaded checkout using only Python's standard library."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import socket
import subprocess
import sys
import time
import webbrowser
from contextlib import closing
from pathlib import Path

DEFAULT_PORT = 8765
STAMP_NAME = ".groundwork-source.sha256"


class LaunchError(RuntimeError):
    """A setup/startup problem with an actionable message for the user."""


def source_fingerprint(root: Path) -> str:
    """Include installed code, resources and distribution metadata, not user reports."""
    paths = [root / name for name in ("pyproject.toml", "README.md", "LICENSE")]
    package = root / "src" / "uk_data_mcp"
    paths.extend(
        path for path in package.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    )
    if not (root / "pyproject.toml").is_file() or not (package / "cli.py").is_file():
        raise LaunchError("Extract the whole project ZIP before running launch.py.")
    digest = hashlib.sha256(b"groundwork-launch-install-v1\0")
    for path in sorted(path for path in paths if path.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def venv_python(root: Path) -> Path:
    directory = "Scripts" if sys.platform == "win32" else "bin"
    executable = "python.exe" if sys.platform == "win32" else "python"
    return root / ".venv" / directory / executable


def ensure_environment(root: Path, *, reinstall: bool = False) -> Path:
    """Mark installation only after pip succeeds, so interrupted setup can be retried."""
    fingerprint = source_fingerprint(root)
    python = venv_python(root)
    if not python.is_file():
        print("Creating Groundwork's local Python environment...", flush=True)
        try:
            subprocess.run([sys.executable, "-m", "venv", str(root / ".venv")],
                           cwd=root, check=True)
        except subprocess.CalledProcessError as exc:
            raise LaunchError(
                "Could not create .venv. Install Python 3.11 or newer with venv/pip support "
                "(on some Linux systems, install python3-venv), then run this command again."
            ) from exc
    try:
        subprocess.run(
            [str(python), "-I", "-c",
             "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"],
            cwd=root, check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise LaunchError(
            "The existing .venv cannot run Python 3.11 or newer. Rename that .venv folder "
            "and run the launcher again with Python 3.11 or newer."
        ) from exc
    stamp = root / ".venv" / STAMP_NAME
    try:
        installed = stamp.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        installed = ""
    if reinstall or installed != fingerprint:
        print("Installing Groundwork and its pinned dependencies. Internet is needed for setup "
              "and updates...", flush=True)
        try:
            subprocess.run([str(python), "-I", "-m", "pip", "install", "."],
                           cwd=root, check=True)
        except subprocess.CalledProcessError as exc:
            raise LaunchError(
                "Setup did not finish. Check the pip message above and your internet connection, "
                "then run the launcher again. Your saved reports have not been changed."
            ) from exc
        stamp.write_text(fingerprint + "\n", encoding="utf-8")
    else:
        print("Using the existing installation. Saved examples and reports can be opened offline.",
              flush=True)
    return python


def choose_port(preferred: int, *, allow_fallback: bool) -> int:
    """Never replace an existing server; use another port for the default launch."""
    candidates = (preferred, 0) if allow_fallback and preferred else (preferred,)
    for candidate in candidates:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            try:
                listener.bind(("127.0.0.1", candidate))
            except OSError as exc:
                if allow_fallback and candidate:
                    continue
                raise LaunchError(
                    f"Port {preferred} is unavailable. Choose another with --port 8766 "
                    "or use --port 0 for an available port."
                ) from exc
            return listener.getsockname()[1]
    raise LaunchError("No local port was available.")


def health_ready(port: int) -> bool:
    """A direct loopback request: no proxy, redirects or public-provider calls."""
    try:
        with closing(http.client.HTTPConnection("127.0.0.1", port, timeout=0.5)) as connection:
            connection.request("GET", "/api/health")
            response = connection.getresponse()
            body = response.read(4097)
            if response.status != 200 or len(body) > 4096:
                return False
            value = json.loads(body)
            return isinstance(value, dict) and value.get("status") == "ok" \
                and value.get("mode") == "local"
    except (OSError, ValueError, http.client.HTTPException):
        return False


def wait_for_server(process: subprocess.Popen, port: int, *, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        code = process.poll()
        if code is not None:
            raise LaunchError(
                f"Groundwork exited during startup (code {code}). Check the message above. "
                "If its installation is incomplete, retry with --reinstall."
            )
        if health_ready(port) and process.poll() is None:
            return
        time.sleep(0.25)
    raise LaunchError("Groundwork did not become ready within 60 seconds. Check the message above.")


def stop_server(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def port_argument(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use a port from 1 to 65535, or 0 for automatic.") from exc
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("Use a port from 1 to 65535, or 0 for automatic.")
    return port


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Set up and start Groundwork locally. First setup requires internet; "
        "unchanged installations can open saved examples offline."
    )
    parser.add_argument("--no-browser", action="store_true", help="Print the URL without opening it")
    parser.add_argument("--port", type=port_argument, help="Local port (default: 8765, with fallback)")
    parser.add_argument("--reinstall", action="store_true", help="Run local installation again")
    args = parser.parse_args(argv)
    process = None
    try:
        if sys.version_info < (3, 11):
            raise LaunchError("Install Python 3.11 or newer, then run this command again.")
        root = Path(__file__).resolve().parent
        python = ensure_environment(root, reinstall=args.reinstall)
        preferred = DEFAULT_PORT if args.port is None else args.port
        port = choose_port(preferred, allow_fallback=args.port is None)
        if preferred and port != preferred:
            print(f"Port {preferred} is in use; using port {port} instead.", flush=True)
        print("Starting Groundwork...", flush=True)
        process = subprocess.Popen(
            [str(python), "-I", "-m", "uk_data_mcp.cli", "app", "--port", str(port)], cwd=root
        )
        wait_for_server(process, port)
        url = f"http://127.0.0.1:{port}/"
        print(f"Groundwork is ready: {url}\nLeave this terminal open. Press Ctrl+C to stop.",
              flush=True)
        if not args.no_browser:
            try:
                if not webbrowser.open(url, new=2):
                    print("Open the URL above in your browser.", flush=True)
            except (OSError, webbrowser.Error):
                print("Could not open the browser automatically. Open the URL above.", flush=True)
        return process.wait()
    except KeyboardInterrupt:
        print("\nGroundwork stopped.", flush=True)
        return 0
    except (LaunchError, OSError) as exc:
        print(f"Groundwork could not start: {exc}", file=sys.stderr)
        return 1
    finally:
        if process is not None:
            stop_server(process)


if __name__ == "__main__":
    raise SystemExit(main())

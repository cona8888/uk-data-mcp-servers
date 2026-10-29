"""Launcher lifecycle checks without installing packages, serving HTTP or opening a browser."""

import importlib.util
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location("groundwork_launcher", Path(__file__).parents[1] / "launch.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def project(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='synthetic'\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("Synthetic README", encoding="utf-8")
    package = tmp_path / "src" / "uk_data_mcp"
    package.mkdir(parents=True)
    (package / "cli.py").write_text("# synthetic CLI", encoding="utf-8")
    (package / "demo.json").write_text('{"synthetic":true}', encoding="utf-8")
    return tmp_path


def installed_python(root):
    python = launcher.venv_python(root)
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_text("synthetic executable; never run", encoding="utf-8")
    return python


def test_fingerprint_tracks_packaged_resources_not_reports_or_caches(tmp_path):
    root = project(tmp_path)
    original = launcher.source_fingerprint(root)
    (root / "reports").mkdir()
    (root / "reports" / "private.json").write_text("{}", encoding="utf-8")
    cache = root / "src" / "uk_data_mcp" / "__pycache__"
    cache.mkdir()
    (cache / "cli.pyc").write_bytes(b"synthetic cache")
    assert launcher.source_fingerprint(root) == original
    (root / "src" / "uk_data_mcp" / "demo.json").write_text("{}", encoding="utf-8")
    assert launcher.source_fingerprint(root) != original


def test_first_setup_creates_venv_and_unchanged_setup_skips_pip(tmp_path, monkeypatch):
    root = project(tmp_path)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert kwargs == {"cwd": root, "check": True}
        if command[1:3] == ["-m", "venv"]:
            installed_python(root)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(launcher.subprocess, "run", run)
    python = launcher.ensure_environment(root)
    assert python == launcher.venv_python(root)
    assert sum("pip" in command for command in calls) == 1
    calls.clear()
    launcher.ensure_environment(root)
    assert all("pip" not in command for command in calls)
    assert all("venv" not in command for command in calls)
    launcher.ensure_environment(root, reinstall=True)
    assert sum("pip" in command for command in calls) == 1


def test_failed_update_keeps_old_stamp_and_retries_next_time(tmp_path, monkeypatch):
    root = project(tmp_path)
    installed_python(root)
    stamp = root / ".venv" / launcher.STAMP_NAME
    stamp.write_text("old-fingerprint", encoding="utf-8")
    installs = []

    def failed_install(command, **kwargs):
        if "pip" in command:
            installs.append(command)
            raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(launcher.subprocess, "run", failed_install)
    for _ in range(2):
        with pytest.raises(launcher.LaunchError, match="Setup did not finish"):
            launcher.ensure_environment(root)
    assert len(installs) == 2
    assert stamp.read_text(encoding="utf-8") == "old-fingerprint"


def test_unsupported_existing_venv_does_not_attempt_install(tmp_path, monkeypatch):
    root = project(tmp_path)
    installed_python(root)
    run = Mock(side_effect=subprocess.CalledProcessError(1, "version check"))
    monkeypatch.setattr(launcher.subprocess, "run", run)
    with pytest.raises(launcher.LaunchError, match="Rename that .venv"):
        launcher.ensure_environment(root)
    assert run.call_count == 1
    assert "pip" not in run.call_args.args[0]


class Socket:
    def __init__(self, occupied):
        self.occupied = occupied

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def bind(self, address):
        self.address = address
        if address[1] in self.occupied:
            raise OSError("synthetic occupied port")

    def getsockname(self):
        return ("127.0.0.1", self.address[1] or 49152)


def test_default_busy_port_falls_back_but_explicit_port_is_respected(monkeypatch):
    monkeypatch.setattr(launcher.socket, "socket", lambda *args: Socket({8765}))
    assert launcher.choose_port(8765, allow_fallback=True) == 49152
    with pytest.raises(launcher.LaunchError, match="--port"):
        launcher.choose_port(8765, allow_fallback=False)
    assert launcher.choose_port(0, allow_fallback=False) == 49152


@pytest.mark.parametrize("value", ["-1", "65536", "text"])
def test_invalid_port_is_rejected_before_any_setup(value, monkeypatch):
    setup = Mock()
    monkeypatch.setattr(launcher, "ensure_environment", setup)
    with pytest.raises(SystemExit) as exc:
        launcher.main(["--port", value])
    assert exc.value.code == 2
    setup.assert_not_called()


@pytest.mark.parametrize("payload,expected", [
    ({"status": "ok", "mode": "local"}, True),
    ({"status": "ok", "mode": "remote"}, False),
    ([], False),
])
def test_health_probe_is_bounded_and_local(payload, expected, monkeypatch):
    connection = Mock()
    response = connection.getresponse.return_value
    response.status = 200
    response.read.return_value = json.dumps(payload).encode()
    factory = Mock(return_value=connection)
    monkeypatch.setattr(launcher.http.client, "HTTPConnection", factory)
    assert launcher.health_ready(8765) is expected
    factory.assert_called_once_with("127.0.0.1", 8765, timeout=0.5)
    connection.request.assert_called_once_with("GET", "/api/health")
    response.read.assert_called_once_with(4097)
    connection.close.assert_called_once()


def test_readiness_wait_stops_on_early_process_exit(monkeypatch):
    process = Mock()
    process.poll.return_value = 1
    health = Mock()
    monkeypatch.setattr(launcher, "health_ready", health)
    with pytest.raises(launcher.LaunchError, match="exited during startup"):
        launcher.wait_for_server(process, 8765)
    health.assert_not_called()


def test_readiness_polls_until_server_answers(monkeypatch):
    process = Mock()
    process.poll.return_value = None
    health = Mock(side_effect=[False, True])
    monkeypatch.setattr(launcher, "health_ready", health)
    monkeypatch.setattr(launcher.time, "sleep", Mock())
    launcher.wait_for_server(process, 8765)
    assert health.call_count == 2


@pytest.mark.parametrize("no_browser", [False, True])
def test_browser_opens_only_after_readiness_and_headless_mode_never_opens(no_browser, monkeypatch):
    events = []
    process = Mock()
    process.wait.return_value = 0
    process.poll.return_value = 0
    monkeypatch.setattr(launcher, "ensure_environment", lambda *args, **kwargs: Path("python"))
    monkeypatch.setattr(launcher, "choose_port", lambda *args, **kwargs: 8766)
    popen = Mock(return_value=process)
    monkeypatch.setattr(launcher.subprocess, "Popen", popen)
    monkeypatch.setattr(launcher, "wait_for_server", lambda *args: events.append("ready"))
    browser = Mock(side_effect=lambda *args, **kwargs: events.append("browser") or True)
    monkeypatch.setattr(launcher.webbrowser, "open", browser)
    assert launcher.main(["--no-browser"] if no_browser else []) == 0
    assert events == (["ready"] if no_browser else ["ready", "browser"])
    command = popen.call_args.args[0]
    assert command[1:] == ["-I", "-m", "uk_data_mcp.cli", "app", "--port", "8766"]


def test_startup_failure_stops_owned_child_without_opening_browser(monkeypatch):
    process = Mock()
    process.poll.return_value = None
    monkeypatch.setattr(launcher, "ensure_environment", lambda *args, **kwargs: Path("python"))
    monkeypatch.setattr(launcher, "choose_port", lambda *args, **kwargs: 8765)
    monkeypatch.setattr(launcher.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(launcher, "wait_for_server", Mock(side_effect=launcher.LaunchError("timeout")))
    browser = Mock()
    monkeypatch.setattr(launcher.webbrowser, "open", browser)
    assert launcher.main([]) == 1
    process.terminate.assert_called_once()
    browser.assert_not_called()

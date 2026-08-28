import subprocess
from types import SimpleNamespace

from backend.services.system_service import run_command


def test_run_command_success(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="ok output", stderr=""),
    )
    result = run_command(["echo", "hi"])
    assert result.success is True
    assert result.returncode == 0
    assert result.output == "ok output"


def test_run_command_nonzero_exit_is_failure(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="boom"),
    )
    result = run_command(["false"])
    assert result.success is False
    assert result.returncode == 1
    assert result.output == "boom"


def test_run_command_timeout(monkeypatch):
    def _raise(*a, **k):
        raise subprocess.TimeoutExpired(cmd="slow", timeout=1)

    monkeypatch.setattr(subprocess, "run", _raise)
    result = run_command(["slow"], timeout=1)
    assert result.success is False
    assert result.timed_out is True
    assert result.output == "Command timed out."


def test_run_command_exception(monkeypatch):
    def _raise(*a, **k):
        raise FileNotFoundError("no such file")

    monkeypatch.setattr(subprocess, "run", _raise)
    result = run_command(["missing"])
    assert result.success is False
    assert result.error is not None
    assert "no such file" in result.output


def test_run_command_empty_output_message(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    result = run_command(["noop"])
    assert result.output == "Command completed with no output."

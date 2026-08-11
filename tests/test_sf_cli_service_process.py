"""Tests for the low-level Salesforce CLI process helpers (_ProcessMixin).

Covers the fix for ``OSError: [WinError 193] %1 is not a valid Win32
application``, which is raised on Windows when a ``.cmd``/``.bat`` shim
(typically ``sf.cmd`` from ``npm install -g @salesforce/cli``) is launched
directly via ``subprocess`` without a command interpreter.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.sf_cli_service_process import _ProcessMixin


class _FakeService(_ProcessMixin):
    """Minimal host object providing what :class:`_ProcessMixin` expects."""

    def __init__(self) -> None:
        self.log = MagicMock()
        self.project_dir = Path(".")
        self.command_stats: dict[str, int] = {}

    def _track_command(self, label: str) -> None:
        self.command_stats[label] = self.command_stats.get(label, 0) + 1


class TestPrepareCommand:
    def test_wraps_cmd_executable_on_windows(self) -> None:
        service = _FakeService()
        with patch("src.core.sf_cli_service_process.platform.system", return_value="Windows"):
            result = service._prepare_command([r"C:\Program Files\sf\bin\sf.cmd", "org", "list"])
        assert result == ["cmd.exe", "/c", r"C:\Program Files\sf\bin\sf.cmd", "org", "list"]

    def test_wraps_bat_executable_case_insensitive_on_windows(self) -> None:
        service = _FakeService()
        with patch("src.core.sf_cli_service_process.platform.system", return_value="Windows"):
            result = service._prepare_command([r"C:\tools\sf.BAT", "--version"])
        assert result[:2] == ["cmd.exe", "/c"]

    def test_leaves_native_exe_untouched_on_windows(self) -> None:
        service = _FakeService()
        with patch("src.core.sf_cli_service_process.platform.system", return_value="Windows"):
            result = service._prepare_command([r"C:\Program Files\sf\bin\sf.exe", "org", "list"])
        assert result == [r"C:\Program Files\sf\bin\sf.exe", "org", "list"]

    def test_does_not_wrap_on_non_windows_platform(self) -> None:
        service = _FakeService()
        with patch("src.core.sf_cli_service_process.platform.system", return_value="Linux"):
            result = service._prepare_command(["/usr/local/bin/sf.cmd", "org", "list"])
        assert result == ["/usr/local/bin/sf.cmd", "org", "list"]

    def test_empty_command_is_returned_unchanged(self) -> None:
        service = _FakeService()
        assert service._prepare_command([]) == []


class TestDescribeCliLaunchError:
    def test_generic_oserror_returns_short_message(self) -> None:
        service = _FakeService()
        exc = OSError("some other failure")
        message = service._describe_cli_launch_error(exc, ["sf", "org", "list"])
        assert message == "Erreur lors de l'execution de la commande Salesforce CLI : some other failure"

    def test_winerror_193_returns_actionable_guidance(self) -> None:
        service = _FakeService()
        exc = OSError(193, "%1 is not a valid Win32 application")
        exc.winerror = 193
        message = service._describe_cli_launch_error(exc, [r"C:\Program Files\sf\bin\sf.cmd", "org", "list"])

        assert "sf.cmd" in message
        assert "npm install -g @salesforce/cli" in message
        assert "developer.salesforce.com/tools/salesforcecli" in message
        assert "Solutions recommandees" in message

    def test_missing_command_falls_back_to_generic_executable_name(self) -> None:
        service = _FakeService()
        exc = OSError(193, "%1 is not a valid Win32 application")
        exc.winerror = 193
        message = service._describe_cli_launch_error(exc, [])
        assert '"sf"' in message


class TestRunJsonUsesPreparedCommand:
    def test_run_json_invokes_subprocess_with_prepared_command(self) -> None:
        service = _FakeService()
        completed = MagicMock(stdout='{"status": 0, "result": {"ok": true}}', stderr="", returncode=0)
        with patch("src.core.sf_cli_service_process.platform.system", return_value="Windows"), \
             patch("src.core.sf_cli_service_process.subprocess.run", return_value=completed) as mock_run:
            result = service._run_json([r"C:\sf\sf.cmd", "org", "list", "--json"], label="org list")

        called_command = mock_run.call_args[0][0]
        assert called_command[:2] == ["cmd.exe", "/c"]
        assert result == {"ok": True}
        assert service.command_stats["org list"] == 1

    def test_run_json_launch_failure_logs_actionable_message(self) -> None:
        service = _FakeService()
        exc = OSError(193, "%1 is not a valid Win32 application")
        exc.winerror = 193
        with patch("src.core.sf_cli_service_process.platform.system", return_value="Windows"), \
             patch("src.core.sf_cli_service_process.subprocess.run", side_effect=exc):
            result = service._run_json([r"C:\sf\sf.cmd", "org", "list", "--json"], label="org list")

        assert result == {}
        service.log.assert_called_once()
        logged_message = service.log.call_args[0][0]
        assert "sf.cmd" in logged_message
        assert "Solutions recommandees" in logged_message

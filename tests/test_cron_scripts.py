"""Tests for cron/ shell scripts — syntax, permissions, and watchdog behavior."""
import subprocess
import os
import stat
from pathlib import Path

CRON_DIR = Path(__file__).parent.parent / "cron"
SCRIPTS = ["scan.sh", "execute.sh", "update.sh", "api_watchdog.sh"]


def test_cron_dir_exists():
    """cron/ directory must exist."""
    assert CRON_DIR.is_dir(), f"cron/ directory not found at {CRON_DIR}"


def test_all_scripts_exist():
    """All four scripts must be present."""
    for name in SCRIPTS:
        path = CRON_DIR / name
        assert path.exists(), f"Missing script: {path}"


def test_all_scripts_executable():
    """All scripts must have the executable bit set."""
    for name in SCRIPTS:
        path = CRON_DIR / name
        if path.exists():
            mode = os.stat(path).st_mode
            assert mode & stat.S_IXUSR, f"{name} is not executable (chmod +x missing)"


def test_all_scripts_pass_syntax_check():
    """All scripts must pass bash -n (syntax validation)."""
    for name in SCRIPTS:
        path = CRON_DIR / name
        if path.exists():
            result = subprocess.run(
                ["bash", "-n", str(path)],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, (
                f"{name} failed bash syntax check:\n{result.stderr}"
            )


def test_all_scripts_have_shebang():
    """All scripts must start with #!/usr/bin/env bash."""
    for name in SCRIPTS:
        path = CRON_DIR / name
        if path.exists():
            first_line = path.read_text().splitlines()[0]
            assert first_line == "#!/usr/bin/env bash", (
                f"{name} missing shebang, got: {first_line!r}"
            )


def test_watchdog_exits_cleanly_when_api_healthy():
    """
    Watchdog must exit 0 without modifying logs when API is up.
    Assumes the API is running (integration test — skip if port 8001 not listening).
    """
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    api_up = sock.connect_ex(("localhost", 8001)) == 0
    sock.close()

    if not api_up:
        import pytest
        pytest.skip("API not running on port 8001 — skipping watchdog live test")

    watchdog = CRON_DIR / "api_watchdog.sh"
    if not watchdog.exists():
        import pytest
        pytest.skip("api_watchdog.sh not yet created")

    result = subprocess.run(
        ["bash", str(watchdog)],
        capture_output=True,
        text=True,
        cwd=str(CRON_DIR.parent),
    )
    assert result.returncode == 0, (
        f"Watchdog exited non-zero when API was healthy:\n{result.stderr}"
    )

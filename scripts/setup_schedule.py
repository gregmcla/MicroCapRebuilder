#!/usr/bin/env python3
"""
Schedule Setup for Mommy Bot.

Sets up automated daily runs using cron (Linux/Mac) or provides
instructions for Windows Task Scheduler.

Usage:
    python scripts/setup_schedule.py --install     # Install cron job
    python scripts/setup_schedule.py --remove      # Remove cron job
    python scripts/setup_schedule.py --status      # Check current schedule
    python scripts/setup_schedule.py --test        # Test the daily run

Options:
    --time HH:MM    Set custom run time (default: 16:30 / 4:30 PM)
    --timezone TZ   Set timezone (default: America/New_York)
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

# ─── Configuration ───────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
SCRIPT_PATH = PROJECT_ROOT / "run_daily.sh"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "daily_run.log"

# Cron job identifier (used to find/remove our job)
CRON_MARKER = "# MOMMY_BOT_DAILY_RUN"


def get_current_cron_jobs():
    """Get current user's cron jobs."""
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout
        return ""
    except FileNotFoundError:
        return None  # cron not available


def has_existing_job():
    """Check if Mommy Bot cron job already exists."""
    jobs = get_current_cron_jobs()
    if jobs is None:
        return None
    return CRON_MARKER in jobs


def install_cron_job(hour: int = 16, minute: int = 30, timezone: str = "America/New_York"):
    """Install the cron job for daily runs."""

    # Ensure logs directory exists
    LOG_DIR.mkdir(exist_ok=True)

    # Check if cron is available
    current_jobs = get_current_cron_jobs()
    if current_jobs is None:
        print("❌ Cron is not available on this system")
        print("\nFor Windows, use Task Scheduler instead:")
        print(f"  1. Open Task Scheduler")
        print(f"  2. Create Basic Task -> 'Mommy Bot Daily Run'")
        print(f"  3. Trigger: Daily at {hour:02d}:{minute:02d}")
        print(f"  4. Action: Start a program")
        print(f"     Program: bash")
        print(f"     Arguments: {SCRIPT_PATH}")
        print(f"     Start in: {PROJECT_ROOT}")
        return False

    # Check if already installed
    if CRON_MARKER in current_jobs:
        print("⚠️  Mommy Bot cron job already exists")
        print("   Use --remove first, then --install to change settings")
        return False

    # Build cron expression
    # Run Monday-Friday at specified time
    cron_time = f"{minute} {hour} * * 1-5"

    # Build the command
    # Use full paths and redirect output to log file
    cron_command = (
        f"cd {PROJECT_ROOT} && "
        f"./run_daily.sh >> {LOG_FILE} 2>&1"
    )

    # Full cron line
    cron_line = f"{cron_time} {cron_command} {CRON_MARKER}\n"

    # Add to existing jobs
    new_jobs = current_jobs + cron_line

    # Install new crontab
    try:
        process = subprocess.Popen(
            ["crontab", "-"],
            stdin=subprocess.PIPE,
            text=True
        )
        process.communicate(input=new_jobs)

        if process.returncode == 0:
            print(f"✅ Cron job installed successfully!")
            print(f"")
            print(f"   Schedule: {hour:02d}:{minute:02d} Mon-Fri")
            print(f"   Timezone: System timezone (configure TZ if needed)")
            print(f"   Log file: {LOG_FILE}")
            print(f"")
            print(f"   The bot will run automatically at market close.")
            print(f"   Use 'python scripts/setup_schedule.py --status' to verify.")
            return True
        else:
            print("❌ Failed to install cron job")
            return False
    except Exception as e:
        print(f"❌ Error installing cron job: {e}")
        return False


def remove_cron_job():
    """Remove the Mommy Bot cron job."""
    current_jobs = get_current_cron_jobs()

    if current_jobs is None:
        print("❌ Cron is not available on this system")
        return False

    if CRON_MARKER not in current_jobs:
        print("ℹ️  No Mommy Bot cron job found")
        return True

    # Filter out our job
    new_jobs = "\n".join(
        line for line in current_jobs.split("\n")
        if CRON_MARKER not in line
    )

    # Ensure it ends with newline
    if new_jobs and not new_jobs.endswith("\n"):
        new_jobs += "\n"

    # Install filtered crontab
    try:
        process = subprocess.Popen(
            ["crontab", "-"],
            stdin=subprocess.PIPE,
            text=True
        )
        process.communicate(input=new_jobs)

        if process.returncode == 0:
            print("✅ Cron job removed successfully")
            return True
        else:
            print("❌ Failed to remove cron job")
            return False
    except Exception as e:
        print(f"❌ Error removing cron job: {e}")
        return False


def show_status():
    """Show current scheduling status."""
    print("\n─── Mommy Bot Schedule Status ───\n")

    current_jobs = get_current_cron_jobs()

    if current_jobs is None:
        print("❌ Cron is not available on this system")
        print("   Consider using Task Scheduler (Windows) or launchd (macOS)")
        return

    # Find our job
    our_job = None
    for line in current_jobs.split("\n"):
        if CRON_MARKER in line:
            our_job = line
            break

    if our_job:
        # Parse the cron time
        parts = our_job.split()
        if len(parts) >= 5:
            minute, hour = parts[0], parts[1]
            print(f"✅ Scheduled: {hour}:{minute} Mon-Fri")
            print(f"   Log file: {LOG_FILE}")

            # Check if log exists and show last run
            if LOG_FILE.exists():
                stat = LOG_FILE.stat()
                last_modified = datetime.fromtimestamp(stat.st_mtime)
                print(f"   Last run: {last_modified.strftime('%Y-%m-%d %H:%M:%S')}")

                # Show last few lines of log
                try:
                    with open(LOG_FILE, "r") as f:
                        lines = f.readlines()
                        if lines:
                            print(f"\n   Last log entries:")
                            for line in lines[-5:]:
                                print(f"   {line.rstrip()}")
                except:
                    pass
    else:
        print("❌ No scheduled job found")
        print("   Run 'python scripts/setup_schedule.py --install' to set up")

    print("")


def test_run():
    """Test the daily run script."""
    print("\n─── Testing Daily Run ───\n")

    if not SCRIPT_PATH.exists():
        print(f"❌ Script not found: {SCRIPT_PATH}")
        return False

    print(f"Running: {SCRIPT_PATH}")
    print("=" * 60)

    try:
        result = subprocess.run(
            ["bash", str(SCRIPT_PATH)],
            cwd=PROJECT_ROOT,
            timeout=600  # 10 minute timeout
        )

        print("=" * 60)
        if result.returncode == 0:
            print("✅ Test run completed successfully")
            return True
        else:
            print(f"❌ Test run failed with exit code {result.returncode}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Test run timed out (>10 minutes)")
        return False
    except Exception as e:
        print(f"❌ Error running test: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Set up automated daily runs for Mommy Bot"
    )

    parser.add_argument(
        "--install", action="store_true",
        help="Install the cron job for daily runs"
    )
    parser.add_argument(
        "--remove", action="store_true",
        help="Remove the cron job"
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show current schedule status"
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Test run the daily script"
    )
    parser.add_argument(
        "--time", type=str, default="16:30",
        help="Run time in HH:MM format (default: 16:30)"
    )
    parser.add_argument(
        "--timezone", type=str, default="America/New_York",
        help="Timezone (default: America/New_York)"
    )

    args = parser.parse_args()

    # Parse time
    try:
        hour, minute = map(int, args.time.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError()
    except:
        print(f"❌ Invalid time format: {args.time}")
        print("   Use HH:MM format (e.g., 16:30)")
        sys.exit(1)

    # Handle commands
    if args.install:
        install_cron_job(hour, minute, args.timezone)
    elif args.remove:
        remove_cron_job()
    elif args.test:
        test_run()
    elif args.status:
        show_status()
    else:
        # Default to status
        show_status()
        print("Commands:")
        print("  --install    Install scheduled daily run")
        print("  --remove     Remove scheduled run")
        print("  --status     Show current status")
        print("  --test       Test run the daily script")
        print("")
        print("Options:")
        print("  --time HH:MM   Set run time (default: 16:30)")


if __name__ == "__main__":
    main()

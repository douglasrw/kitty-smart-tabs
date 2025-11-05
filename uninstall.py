#!/usr/bin/env python3
"""Uninstaller for Smart Tabs kitten."""

import os
import subprocess
from pathlib import Path


def stop_daemon():
    """Stop the Smart Tabs daemon using PID file."""
    print("🛑 Stopping Smart Tabs daemon...")
    try:
        # Use PID file for precise daemon shutdown
        from smart_tabs.tempfiles import get_temp_dir
        pid_file = get_temp_dir() / 'daemon.pid'

        if not pid_file.exists():
            print("   ✓ Daemon not running")
            return

        # Read PID and send SIGTERM for graceful shutdown
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 15)  # SIGTERM
        print(f"   ✓ Daemon stopped (PID {pid})")

    except ProcessLookupError:
        # Process not running, clean up stale PID file
        print("   ✓ Daemon not running (stale PID file removed)")
        try:
            pid_file.unlink()
        except Exception:
            pass
    except Exception as e:
        print(f"   ⚠️  Could not stop daemon: {e}")
        # Fallback to pkill as last resort
        try:
            subprocess.run(['pkill', '-f', 'smart_tabs.*daemon'], capture_output=True)
            print("   ✓ Daemon stopped (fallback method)")
        except Exception:
            pass


def remove_shell_hooks():
    """Remove shell hooks from RC files."""
    print("\n🧹 Removing shell hooks...")

    rc_files = [
        Path.home() / '.zshrc',
        Path.home() / '.bashrc',
    ]

    for rc_file in rc_files:
        if not rc_file.exists():
            continue

        content = rc_file.read_text()

        # Check if hooks exist
        if 'Smart Tabs' not in content:
            continue

        # Remove Smart Tabs section
        lines = content.split('\n')
        new_lines = []
        skip = False

        for line in lines:
            if '# Smart Tabs' in line:
                skip = True
            elif skip and line.strip() == '' and new_lines and new_lines[-1].strip() == '':
                skip = False
                continue
            elif skip and not line.strip().startswith(('#', 'if', 'function', '_smart_tabs', 'fi', '}')):
                skip = False

            if not skip:
                new_lines.append(line)

        # Write back
        rc_file.write_text('\n'.join(new_lines))
        print(f"   ✓ Cleaned {rc_file.name}")


def remove_files():
    """Remove Smart Tabs files."""
    print("\n🗑️  Removing files...")

    files_to_remove = [
        Path.home() / '.config/kitty/kittens/smart_tabs',
        Path.home() / '.config/kitty/smart_tabs.conf',
        Path.home() / '.config/kitty/tab_color_debug.log',
        Path.home() / '.config/kitty/smart_tabs_daemon.log',
    ]

    for path in files_to_remove:
        if path.exists():
            if path.is_dir():
                import shutil
                shutil.rmtree(path)
            else:
                path.unlink()
            print(f"   ✓ Removed {path.name}")


def clean_temp_files():
    """Clean up temp CWD files from both old and new locations."""
    print("\n🧹 Cleaning temp files...")

    count = 0

    # Clean old location (/tmp)
    temp_pattern = Path('/tmp')
    for temp_file in temp_pattern.glob('kitty_tab_*_cwd'):
        try:
            temp_file.unlink()
            count += 1
        except Exception:
            pass

    # Clean new secure location using tempfiles module
    try:
        from smart_tabs.tempfiles import cleanup_temp_files
        cleanup_temp_files()
        # Count files in new location too
        from smart_tabs.tempfiles import get_temp_dir
        temp_dir = get_temp_dir()
        if temp_dir.exists():
            count += len(list(temp_dir.glob('tab_*_cwd')))
    except Exception:
        pass

    if count > 0:
        print(f"   ✓ Removed {count} temp files")
    else:
        print("   No temp files to clean")


def print_completion():
    """Print uninstall completion message."""
    print("\n" + "="*60)
    print("✅ Smart Tabs uninstalled")
    print("="*60)
    print("\n📋 What was removed:")
    print("   ✓ Smart Tabs kitten")
    print("   ✓ Shell hooks")
    print("   ✓ Configuration files")
    print("   ✓ Temp files")
    print("   ✓ Background daemon")
    print("\n🔄 Final step:")
    print("   Reload your shell: source ~/.zshrc")
    print()


def main():
    """Main uninstall process."""
    print("🗑️  Smart Tabs Uninstaller")
    print("="*60)

    response = input("\nAre you sure you want to uninstall? (y/N): ")
    if response.lower() != 'y':
        print("Uninstall cancelled")
        return

    try:
        stop_daemon()
        remove_shell_hooks()
        remove_files()
        clean_temp_files()
        print_completion()
    except Exception as e:
        print(f"\n❌ Uninstall failed: {e}")
        return 1

    return 0


if __name__ == '__main__':
    exit(main())

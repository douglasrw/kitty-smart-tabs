#!/usr/bin/env python3
"""Migration script from old tab coloring setup to Smart Tabs kitten."""

import os
import shutil
import subprocess
from pathlib import Path


def backup_old_files():
    """Backup existing configuration."""
    backup_dir = Path.home() / '.config/kitty/smart_tabs_backup'
    backup_dir.mkdir(parents=True, exist_ok=True)

    print("📦 Backing up old configuration...")

    old_files = [
        Path.home() / '.config/kitty/color_tabs_by_cwd.py',
        Path.home() / '.config/kitty/poll_tab_updates.sh',
    ]

    for old_file in old_files:
        if old_file.exists():
            dest = backup_dir / old_file.name
            shutil.copy2(old_file, dest)
            print(f"   ✓ Backed up {old_file.name}")

    print(f"   Backups saved to: {backup_dir}")


def stop_old_poller():
    """Stop the old background poller."""
    print("\n🛑 Stopping old background poller...")

    try:
        subprocess.run(['pkill', '-f', 'poll_tab_updates.sh'],
                      capture_output=True)
        print("   ✓ Old poller stopped")
    except Exception as e:
        print(f"   ⚠️  Could not stop poller: {e}")


def clean_shell_rc():
    """Remove old shell hooks from RC files."""
    print("\n🧹 Cleaning old shell hooks...")

    rc_files = [
        Path.home() / '.zshrc',
        Path.home() / '.bashrc',
    ]

    for rc_file in rc_files:
        if not rc_file.exists():
            continue

        content = rc_file.read_text()

        # Remove old Kitty tab coloring section
        lines = content.split('\n')
        new_lines = []
        skip = False

        for line in lines:
            if 'Kitty tab coloring' in line or 'poll_tab_updates' in line:
                skip = True
            elif 'color_tabs_by_cwd' in line:
                skip = True
            elif skip and line.strip() and not line.strip().startswith('#'):
                skip = False

            if not skip:
                new_lines.append(line)

        if len(new_lines) != len(lines):
            rc_file.write_text('\n'.join(new_lines))
            print(f"   ✓ Cleaned {rc_file.name}")


def remove_old_files():
    """Remove old implementation files."""
    print("\n🗑️  Removing old files...")

    old_files = [
        Path.home() / '.config/kitty/color_tabs_by_cwd.py',
        Path.home() / '.config/kitty/poll_tab_updates.sh',
    ]

    for old_file in old_files:
        if old_file.exists():
            old_file.unlink()
            print(f"   ✓ Removed {old_file.name}")


def run_installer():
    """Run the new installer."""
    print("\n🚀 Installing Smart Tabs kitten...")

    install_script = Path(__file__).parent / 'install.py'
    try:
        subprocess.run([str(install_script)], check=True)
    except Exception as e:
        print(f"\n❌ Installation failed: {e}")
        print("   Please run ./install.py manually")
        return False

    return True


def print_completion():
    """Print migration completion message."""
    print("\n" + "="*60)
    print("✨ Migration complete!")
    print("="*60)
    print("\n📋 What changed:")
    print("   ✓ Old files backed up to ~/.config/kitty/smart_tabs_backup")
    print("   ✓ Old shell hooks removed")
    print("   ✓ Smart Tabs kitten installed")
    print("   ✓ New shell hooks added")
    print("\n🔄 Next steps:")
    print("   1. Reload your shell: source ~/.zshrc")
    print("   2. Check tabs are working")
    print("   3. Customize config: ~/.config/kitty/smart_tabs.conf")
    print("\n💡 Old temp files (/tmp/kitty_tab_*_cwd) are preserved")
    print("   Smart Tabs uses the same temp file system, so no disruption!")
    print()


def main():
    """Main migration process."""
    print("🔄 Smart Tabs Migration Tool")
    print("="*60)
    print("\nThis will migrate your existing tab coloring setup")
    print("to the new Smart Tabs kitten system.")

    response = input("\nContinue? (y/N): ")
    if response.lower() != 'y':
        print("Migration cancelled")
        return

    try:
        backup_old_files()
        stop_old_poller()
        clean_shell_rc()
        remove_old_files()

        if run_installer():
            print_completion()
        else:
            print("\n⚠️  Installation step failed - see above")
            print("   Your old files are backed up and safe")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        print("   Your old files are backed up at:")
        print("   ~/.config/kitty/smart_tabs_backup")
        return 1

    return 0


if __name__ == '__main__':
    exit(main())

#!/usr/bin/env python3
"""Installer for Smart Tabs kitten."""

import os
import shutil
import sys
from pathlib import Path


def detect_shell():
    """Detect user's shell.

    Returns:
        'zsh', 'bash', or None if unsupported
    """
    shell_env = os.environ.get('SHELL', '')
    if 'zsh' in shell_env:
        return 'zsh'
    elif 'bash' in shell_env:
        return 'bash'
    return None


def get_shell_rc_path(shell):
    """Get path to shell RC file.

    Args:
        shell: 'zsh' or 'bash'

    Returns:
        Path to RC file
    """
    home = Path.home()
    if shell == 'zsh':
        return home / '.zshrc'
    elif shell == 'bash':
        # Check for .bash_profile first, then .bashrc
        bash_profile = home / '.bash_profile'
        if bash_profile.exists():
            return bash_profile
        return home / '.bashrc'
    return None


def install_kitten():
    """Install smart_tabs kitten to Kitty config directory."""
    source_dir = Path(__file__).parent / 'smart_tabs'
    dest_dir = Path.home() / '.config/kitty/kittens/smart_tabs'

    print(f"📦 Installing kitten to {dest_dir}")

    # Create destination directory
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Copy all Python files
    for py_file in source_dir.glob('*.py'):
        shutil.copy2(py_file, dest_dir / py_file.name)

    print("✓ Kitten installed")


def install_config():
    """Install example config file."""
    source_config = Path(__file__).parent / 'smart_tabs.conf.example'
    dest_config = Path.home() / '.config/kitty/smart_tabs.conf'

    if dest_config.exists():
        print(f"⚠️  Config already exists at {dest_config}")
        response = input("Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Skipping config installation")
            return

    print(f"📝 Installing config to {dest_config}")
    shutil.copy2(source_config, dest_config)
    print("✓ Config installed")


def install_shell_hook(shell):
    """Install shell integration hook.

    Args:
        shell: 'zsh' or 'bash'
    """
    rc_file = get_shell_rc_path(shell)
    if not rc_file:
        print(f"❌ Could not find RC file for {shell}")
        return False

    # Read hook file
    hook_file = Path(__file__).parent / 'shell_hooks' / f'{shell}.sh'
    if not hook_file.exists():
        print(f"❌ Hook file not found: {hook_file}")
        return False

    hook_content = hook_file.read_text()

    # Check if already installed
    rc_content = rc_file.read_text() if rc_file.exists() else ''
    if 'Smart Tabs shell integration' in rc_content:
        print(f"⚠️  Shell hook already installed in {rc_file}")
        return True

    # Append hook to RC file
    print(f"📝 Adding shell hook to {rc_file}")

    with open(rc_file, 'a') as f:
        f.write('\n\n# Smart Tabs - Installed by kitty-smart-tabs\n')
        f.write(hook_content)
        f.write('\n')

    print("✓ Shell hook installed")
    return True


def add_python_path():
    """Ensure smart_tabs package is in PYTHONPATH."""
    kittens_dir = Path.home() / '.config/kitty/kittens'

    # Check if already in PYTHONPATH
    python_path = os.environ.get('PYTHONPATH', '')
    if str(kittens_dir) in python_path:
        return

    print("\n📌 To use smart_tabs as a Python module, add this to your shell RC:")
    print(f'   export PYTHONPATH="{kittens_dir}:$PYTHONPATH"')


def print_next_steps():
    """Print post-installation instructions."""
    print("\n" + "="*60)
    print("✨ Smart Tabs installed successfully!")
    print("="*60)
    print("\n📋 Next steps:")
    print("\n1. Reload your shell:")
    print("   source ~/.zshrc    # or ~/.bashrc")
    print("\n2. (Optional) Add keyboard shortcut to kitty.conf:")
    print("   map f5 kitten smart_tabs")
    print("\n3. (Optional) Customize colors in:")
    print("   ~/.config/kitty/smart_tabs.conf")
    print("\n4. Enjoy automatic tab coloring and command detection!")
    print("\n💡 Tips:")
    print("   - Tabs auto-color by directory")
    print("   - Commands show within 2 seconds")
    print("   - Same directory = same color")
    print("\n🐛 Debug mode:")
    print("   python3 -m smart_tabs.kitten --debug")
    print("   tail ~/.config/kitty/tab_color_debug.log")
    print()


def main():
    """Main installer."""
    print("🐱 Smart Tabs Installer")
    print("="*60)

    # Detect shell
    shell = detect_shell()
    if not shell:
        print("❌ Unsupported shell. Only zsh and bash are supported.")
        print(f"   Your shell: {os.environ.get('SHELL', 'unknown')}")
        sys.exit(1)

    print(f"✓ Detected shell: {shell}")

    # Install components
    try:
        install_kitten()
        install_config()
        install_shell_hook(shell)
        add_python_path()
        print_next_steps()
    except Exception as e:
        print(f"\n❌ Installation failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

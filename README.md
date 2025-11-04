# Smart Tabs for Kitty

Intelligent tab coloring and command detection for the [Kitty terminal emulator](https://sw.kovidgoyal.net/kitty/).

## Features

- **🎨 Automatic Color Coding**: Tabs in the same directory get the same color
- **⚡ Live Command Detection**: Shows running command in tab title (e.g., `[nvim]`, `[git]`)
- **👁️ Visual Active Tab**: Bold arrows and styling make active tab unmistakable
- **🔄 Real-time Updates**: Auto-updates on directory changes and command execution
- **⚙️ Highly Configurable**: Customize colors, filters, and behavior via INI config
- **🚀 Zero User Interaction**: Works automatically once installed

## What It Looks Like

**Active Tab:**
```
▶▶▶▶ 1: mix_decode [nvim] ◀◀◀◀
```

**Inactive Tabs:**
```
2: dev        3: mix_decode
```

- Same directory tabs share the same color
- Running commands appear in brackets
- Active tab has arrows and bold styling

## Requirements

- **Kitty terminal** (with remote control enabled)
- **Python 3.7+**
- **zsh or bash** shell

## Quick Install

```bash
git clone https://github.com/douglasrw/kitty-smart-tabs
cd kitty-smart-tabs
./install.py
```

Then reload your shell:
```bash
source ~/.zshrc    # or ~/.bashrc
```

## Manual Installation

1. **Copy kitten files:**
   ```bash
   cp -r smart_tabs ~/.config/kitty/kittens/
   ```

2. **Copy config:**
   ```bash
   cp smart_tabs.conf.example ~/.config/kitty/smart_tabs.conf
   ```

3. **Add shell hook** to `~/.zshrc` or `~/.bashrc`:
   ```bash
   cat shell_hooks/zsh.sh >> ~/.zshrc    # or bash.sh >> ~/.bashrc
   ```

4. **Reload shell:**
   ```bash
   source ~/.zshrc
   ```

## Configuration

Edit `~/.config/kitty/smart_tabs.conf`:

```ini
[colors]
# Customize color palette (hex colors)
palette = #2b8eff,#a9dc76,#ab9df2,#ffd866,#78dce8,#f48771

[behavior]
show_commands = true      # Show running commands
show_tab_index = true     # Show tab numbers
poll_interval = 2         # Update frequency (seconds)

[filters]
# Customize which commands to ignore/prioritize
priority_commands = nvim,vim,claude,git,docker
ignored_commands = npm,yarn,sleep
```

## How It Works

### Directory Tracking
- Shell hook writes current directory to `/tmp/kitty_tab_{ID}_cwd` on every `cd`
- MD5 hash of path determines color (consistent across sessions)

### Command Detection
- Background daemon polls every 2 seconds
- Detects foreground processes via `kitty @ ls`
- Filters out shells, build tools, helpers
- Prioritizes user-facing commands (editors, dev tools)

### Smart Filtering
**Shows:**
- Editors: `nvim`, `vim`, `emacs`, `code`
- Dev tools: `git`, `docker`, `claude`
- Scripts: `python script.py` → shows `[script]` not `[python]`

**Filters out:**
- Shells: `zsh`, `bash`
- Build tools: `npm`, `yarn`, `make`
- Helpers: `mcp_server_*`, `*-daemon`

## Keyboard Shortcuts (Optional)

Add to `~/.config/kitty/kitty.conf`:

```
# Manual update (if auto-update isn't working)
map f5 kitten smart_tabs

# Update on new tab
map cmd+t launch --type=tab --cwd=~ kitten smart_tabs
```

## Troubleshooting

### Tabs not updating?

**Check daemon is running:**
```bash
ps aux | grep smart_tabs
```

**Restart daemon:**
```bash
pkill -f smart_tabs
# Reload shell to restart it
source ~/.zshrc
```

### Debug mode:

```bash
python3 -m smart_tabs.kitten --debug
tail ~/.config/kitty/tab_color_debug.log
```

### Colors not showing?

Check Kitty remote control is enabled in `~/.config/kitty/kitty.conf`:
```
allow_remote_control yes
listen_on unix:/tmp/kitty
```

### CWD not tracking?

Verify shell hook is installed:
```bash
grep "Smart Tabs" ~/.zshrc    # or ~/.bashrc
```

## Uninstall

```bash
./uninstall.py
```

Or manually:
1. Remove shell hook from `~/.zshrc`/`~/.bashrc`
2. `rm -rf ~/.config/kitty/kittens/smart_tabs`
3. `rm ~/.config/kitty/smart_tabs.conf`
4. `pkill -f smart_tabs`

## Migration from Old Setup

If you have an existing tab coloring setup:

```bash
./migrate.py
```

This will:
- Stop old background processes
- Migrate your color preferences
- Install new system
- Clean up old files

## Development

**Project Structure:**
```
kitty-smart-tabs/
├── smart_tabs/           # Python package
│   ├── kitten.py        # Main kitten entry point
│   ├── daemon.py        # Background poller
│   ├── core.py          # Tab update logic
│   ├── colors.py        # Color generation
│   └── config.py        # INI config parser
├── shell_hooks/         # Shell integration
│   ├── zsh.sh
│   └── bash.sh
├── install.py           # Automated installer
└── README.md
```

**Run tests:**
```bash
python3 -m pytest tests/
```

## Contributing

Contributions welcome! Please:
1. Fork the repo
2. Create a feature branch
3. Add tests if applicable
4. Submit a pull request

## License

MIT License - see LICENSE file

## Credits

Created by Douglas Walseth

Built on top of Kitty's powerful [remote control](https://sw.kovidgoyal.net/kitty/remote-control/) and [kittens](https://sw.kovidgoyal.net/kitty/kittens_intro/) APIs.

## Support

- **Issues**: [GitHub Issues](https://github.com/douglasrw/kitty-smart-tabs/issues)
- **Discussions**: [GitHub Discussions](https://github.com/douglasrw/kitty-smart-tabs/discussions)

---

⭐ If you find this useful, please star the repo!

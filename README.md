# Smart Tabs for Kitty

Intelligent tab coloring and live command detection for the [Kitty terminal emulator](https://sw.kovidgoyal.net/kitty/).

## Features

- **🎨 Automatic Color Coding**: Tabs in same directory get same color (16-color palette for minimal collision)
- **⚡ Live Command Detection**: Shows running commands in tab titles (e.g., `[nvim]`, `[git]`)
- **👁️ Visual Active Tab**: Bold arrows and styling make active tab unmistakable
- **🔄 Real-time Updates**: Auto-updates on directory changes and command execution
- **⚙️ Highly Configurable**: Customize colors, filters, and behavior via INI config
- **🚀 Zero User Interaction**: Works automatically once installed
- **🔒 Secure**: Validated inputs, atomic file operations, owner-only permissions
- **⚡ Performance Optimized**: Adaptive polling, socket caching, early bailout for unchanged tabs

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
- Tab numbers optional (configurable)

## Why Use This?

**Problem:** With many tabs open, it's hard to:
- Find tabs in the same project
- Know what's running where
- Identify the active tab quickly

**Solution:** Smart Tabs provides:
- Visual grouping via color coding
- Live command feedback
- Clear active tab indication

## Requirements

- **Kitty terminal** 0.26.0+
- **Python 3.7+**
- **zsh or bash** shell (other shells work with reduced functionality)
- **macOS or Linux** (process CWD detection)

---

## Prerequisites

**⚠️ CRITICAL:** Enable Kitty remote control **BEFORE** installation.

Edit `~/.config/kitty/kitty.conf`:
```conf
allow_remote_control yes
listen_on unix:/tmp/kitty
```

Restart Kitty, then proceed with installation.

**Verify remote control works:**
```bash
kitty @ ls
# Should output JSON with window/tab info
```

If this fails, Smart Tabs won't work. Check Kitty's [remote control docs](https://sw.kovidgoyal.net/kitty/remote-control/).

---

## Installation

### Quick Install (Recommended)

```bash
git clone https://github.com/douglasrw/kitty-smart-tabs
cd kitty-smart-tabs
python3 install.py
```

Then reload your shell:
```bash
source ~/.zshrc    # or ~/.bashrc
```

### Manual Installation

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

---

## Verify Installation

After installing, verify everything works:

### 1. Check daemon is running
```bash
ps aux | grep smart_tabs | grep daemon
```

Should show a python process running `smart_tabs.daemon`.

### 2. Open new tab
Press `Cmd+T` (macOS) or `Ctrl+Shift+T` (Linux).

Tab should show:
- Tab number (e.g., `1:`)
- Directory name (e.g., `home`)
- Color coding

### 3. Test command detection
```bash
nvim test.txt
```

Tab title should update to show: `1: dirname [nvim]`

### 4. Test color coding
```bash
# Tab 1
cd /tmp

# Open new tab (Tab 2)
cd /tmp

# Both tabs should have the same color
```

**If verification fails**, see [Troubleshooting](#troubleshooting).

---

## Configuration

Edit `~/.config/kitty/smart_tabs.conf`:

```ini
[colors]
# 16-color palette for better distribution (reduced collisions)
palette = #2b8eff,#a9dc76,#ab9df2,#ffd866,#78dce8,#f48771,#ff6188,#fc9867,#79dac8,#5ad4e6,#9ecd6f,#e0af68,#bb9af7,#7dcfff,#ff9e64,#7aa2f7

[behavior]
show_commands = true      # Show running commands in brackets
show_tab_index = true     # Show tab numbers (1:, 2:, etc.)
poll_interval = 2         # Update frequency (seconds, adaptive: 2s active → 8s idle)
max_dir_length = 30       # Truncate long directory names
max_cmd_length = 30       # Truncate long command names

[active_tab]
arrows = ▶▶▶▶              # Arrows surrounding active tab title

[filters]
# Commands to prioritize (always show these)
priority_commands = nvim,vim,vi,emacs,code,nano,claude,git,docker,kubectl

# Commands to ignore (don't show these)
ignored_commands = npm,yarn,sleep,cat,grep,sed,awk,pip,gem,bundle

# Command prefixes to ignore
ignored_prefixes = mcp_server_,mcp-server-,helper-,worker-

# Command suffixes to ignore
ignored_suffixes = -helper,-worker,-daemon,-service,-server

# Shells to filter out (never show these)
ignored_shells = zsh,bash,sh,fish,ksh,tcsh,csh
```

**Reload after config changes:**
```bash
# Restart daemon
kill -15 $(cat ~/.cache/kitty-smart-tabs/daemon.pid)
source ~/.zshrc
```

---

## How It Works

### Architecture

**Three-tier CWD Detection** (in priority order):

1. **Shell hooks** (primary, instant)
   - Writes to `$XDG_RUNTIME_DIR/kitty-smart-tabs/tab_{ID}_cwd` on every `cd`
   - Atomic writes with owner-only permissions (0600)
   - Most accurate, requires shell hook installed

2. **Process CWD detection** (fallback, no hooks needed)
   - Reads `/proc/{PID}/cwd` symlink (Linux)
   - Parses `lsof -p {PID}` output (macOS/BSD)
   - Works even without shell hooks installed
   - Slightly slower but still accurate

3. **Kitty CWD** (last resort)
   - Uses CWD reported by `kitty @ ls`
   - May be stale after `cd` in existing tabs
   - Always works but least accurate

### Command Detection

- Background daemon polls every 2 seconds (8 seconds when idle)
- Detects foreground processes via `kitty @ ls`
- Filters out shells, build tools, helpers
- Prioritizes user-facing commands (editors, dev tools)
- Unwraps interpreters: `python script.py` → shows `[script]` not `[python]`

### Color Generation

- MD5 hash of full directory path
- Modulo palette size to get color index
- Consistent across sessions
- Root directory `/` handled specially (prevents empty string collision)
- 16-color palette reduces collision probability

### Smart Filtering

**Shows:**
- Editors: `nvim`, `vim`, `emacs`, `code`
- Dev tools: `git`, `docker`, `kubectl`, `claude`
- Scripts: Extracts script name from interpreter commands
- Priority commands (configurable)

**Filters out:**
- Shells: `zsh`, `bash`, `fish`
- Build tools: `npm`, `yarn`, `make`
- System utilities: `cat`, `grep`, `sed`
- Helpers: `mcp_server_*`, `*-daemon`, `*-worker`

### Performance

- **Adaptive polling**: 2s when active, increases to 8s when idle
- **Socket caching**: Kitty socket path cached, only re-scanned on failure
- **Early cache checking**: Skips computation for unchanged tabs
- **Minimal overhead**: ~1-2% CPU during polls, near-zero when idle
- **Graceful shutdown**: Responds to SIGTERM/SIGINT for clean daemon shutdown

### Security

- **Path validation**: No traversal, length limits, absolute paths only
- **Input sanitization**: Tab IDs validated, titles sanitized for control chars
- **Atomic operations**: Temp files written atomically via rename
- **Secure permissions**: Temp files mode 0600 (owner-only read/write)
- **Ownership verification**: Temp files must be owned by current user

---

## Troubleshooting

### Tabs not updating?

**Check daemon is running:**
```bash
ps aux | grep smart_tabs | grep daemon
```

**Restart daemon:**
```bash
# Stop (graceful shutdown via PID file)
kill -15 $(cat ~/.cache/kitty-smart-tabs/daemon.pid 2>/dev/null)

# Or if PID file missing (fallback)
pkill -f smart_tabs

# Start (reload shell to auto-start)
source ~/.zshrc
```

**Check daemon logs:**
```bash
tail -f ~/.config/kitty/smart_tabs_daemon.log
```

### Colors not showing?

**Verify remote control enabled:**
```bash
kitty @ ls
```
Should output JSON. If error, check `~/.config/kitty/kitty.conf`:
```conf
allow_remote_control yes
listen_on unix:/tmp/kitty
```

**Check socket path:**
```bash
ls -la /tmp/kitty-*
```
Should show socket file(s).

### CWD not tracking after cd?

**Verify shell hook installed:**
```bash
grep "Smart Tabs" ~/.zshrc    # or ~/.bashrc
```
Should show hook code.

**Check temp files being created:**
```bash
ls -la $XDG_RUNTIME_DIR/kitty-smart-tabs/ 2>/dev/null || ls -la ~/.cache/kitty-smart-tabs/
```
Should show `tab_*_cwd` files.

**Fallback without shell hooks:**
Even without hooks, process CWD detection should work:
```bash
# Test process detection
cd /tmp
nvim test.txt
# Tab should still show /tmp
```

### Debug mode

**Run daemon with debug logging:**
```bash
# Stop current daemon
kill -15 $(cat ~/.cache/kitty-smart-tabs/daemon.pid 2>/dev/null)

# Start with debug
cd ~/.config/kitty/kittens
python3 -m smart_tabs.daemon --debug &

# Watch logs
tail -f ~/.config/kitty/smart_tabs_daemon.log
```

**Debug temp file errors:**
```bash
tail -f ~/.config/kitty/smart_tabs_tempfile_debug.log
```

### Commands not showing?

**Check filters in config:**
```bash
grep -A5 "\[filters\]" ~/.config/kitty/smart_tabs.conf
```

Your command might be in `ignored_commands` or match an ignored prefix/suffix.

**Test manually:**
```bash
# Run update once with debug
cd ~/.config/kitty/kittens
python3 -m smart_tabs.kitten --debug
```

---

## FAQ

**Q: Does it work without shell hooks?**
A: Yes! Fallback to process CWD detection via `/proc` (Linux) or `lsof` (macOS). Less instant but still works.

**Q: Performance impact?**
A: Minimal. 2s poll when active, 8s when idle. Socket caching & early bailout reduce overhead. ~1-2% CPU during polls.

**Q: Can tabs in different directories have same color?**
A: Rare with 16-color palette. MD5 hash distribution minimizes collisions. Root `/` handled specially to avoid empty string collision.

**Q: Supports fish/other shells?**
A: Partially. Process CWD detection works for all shells. Shell hooks only available for zsh/bash currently.

**Q: Works over SSH?**
A: Yes, if Kitty is running locally. Remote shell detection works via process inspection.

**Q: Thread-safe? Multiple kitty instances?**
A: Yes. PID lock prevents multiple daemons. Temp files include tab IDs for isolation.

**Q: Why not use Kitty's built-in tab coloring?**
A: Kitty doesn't provide directory-based auto-coloring or command detection. This kitten adds that intelligence.

---

## Uninstall

### Automated
```bash
python3 uninstall.py
```

### Manual
1. Remove shell hook from `~/.zshrc`/`~/.bashrc` (look for "Smart Tabs" comment)
2. Stop daemon: `kill -15 $(cat ~/.cache/kitty-smart-tabs/daemon.pid)`
3. Remove files:
   ```bash
   rm -rf ~/.config/kitty/kittens/smart_tabs
   rm ~/.config/kitty/smart_tabs.conf
   rm -rf ~/.cache/kitty-smart-tabs
   rm -rf $XDG_RUNTIME_DIR/kitty-smart-tabs
   ```

---

## Migration from Old Setup

If you have an existing tab coloring setup:

```bash
python3 migrate.py
```

This will:
- Stop old background processes
- Migrate your color preferences
- Install new system
- Clean up old files

---

## Development

### Project Structure
```
kitty-smart-tabs/
├── smart_tabs/           # Python package
│   ├── kitten.py        # Kitten entry point
│   ├── daemon.py        # Background poller with adaptive intervals
│   ├── core.py          # Tab update logic, command parsing
│   ├── colors.py        # MD5-based color generation
│   ├── config.py        # INI config parser
│   └── tempfiles.py     # Secure temp file operations
├── shell_hooks/         # Shell integration
│   ├── zsh.sh          # Zsh hook for CWD tracking
│   └── bash.sh         # Bash hook for CWD tracking
├── tests/              # Comprehensive test suite
│   ├── test_colors.py
│   ├── test_core.py
│   ├── test_security.py
│   └── ...
├── install.py          # Automated installer
├── uninstall.py        # Automated uninstaller
└── README.md
```

### Run Tests
```bash
# All tests
python3 -m pytest tests/

# Specific test file
python3 -m pytest tests/test_colors.py -v

# With coverage
python3 -m pytest tests/ --cov=smart_tabs
```

**Test Coverage:** 162 tests covering:
- Color generation & collision handling
- Command parsing & filtering
- Security (path traversal, injection, permissions)
- Integration scenarios
- Regression tests
- Edge cases

### Code Quality
- Type hints throughout
- Comprehensive docstrings
- Security-first design
- Performance optimizations
- Error handling & graceful degradation

---

## Contributing

Contributions welcome! Please:

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Add tests for new functionality
4. Ensure all tests pass (`pytest tests/`)
5. Follow existing code style
6. Submit a pull request

**Areas for contribution:**
- Fish shell hook
- Windows support (PowerShell hook)
- Additional color palettes
- Performance improvements
- Documentation

---

## Known Limitations

- **Shell hooks only for zsh/bash** (fish/other shells use fallback process detection)
- **No Windows support** (process CWD detection uses Unix `/proc` or `lsof`)
- **Color collisions possible** with many tabs (birthday paradox, mitigated by 16-color palette)
- **2-second delay** for command detection (configurable, but lower = higher CPU)

---

## License

MIT License - see [LICENSE](LICENSE) file

---

## Credits

Created by Douglas Walseth

Built on top of Kitty's powerful [remote control](https://sw.kovidgoyal.net/kitty/remote-control/) and [kittens](https://sw.kovidgoyal.net/kitty/kittens_intro/) APIs.

---

## Support

- **Issues**: [GitHub Issues](https://github.com/douglasrw/kitty-smart-tabs/issues)
- **Discussions**: [GitHub Discussions](https://github.com/douglasrw/kitty-smart-tabs/discussions)
- **Documentation**: This README

---

⭐ If you find this useful, please star the repo!

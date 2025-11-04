# Smart Tabs shell integration for Bash
# Add this to your ~/.bashrc

if [[ "$TERM" == "xterm-kitty" ]]; then

    _smart_tabs_get_tab_id() {
        # Use KITTY_WINDOW_ID to reliably get current tab ID
        if [[ -z "$KITTY_WINDOW_ID" ]]; then
            return 1
        fi

        local tab_id=$(kitty @ ls 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    window_id = $KITTY_WINDOW_ID
    for os_win in data:
        for tab in os_win.get('tabs', []):
            for win in tab.get('windows', []):
                if win.get('id') == window_id:
                    print(tab.get('id', ''))
                    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null)

        if [[ -n "$tab_id" ]]; then
            echo "$tab_id"
            return 0
        else
            return 1
        fi
    }

    _smart_tabs_update() {
        # Get current tab ID dynamically
        local tab_id=$(_smart_tabs_get_tab_id)

        # Only proceed if we successfully got a tab ID
        if [[ -z "$tab_id" ]]; then
            return
        fi

        # Store current PWD for this tab
        echo "$PWD" > "/tmp/kitty_tab_${tab_id}_cwd" 2>/dev/null

        # The daemon will handle the actual update
    }

    # Update on directory change via PROMPT_COMMAND
    _smart_tabs_prompt_command() {
        local last_dir="$_smart_tabs_last_dir"
        if [[ "$PWD" != "$last_dir" ]]; then
            _smart_tabs_update
            _smart_tabs_last_dir="$PWD"
        fi
    }

    # Add to PROMPT_COMMAND
    if [[ -z "$PROMPT_COMMAND" ]]; then
        PROMPT_COMMAND="_smart_tabs_prompt_command"
    else
        PROMPT_COMMAND="${PROMPT_COMMAND};_smart_tabs_prompt_command"
    fi

    # Run once on shell start
    (sleep 0.1 && _smart_tabs_update) &

    # Start daemon if not already running
    if ! pgrep -f "smart_tabs.*daemon" >/dev/null 2>&1; then
        nohup python3 -m smart_tabs.daemon >/dev/null 2>&1 &
    fi
fi

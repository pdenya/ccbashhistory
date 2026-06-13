#!/usr/bin/env python3
import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import ccbashhistory

# POSIX-only modules. Guard them so importing this module never fails on Windows.
try:
    import termios
    import tty
except ImportError:  # pragma: no cover - Windows
    termios = None
    tty = None

# Windows-only console input.
try:
    import msvcrt
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None


def enable_windows_vt_mode():
    """Enable ANSI/VT escape sequence processing on the Windows console.

    No-op on POSIX. Falls back gracefully if the console mode cannot be set.
    """
    if os.name != 'nt':
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        STD_OUTPUT_HANDLE = -11
        handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(
                handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING
            )
    except Exception:  # pragma: no cover - best effort
        pass


def clear_screen():
    """Clear the terminal using ANSI escape sequences."""
    sys.stdout.write("\033[H\033[2J")
    sys.stdout.flush()


# ANSI color codes
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_CYAN = '\033[96m'


def find_claude_sessions(hours=24):
    """Find all Claude Code session files modified in the last N hours."""
    home = Path.home()
    claude_dir = home / ".claude" / "projects"

    if not claude_dir.exists():
        print(f"Error: Claude projects directory not found at {claude_dir}")
        sys.exit(1)

    cutoff_time = datetime.now() - timedelta(hours=hours)
    sessions = []

    # Iterate through all project directories
    for project_dir in claude_dir.iterdir():
        if not project_dir.is_dir():
            continue

        project_name = project_dir.name

        # Find all .jsonl files in this project
        for jsonl_file in project_dir.glob("*.jsonl"):
            mtime = datetime.fromtimestamp(jsonl_file.stat().st_mtime)

            if mtime >= cutoff_time:
                # Try to get session info from the first line
                session_info = get_session_info(jsonl_file)

                sessions.append({
                    'path': jsonl_file,
                    'project': project_name,
                    'modified': mtime,
                    'size': jsonl_file.stat().st_size,
                    'session_id': session_info.get('session_id'),
                    'branch': session_info.get('branch'),
                    'cwd': session_info.get('cwd'),
                    'title': session_info.get('title'),
                    'message_count': session_info.get('message_count', 0)
                })

    # Sort by modification time (newest first)
    sessions.sort(key=lambda x: x['modified'], reverse=True)
    return sessions


# Message `type` values that are config/state/system metadata and never carry a
# human prompt suitable for a session title.
META_MESSAGE_TYPES = frozenset({
    'permission-mode', 'file-history-snapshot', 'mode',
    'queue-operation', 'attachment', 'last-prompt',
    'ai-title', 'system', 'started', 'result',
})


def _extract_title_from_user_message(message):
    """Return a human prompt title from a user message, or None.

    Handles both content shapes:
      - STRING content: the prompt text itself.
      - LIST content: use the first block's `text` if it's a text block;
        skip the message entirely if the first block is a tool_result.
    """
    if not isinstance(message, dict):
        return None

    content = message.get('content')

    if isinstance(content, str):
        text = content.strip()
        return text or None

    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict) and first.get('type') == 'text':
            text = first.get('text', '')
            if isinstance(text, str):
                text = text.strip()
                return text or None
        # First block is a tool_result (or anything non-text): not a human prompt.
        return None

    return None


def get_session_info(jsonl_file):
    """Extract session info and count messages from a JSONL file."""
    info = {'message_count': 0}

    try:
        with open(jsonl_file, 'r') as f:
            # Read all lines to count messages and get metadata
            for i, line in enumerate(f):
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(data, dict):
                    continue

                msg_type = data.get('type')

                # Count user and assistant messages
                if msg_type in ('user', 'assistant'):
                    info['message_count'] += 1

                # Look for session metadata (only in first 50 lines)
                if i < 50:
                    if not info.get('session_id') and 'sessionId' in data:
                        info['session_id'] = data['sessionId']

                    if not info.get('branch') and 'gitBranch' in data:
                        info['branch'] = data['gitBranch']

                    if not info.get('cwd') and 'cwd' in data:
                        info['cwd'] = data['cwd']

                    # Look for a session title in the first human user prompt.
                    # Skip meta/system messages and tool-result-only user
                    # messages (handled by _extract_title_from_user_message).
                    if (not info.get('title')
                            and msg_type == 'user'
                            and msg_type not in META_MESSAGE_TYPES):
                        title = _extract_title_from_user_message(
                            data.get('message', {})
                        )
                        if title:
                            # Use first line of the prompt (truncate if too long)
                            info['title'] = title.split('\n')[0][:80]

    except (OSError, ValueError):
        # OSError: file went away / unreadable. ValueError covers stray
        # decoding issues. Never swallow KeyboardInterrupt/SystemExit.
        pass

    return info


def format_size(size_bytes):
    """Format bytes to human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f}TB"


def format_time_ago(dt):
    """Format datetime as time ago."""
    now = datetime.now()
    diff = now - dt
    seconds = diff.total_seconds()

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    elif seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    elif seconds < 604800:
        return f"{int(seconds // 86400)}d ago"
    else:
        return dt.strftime("%Y-%m-%d %H:%M")


def display_sessions(sessions, selected_idx=None, scroll_offset=0, visible_count=10, hours=24):
    """Display sessions in a scrollable window with optional highlighting."""
    header = f"Claude Code Sessions (Last {hours} Hours)"
    print(f"\n{Colors.BOLD}{Colors.CYAN}╔{'═' * 78}╗{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}║{Colors.RESET} {Colors.BOLD}{header}{Colors.RESET}{' ' * (75 - len(header))}{Colors.BOLD}{Colors.CYAN}║{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}╚{'═' * 78}╝{Colors.RESET}\n")

    total_sessions = len(sessions)
    end_offset = min(scroll_offset + visible_count, total_sessions)

    # Show scroll indicator at top if not at the beginning
    if scroll_offset > 0:
        print(f"{Colors.BRIGHT_BLACK}     ↑ {scroll_offset} more above ↑{Colors.RESET}")
        print()

    for i in range(scroll_offset, end_offset):
        session = sessions[i]

        # Extract project name from path (make it more readable)
        project = session['project']

        # Get working directory basename if available
        cwd_name = ""
        if session['cwd']:
            cwd_name = os.path.basename(session['cwd'])

        # Build the title/info line
        title = session.get('title', 'Untitled Session')

        # Build metadata parts
        metadata_parts = []
        if cwd_name:
            metadata_parts.append(f"{Colors.BLUE}{cwd_name}{Colors.RESET}")
        if session['branch']:
            metadata_parts.append(f"{Colors.MAGENTA}{session['branch']}{Colors.RESET}")

        metadata_parts.append(f"{Colors.BRIGHT_BLACK}{format_time_ago(session['modified'])}{Colors.RESET}")

        # Add message count and size together
        msg_count = session.get('message_count', 0)
        size_str = format_size(session['size'])
        metadata_parts.append(f"{Colors.BRIGHT_BLACK}{msg_count} msgs · {size_str}{Colors.RESET}")

        metadata = f"{Colors.BRIGHT_BLACK}│{Colors.RESET} ".join(metadata_parts)

        # Highlight selected item
        is_selected = selected_idx is not None and i == selected_idx
        prefix = "► " if is_selected else "  "
        num_color = Colors.BOLD + Colors.CYAN if is_selected else Colors.BOLD + Colors.YELLOW

        # Format the display - compact single line per session
        print(f"{prefix}{num_color}[{i+1:2d}]{Colors.RESET} {Colors.GREEN}{title}{Colors.RESET}")
        print(f"     {metadata}")
        print()

    # Show scroll indicator at bottom if more items below
    if end_offset < total_sessions:
        print(f"{Colors.BRIGHT_BLACK}     ↓ {total_sessions - end_offset} more below ↓{Colors.RESET}")
        print()

    print(f"{Colors.BRIGHT_BLACK}{'─' * 80}{Colors.RESET}")

    # Show position indicator
    if total_sessions > visible_count:
        print(f"{Colors.BRIGHT_BLACK}Showing {scroll_offset + 1}-{end_offset} of {total_sessions}{Colors.RESET}")


def _get_arrow_key_windows():
    """Read a single key press on Windows via msvcrt.

    Arrow keys arrive as a two-character sequence: a prefix ('\\x00' or
    '\\xe0') followed by 'H' (up) or 'P' (down).
    """
    ch = msvcrt.getwch()

    # Arrow / function keys come in as a prefix followed by a scan code.
    if ch in ('\x00', '\xe0'):
        ch2 = msvcrt.getwch()
        if ch2 == 'H':
            return 'UP'
        elif ch2 == 'P':
            return 'DOWN'
        return ''
    elif ch in ('\r', '\n'):
        return 'ENTER'
    elif ch in ('q', 'Q'):
        return 'QUIT'
    elif ch == '\x03':  # Ctrl+C
        return 'QUIT'

    return ch


def _get_arrow_key_posix():
    """Read a single key press on POSIX terminals via termios/tty."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)

        # Check for escape sequences (arrow keys)
        if ch == '\x1b':
            ch2 = sys.stdin.read(1)
            if ch2 == '[':
                ch3 = sys.stdin.read(1)
                if ch3 == 'A':
                    return 'UP'
                elif ch3 == 'B':
                    return 'DOWN'
        elif ch == '\r' or ch == '\n':
            return 'ENTER'
        elif ch == 'q' or ch == 'Q':
            return 'QUIT'
        elif ch == '\x03':  # Ctrl+C
            return 'QUIT'

        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def get_arrow_key():
    """Read a single key press, including arrow keys.

    Cross-platform: uses msvcrt on Windows and termios/tty on POSIX. Both
    branches return the same tokens ('UP', 'DOWN', 'ENTER', 'QUIT') or the
    raw character for any other key.
    """
    if os.name == 'nt' and msvcrt is not None:
        return _get_arrow_key_windows()
    return _get_arrow_key_posix()


def export_today(output_path=None, hours=24):
    """Export all bash commands from today's sessions to a file."""
    from ccbashhistory.extractor import extract_bash_commands

    sessions = find_claude_sessions(hours=hours)
    if not sessions:
        print(f"No Claude Code sessions found in the last {hours} hours.")
        sys.exit(0)

    today = datetime.now().date()
    today_sessions = [s for s in sessions if s['modified'].date() == today]

    if not today_sessions:
        print("No Claude Code sessions found from today.")
        sys.exit(0)

    if output_path is None:
        output_path = f"cc_bash_commands_{today.isoformat()}.txt"

    all_commands = []
    for session in today_sessions:
        commands = extract_bash_commands(str(session['path']))
        # Attach session metadata to each command (does NOT filter by command
        # timestamp; all commands from each of today's sessions are included).
        for cmd in commands:
            cmd['session_title'] = session.get('title', 'Untitled Session')
            cmd['session_cwd'] = session.get('cwd', '')
            cmd['session_branch'] = session.get('branch', '')
        all_commands.extend(commands)

    # Sort by timestamp
    all_commands.sort(key=lambda c: c.get('timestamp', ''))

    with open(output_path, 'w') as f:
        f.write(f"Claude Code Bash Commands - {today.isoformat()}\n")
        f.write(f"Sessions: {len(today_sessions)} | Commands: {len(all_commands)}\n")
        f.write("=" * 80 + "\n\n")

        for i, cmd in enumerate(all_commands, 1):
            f.write(f"[{i}] {cmd.get('timestamp', 'N/A')}\n")
            f.write(f"    Session: {cmd['session_title']}\n")
            if cmd['session_cwd']:
                f.write(f"    Dir: {cmd['session_cwd']}\n")
            if cmd['session_branch']:
                f.write(f"    Branch: {cmd['session_branch']}\n")
            if cmd['description'] != 'N/A':
                f.write(f"    Desc: {cmd['description']}\n")
            f.write(f"    $ {cmd['command']}\n")
            f.write("\n")

    print(f"Exported {len(all_commands)} commands from {len(today_sessions)} sessions to {output_path}")
    return output_path


def build_parser():
    """Build the argparse parser implementing the CLI spec."""
    parser = argparse.ArgumentParser(
        prog='ccbashhistory',
        description='Browse and export bash commands from Claude Code session history.',
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f"%(prog)s {ccbashhistory.__version__}",
    )
    parser.add_argument(
        '--hours',
        type=int,
        default=24,
        help='Lookback window (in hours) for finding sessions. Default: 24.',
    )
    parser.add_argument(
        '--export',
        nargs='?',
        const=None,
        default=argparse.SUPPRESS,
        metavar='PATH',
        help="Non-interactive: export today's bash commands to PATH "
             "(default filename cc_bash_commands_YYYY-MM-DD.txt).",
    )
    return parser


def run_interactive(sessions, hours):
    """Run the arrow-key session picker, returning the selected session."""
    selected_idx = 0
    visible_count = 10  # Number of sessions visible at once
    scroll_offset = 0

    while True:
        # Calculate scroll offset to keep selected item visible
        if selected_idx < scroll_offset:
            scroll_offset = selected_idx
        elif selected_idx >= scroll_offset + visible_count:
            scroll_offset = selected_idx - visible_count + 1

        # Clear screen and display sessions
        clear_screen()
        display_sessions(sessions, selected_idx, scroll_offset, visible_count, hours)

        print(f"\n{Colors.BRIGHT_BLACK}Use ↑/↓ arrows to navigate, Enter to select, q to quit{Colors.RESET}")

        # Get key press
        key = get_arrow_key()

        if key == 'UP':
            selected_idx = (selected_idx - 1) % len(sessions)
        elif key == 'DOWN':
            selected_idx = (selected_idx + 1) % len(sessions)
        elif key == 'ENTER':
            return sessions[selected_idx]
        elif key == 'QUIT':
            print(f"\n{Colors.BRIGHT_BLACK}Goodbye!{Colors.RESET}")
            sys.exit(0)
        elif key.isdigit():
            # Allow direct number entry
            num = int(key)
            if 1 <= num <= len(sessions):
                return sessions[num - 1]


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Enable ANSI/VT escape processing (no-op outside Windows).
    enable_windows_vt_mode()

    # Non-interactive export path. `--export` without a value -> args.export is
    # None (default filename); with a value -> the given path. Absent entirely
    # -> attribute is suppressed.
    if hasattr(args, 'export'):
        export_today(args.export, hours=args.hours)
        return

    # Find all recent sessions
    sessions = find_claude_sessions(hours=args.hours)

    if not sessions:
        print(f"No Claude Code sessions found in the last {args.hours} hours.")
        sys.exit(0)

    # Interactive selection with arrow keys
    selected = run_interactive(sessions, args.hours)

    # Clear screen one more time
    clear_screen()

    # Run the extraction script
    print(f"\n{Colors.BOLD}{Colors.CYAN}Analyzing session:{Colors.RESET} {Colors.GREEN}{selected.get('title', 'Untitled Session')}{Colors.RESET}")
    print(f"{Colors.BRIGHT_BLACK}{'─' * 80}{Colors.RESET}\n")

    # Import and run the extractor directly
    from ccbashhistory.extractor import extract_and_display_bash_commands

    extract_and_display_bash_commands(str(selected['path']))


if __name__ == '__main__':
    main()

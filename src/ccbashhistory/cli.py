#!/usr/bin/env python3
import json
import os
import sys
import tty
import termios
from datetime import datetime, timedelta
from pathlib import Path


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


def get_session_info(jsonl_file):
    """Extract session info and count messages from a JSONL file."""
    info = {'message_count': 0}

    try:
        with open(jsonl_file, 'r') as f:
            # Read all lines to count messages and get metadata
            for i, line in enumerate(f):
                try:
                    data = json.loads(line)

                    # Count user and assistant messages
                    if data.get('type') in ('user', 'assistant'):
                        info['message_count'] += 1

                    # Look for session metadata (only in first 50 lines)
                    if i < 50:
                        if not info.get('session_id') and 'sessionId' in data:
                            info['session_id'] = data['sessionId']

                        if not info.get('branch') and 'gitBranch' in data:
                            info['branch'] = data['gitBranch']

                        if not info.get('cwd') and 'cwd' in data:
                            info['cwd'] = data['cwd']

                        # Look for session title in user messages
                        if not info.get('title') and data.get('type') == 'user':
                            message = data.get('message', {})
                            if isinstance(message, dict):
                                content = message.get('content')
                                if isinstance(content, str) and content.strip():
                                    # Use first user message as title (truncate if too long)
                                    title = content.strip().split('\n')[0][:80]
                                    info['title'] = title

                except json.JSONDecodeError:
                    continue

    except Exception as e:
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

    if diff.seconds < 60:
        return "just now"
    elif diff.seconds < 3600:
        mins = diff.seconds // 60
        return f"{mins}m ago"
    elif diff.seconds < 86400:
        hours = diff.seconds // 3600
        return f"{hours}h ago"
    else:
        return dt.strftime("%Y-%m-%d %H:%M")


def display_sessions(sessions, selected_idx=None, scroll_offset=0, visible_count=10):
    """Display sessions in a scrollable window with optional highlighting."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}╔{'═' * 78}╗{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}║{Colors.RESET} {Colors.BOLD}Claude Code Sessions (Last 24 Hours){Colors.RESET}{' ' * 39}{Colors.BOLD}{Colors.CYAN}║{Colors.RESET}")
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


def get_arrow_key():
    """Read a single key press, including arrow keys."""
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


def main():
    # Find all recent sessions
    sessions = find_claude_sessions(hours=24)

    if not sessions:
        print("No Claude Code sessions found in the last 24 hours.")
        sys.exit(0)

    # Interactive selection with arrow keys
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
        os.system('clear' if os.name != 'nt' else 'cls')
        display_sessions(sessions, selected_idx, scroll_offset, visible_count)

        print(f"\n{Colors.BRIGHT_BLACK}Use ↑/↓ arrows to navigate, Enter to select, q to quit{Colors.RESET}")

        # Get key press
        key = get_arrow_key()

        if key == 'UP':
            selected_idx = (selected_idx - 1) % len(sessions)
        elif key == 'DOWN':
            selected_idx = (selected_idx + 1) % len(sessions)
        elif key == 'ENTER':
            selected = sessions[selected_idx]
            break
        elif key == 'QUIT':
            print(f"\n{Colors.BRIGHT_BLACK}Goodbye!{Colors.RESET}")
            sys.exit(0)
        elif key.isdigit():
            # Allow direct number entry
            num = int(key)
            if 1 <= num <= len(sessions):
                selected = sessions[num - 1]
                break

    # Clear screen one more time
    os.system('clear' if os.name != 'nt' else 'cls')

    # Run the extraction script
    print(f"\n{Colors.BOLD}{Colors.CYAN}Analyzing session:{Colors.RESET} {Colors.GREEN}{selected.get('title', 'Untitled Session')}{Colors.RESET}")
    print(f"{Colors.BRIGHT_BLACK}{'─' * 80}{Colors.RESET}\n")

    # Import and run the extractor directly
    from ccbashhistory.extractor import extract_and_display_bash_commands

    extract_and_display_bash_commands(str(selected['path']))


if __name__ == '__main__':
    main()

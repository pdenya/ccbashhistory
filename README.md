# ccbashhistory

[![PyPI version](https://img.shields.io/pypi/v/ccbashhistory.svg)](https://pypi.org/project/ccbashhistory/)
[![Downloads/month](https://img.shields.io/pypi/dm/ccbashhistory.svg)](https://pypistats.org/packages/ccbashhistory)
[![Total downloads](https://static.pepy.tech/badge/ccbashhistory)](https://pepy.tech/project/ccbashhistory)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

Extract and analyze bash commands from Claude Code session history.

## Usage

```bash
pipx run ccbashhistory
```

Run with no arguments to open the interactive session picker. It lists your recent Claude Code sessions (those active within the last 24 hours by default). Navigate with the arrow keys (or press the number shown next to a session for direct selection) and press Enter to view that session. Press `q` to quit. Selecting a session prints all of the bash commands Claude Code ran during it.

### Options

| Flag | Description |
| --- | --- |
| _(no flags)_ | Open the interactive arrow-key session picker for the lookback window. |
| `--hours N` | Set the lookback window, in hours, used to find recent sessions. Default: `24`. Increase it to widen the window or decrease it to narrow it. |
| `--export [PATH]` | Non-interactive mode. Export today's bash commands to a file instead of opening the picker. `PATH` is optional; when omitted the file is named `cc_bash_commands_YYYY-MM-DD.txt` in the current directory. |
| `-h`, `--help` | Show the help message and exit. |
| `--version` | Print the installed version and exit. |

Examples:

```bash
# Interactive picker over the last 48 hours
ccbashhistory --hours 48

# Export today's commands to the default file (cc_bash_commands_YYYY-MM-DD.txt)
ccbashhistory --export

# Export today's commands to a specific path
ccbashhistory --export ~/bash-history.txt
```

The interactive picker works across macOS, Linux, and Windows: it uses native key reading on each platform (`msvcrt` on Windows, termios/tty on macOS and Linux) so arrow keys, number selection, and `q` to quit behave the same everywhere. The `--export` mode is fully non-interactive and works identically on all three operating systems.

## Requirements

- **Python**: 3.8 or higher
- **Operating System**: macOS, Linux, or Windows
- **Claude Code**: Installed with conversation history in `~/.claude/projects/`

## Development

```bash
# Clone the repository
git clone https://github.com/pdenya/ccbashhistory.git
cd ccbashhistory

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode
pip install -e .

# Run without cache
pipx run --no-cache --spec . ccbashhistory
```

### Publishing to PyPI

```bash
# Install build and twine
pip install build twine

# Build the package
python3 -m build

# Upload to PyPI (requires API token)
twine upload dist/*
```

## Contributing

Contributions welcome! Please feel free to submit a Pull Request to [github.com/pdenya/ccbashhistory](https://github.com/pdenya/ccbashhistory).

## License

MIT License

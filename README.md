# ccbashhistory

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

Extract and analyze bash commands from Claude Code session history.

## Usage

```bash
pipx run ccbashhistory
```

Shows an interactive list of your recent Claude Code sessions. Use arrow keys to navigate and press Enter to select a session to analyze.
Prints all the bash commands run by claude code during this session

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

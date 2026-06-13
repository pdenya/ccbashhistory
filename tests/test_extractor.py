"""Tests for ccbashhistory.extractor.extract_bash_commands."""

from ccbashhistory.extractor import extract_bash_commands

from tests.conftest import (
    assistant_bash_line,
    assistant_non_bash_line,
    user_string_line,
    write_session,
)


def test_extracts_bash_command_fields(tmp_path):
    """A Bash tool_use yields command/description/timestamp/line."""
    path = tmp_path / "s.jsonl"
    write_session(
        path,
        [
            user_string_line("do a thing"),
            assistant_bash_line(
                "ls -la /tmp",
                "list tmp dir",
                timestamp="2026-06-13T18:00:00.000Z",
            ),
        ],
    )

    commands = extract_bash_commands(str(path))

    assert len(commands) == 1
    cmd = commands[0]
    assert cmd["command"] == "ls -la /tmp"
    assert cmd["description"] == "list tmp dir"
    assert cmd["timestamp"] == "2026-06-13T18:00:00.000Z"
    # The Bash line is the 2nd line in the file (1-indexed).
    assert cmd["line"] == 2


def test_returns_multiple_commands_in_order(tmp_path):
    """Multiple Bash blocks across lines are returned in file order."""
    path = tmp_path / "s.jsonl"
    write_session(
        path,
        [
            user_string_line("hi"),
            assistant_bash_line("echo one", "first"),
            assistant_bash_line("echo two", "second", tool_id="toolu_2"),
        ],
    )

    commands = extract_bash_commands(str(path))

    assert [c["command"] for c in commands] == ["echo one", "echo two"]


def test_ignores_non_bash_tool_use(tmp_path):
    """A non-Bash tool (e.g. Read) is never reported, even with a command key."""
    path = tmp_path / "s.jsonl"
    write_session(
        path,
        [
            user_string_line("hi"),
            assistant_non_bash_line(name="Read"),
            assistant_non_bash_line(name="Grep"),
        ],
    )

    commands = extract_bash_commands(str(path))

    assert commands == []


def test_tolerates_malformed_line_without_raising(tmp_path, malformed_line, capsys):
    """A malformed JSON line is skipped silently; real commands still parse."""
    path = tmp_path / "s.jsonl"
    write_session(
        path,
        [
            user_string_line("hi"),
            malformed_line,
            assistant_bash_line("true", "noop"),
        ],
    )

    # Must not raise.
    commands = extract_bash_commands(str(path))

    assert len(commands) == 1
    assert commands[0]["command"] == "true"

    # Must not print warnings to stdout or stderr.
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == ""


def test_mixed_session_extracts_only_bash(mixed_session):
    """The full mixed fixture: only the two Bash commands come through."""
    commands = extract_bash_commands(str(mixed_session))

    assert [c["command"] for c in commands] == ["git status", "pytest -q"]
    assert [c["description"] for c in commands] == [
        "show working tree status",
        "run the test suite",
    ]


def test_bash_without_command_key_is_skipped(tmp_path):
    """A Bash tool_use lacking input.command is ignored (no KeyError)."""
    line = assistant_bash_line("placeholder", "d")
    # Strip the command key from the Bash tool_use block.
    del line["message"]["content"][1]["input"]["command"]

    path = tmp_path / "s.jsonl"
    write_session(path, [user_string_line("hi"), line])

    assert extract_bash_commands(str(path)) == []

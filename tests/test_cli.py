"""Tests for ccbashhistory.cli helpers and flows."""

import os
from datetime import datetime, timedelta

import pytest

from ccbashhistory import cli

from tests.conftest import (
    assistant_bash_line,
    assistant_non_bash_line,
    meta_line,
    user_string_line,
    user_text_block_line,
    user_tool_result_line,
    write_session,
)


# --- format_size -----------------------------------------------------------


@pytest.mark.parametrize(
    "size_bytes, expected",
    [
        (0, "0.0B"),
        (1, "1.0B"),
        (512, "512.0B"),
        (1023, "1023.0B"),          # just below the KB boundary
        (1024, "1.0KB"),            # exactly the KB boundary
        (1536, "1.5KB"),
        (1024 * 1024 - 1, "1024.0KB"),  # just below the MB boundary
        (1024 * 1024, "1.0MB"),     # exactly the MB boundary
        (5 * 1024 * 1024, "5.0MB"),
    ],
)
def test_format_size_boundaries(size_bytes, expected):
    assert cli.format_size(size_bytes) == expected


# --- format_time_ago -------------------------------------------------------


def test_format_time_ago_just_now():
    assert cli.format_time_ago(datetime.now() - timedelta(seconds=5)) == "just now"


def test_format_time_ago_minutes():
    result = cli.format_time_ago(datetime.now() - timedelta(minutes=10))
    assert result == "10m ago"


def test_format_time_ago_hours_under_a_day():
    result = cli.format_time_ago(datetime.now() - timedelta(hours=3))
    assert result == "3h ago"


def test_format_time_ago_25_hours_reports_days_not_minutes():
    """Bug #2 regression: a 25h delta must report '1d ago', never minutes.

    The original code used ``diff.seconds`` (which wraps every 24h and drops
    the day component) instead of ``diff.total_seconds()``.  With ``.seconds``
    a 25h delta collapses to 1h, and other multi-day deltas surface as a small
    number of minutes.  Assert the correct day-based bucket and that the word
    'm ago' (minutes) never appears.
    """
    result = cli.format_time_ago(datetime.now() - timedelta(hours=25))
    assert result == "1d ago"
    assert "m ago" not in result


def test_format_time_ago_two_days_reports_days_not_minutes():
    """Bug #2 regression: a 2-day delta must report '2d ago', never minutes."""
    result = cli.format_time_ago(datetime.now() - timedelta(days=2))
    assert result == "2d ago"
    assert "m ago" not in result


def test_format_time_ago_old_dates_use_absolute_format():
    """Beyond a week, the absolute YYYY-MM-DD HH:MM format is used."""
    dt = datetime.now() - timedelta(days=30)
    result = cli.format_time_ago(dt)
    assert result == dt.strftime("%Y-%m-%d %H:%M")
    assert "ago" not in result


# --- get_session_info ------------------------------------------------------


def test_get_session_info_title_from_string_content(tmp_path):
    """Title comes from a STRING-content user prompt; metadata is captured."""
    path = tmp_path / "s.jsonl"
    write_session(
        path,
        [
            user_string_line(
                "Fix the broken deploy",
                session_id="sess-AAA",
                branch="feature/x",
                cwd="/Users/me/Code/widget",
            ),
            assistant_bash_line("git status", "status"),
        ],
    )

    info = cli.get_session_info(str(path))

    assert info["title"] == "Fix the broken deploy"
    assert info["session_id"] == "sess-AAA"
    assert info["branch"] == "feature/x"
    assert info["cwd"] == "/Users/me/Code/widget"
    # One user + one assistant line counted.
    assert info["message_count"] == 2


def test_get_session_info_title_from_list_of_blocks(tmp_path):
    """Bug #3 regression: title from a LIST-of-blocks user message (text block).

    When ``message.content`` is a list, the title must be read from the first
    text block's ``text`` field, not from the list object itself.
    """
    path = tmp_path / "s.jsonl"
    write_session(
        path,
        [
            user_text_block_line("Refactor the parser module"),
        ],
    )

    info = cli.get_session_info(str(path))

    assert info["title"] == "Refactor the parser module"


def test_get_session_info_skips_meta_first_messages(tmp_path):
    """Meta/system lines before the first prompt must not become the title."""
    path = tmp_path / "s.jsonl"
    write_session(
        path,
        [
            meta_line("file-history-snapshot"),
            meta_line("system"),
            user_string_line("The real first prompt"),
        ],
    )

    info = cli.get_session_info(str(path))

    assert info["title"] == "The real first prompt"


def test_get_session_info_skips_tool_result_user_for_title(tmp_path):
    """A user line whose first block is a tool_result is not a human prompt.

    The title must come from the later real text prompt, and the tool_result
    user line must still be counted as a message.
    """
    path = tmp_path / "s.jsonl"
    write_session(
        path,
        [
            user_tool_result_line(),
            user_string_line("Actual human prompt here"),
        ],
    )

    info = cli.get_session_info(str(path))

    assert info["title"] == "Actual human prompt here"
    assert info["message_count"] == 2


def test_get_session_info_truncates_to_first_line(tmp_path):
    """Only the first line of a multi-line prompt is used for the title."""
    path = tmp_path / "s.jsonl"
    write_session(
        path,
        [user_string_line("first line\nsecond line\nthird line")],
    )

    info = cli.get_session_info(str(path))

    assert info["title"] == "first line"


def test_get_session_info_tolerates_malformed_line(tmp_path, malformed_line):
    """A malformed JSON line in the session does not break info extraction."""
    path = tmp_path / "s.jsonl"
    write_session(
        path,
        [
            malformed_line,
            user_string_line("Prompt after a bad line"),
        ],
    )

    info = cli.get_session_info(str(path))

    assert info["title"] == "Prompt after a bad line"
    # Only the valid user line is counted.
    assert info["message_count"] == 1


def test_get_session_info_tolerates_valid_non_dict_json(tmp_path):
    """A line that is valid JSON but not an object must be skipped, not crash.

    ``json.loads`` succeeds on a bare number/string/array, so the JSONDecodeError
    guard doesn't catch it; without an ``isinstance(data, dict)`` check the
    subsequent ``data.get(...)`` would raise AttributeError and abort extraction.
    """
    path = tmp_path / "s.jsonl"
    write_session(
        path,
        [
            "42",                       # valid JSON, not a dict
            '"just a bare string"',     # valid JSON, not a dict
            "[1, 2, 3]",                # valid JSON, not a dict
            user_string_line("Prompt after non-dict lines"),
        ],
    )

    info = cli.get_session_info(str(path))

    assert info["title"] == "Prompt after non-dict lines"
    assert info["message_count"] == 1


# --- find_claude_sessions --------------------------------------------------


def test_find_claude_sessions_discovers_session(projects_dir):
    """A fresh .jsonl under the fake home is discovered with its metadata."""
    proj = projects_dir / "-Users-me-Code-proj"
    proj.mkdir()
    session_file = proj / "abc123.jsonl"
    write_session(
        session_file,
        [
            user_string_line(
                "Build the feature",
                session_id="sess-XYZ",
                branch="main",
                cwd="/Users/me/Code/proj",
            ),
            assistant_bash_line("make build", "build it"),
        ],
    )

    sessions = cli.find_claude_sessions(hours=24)

    assert len(sessions) == 1
    s = sessions[0]
    assert s["project"] == "-Users-me-Code-proj"
    assert s["path"] == session_file
    assert s["session_id"] == "sess-XYZ"
    assert s["branch"] == "main"
    assert s["cwd"] == "/Users/me/Code/proj"
    assert s["title"] == "Build the feature"
    assert s["message_count"] == 2


def test_find_claude_sessions_filters_by_hours_window(projects_dir):
    """An old (aged via os.utime) file is excluded by the --hours window."""
    proj = projects_dir / "-Users-me-Code-proj"
    proj.mkdir()

    recent = proj / "recent.jsonl"
    write_session(recent, [user_string_line("recent work")])

    old = proj / "old.jsonl"
    write_session(old, [user_string_line("ancient work")])
    # Age the old file to ~10 days ago via os.utime.
    ten_days_ago = (datetime.now() - timedelta(days=10)).timestamp()
    os.utime(old, (ten_days_ago, ten_days_ago))

    sessions = cli.find_claude_sessions(hours=24)

    paths = {s["path"] for s in sessions}
    assert recent in paths
    assert old not in paths
    assert len(sessions) == 1


# --- export_today ----------------------------------------------------------


def test_export_today_writes_header_and_commands(projects_dir, tmp_path):
    """export_today writes a header plus a '$ command' line for today's session."""
    proj = projects_dir / "-Users-me-Code-proj"
    proj.mkdir()
    session_file = proj / "today.jsonl"
    write_session(
        session_file,
        [
            user_string_line(
                "Today's session",
                session_id="sess-today",
                branch="main",
                cwd="/Users/me/Code/proj",
            ),
            assistant_bash_line("git log --oneline -5", "show recent commits"),
            assistant_non_bash_line(name="Read"),
        ],
    )

    out_path = tmp_path / "export.txt"
    returned = cli.export_today(output_path=str(out_path), hours=24)

    assert returned == str(out_path)
    assert out_path.exists()

    content = out_path.read_text()
    today = datetime.now().date().isoformat()
    # Header line includes today's date.
    assert f"Claude Code Bash Commands - {today}" in content
    assert "Sessions: 1 | Commands: 1" in content
    # The command line is written with a '$ ' prefix.
    assert "$ git log --oneline -5" in content
    assert "Desc: show recent commits" in content
    # Non-Bash tool output must not leak in.
    assert "NOT_A_BASH_COMMAND" not in content

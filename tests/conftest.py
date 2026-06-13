"""Shared fixtures for the ccbashhistory test suite.

Every fixture writes synthetic Claude Code JSONL session files into
``tmp_path``.  The line shapes mirror the real ``~/.claude/projects/*/*.jsonl``
format that was captured during recon:

* ``type == "user"`` lines carry the prompt inside ``message`` which is either
  a plain STRING (typed prompts) or a LIST of content blocks.
* Top-level keys ``sessionId``, ``gitBranch`` and ``cwd`` carry session
  metadata.
* ``type == "assistant"`` lines carry ``message.content`` as a LIST of blocks;
  a ``tool_use`` block named ``Bash`` has ``input.command`` and
  ``input.description``.

The helpers below build those shapes so individual tests can compose exactly
the session contents they need without re-deriving the JSON layout.
"""

import json

import pytest


# --- line builders (recon-accurate shapes) --------------------------------


def user_string_line(
    text,
    *,
    session_id="sess-1234",
    branch="main",
    cwd="/Users/me/Code/proj",
    timestamp="2026-06-13T17:51:36.761Z",
):
    """A ``type == "user"`` line whose ``message.content`` is a STRING prompt.

    This is the common typed-prompt shape and the source of the session title.
    ``message`` is a dict with a ``role`` and a STRING ``content`` (recon-
    accurate: typed prompts store the text directly as ``message.content``).
    """
    return {
        "parentUuid": None,
        "isSidechain": False,
        "type": "user",
        "message": {"role": "user", "content": text},  # STRING content
        "uuid": "u-string",
        "timestamp": timestamp,
        "userType": "external",
        "entrypoint": "cli",
        "cwd": cwd,
        "sessionId": session_id,
        "version": "2.1.177",
        "gitBranch": branch,
    }


def user_text_block_line(
    text,
    *,
    session_id="sess-1234",
    branch="main",
    cwd="/Users/me/Code/proj",
    timestamp="2026-06-13T17:51:36.761Z",
):
    """A ``type == "user"`` line whose ``message.content`` is a LIST-of-blocks.

    The first block is a ``text`` block.  This is the bug #3 regression shape:
    the title extractor must read ``content[0]["text"]`` instead of treating
    ``content`` as a string.
    """
    return {
        "parentUuid": None,
        "isSidechain": False,
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {"type": "text", "text": text},
            ],
        },
        "uuid": "u-textblock",
        "timestamp": timestamp,
        "userType": "external",
        "entrypoint": "cli",
        "cwd": cwd,
        "sessionId": session_id,
        "version": "2.1.177",
        "gitBranch": branch,
    }


def user_tool_result_line(
    *,
    session_id="sess-1234",
    branch="main",
    cwd="/Users/me/Code/proj",
    timestamp="2026-06-13T17:51:40.000Z",
):
    """A ``type == "user"`` line whose first content block is a ``tool_result``.

    This is NOT a human prompt and must be skipped when choosing a title, even
    though its ``type`` is ``"user"``.
    """
    return {
        "parentUuid": "u-string",
        "isSidechain": False,
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_abc",
                    "content": "command output here",
                },
            ],
        },
        "uuid": "u-toolresult",
        "timestamp": timestamp,
        "userType": "external",
        "entrypoint": "cli",
        "cwd": cwd,
        "sessionId": session_id,
        "version": "2.1.177",
        "gitBranch": branch,
    }


def meta_line(msg_type="file-history-snapshot", *, session_id="sess-1234"):
    """A meta/system/state line that carries no human prompt.

    These ``type`` values appear before / between conversation turns and must
    be skipped when extracting a title.  They are also NOT counted as messages.
    """
    return {
        "type": msg_type,
        "uuid": f"meta-{msg_type}",
        "timestamp": "2026-06-13T17:51:30.000Z",
        "sessionId": session_id,
    }


def assistant_bash_line(
    command,
    description="run a command",
    *,
    timestamp="2026-06-13T17:52:00.000Z",
    session_id="sess-1234",
    branch="main",
    cwd="/Users/me/Code/proj",
    tool_id="toolu_01EbE7QPWMSpSdCHurrrHd88",
):
    """A ``type == "assistant"`` line containing a Bash ``tool_use`` block."""
    return {
        "parentUuid": "u-string",
        "isSidechain": False,
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Let me run that."},
                {
                    "type": "tool_use",
                    "id": tool_id,
                    "name": "Bash",
                    "input": {
                        "command": command,
                        "description": description,
                    },
                },
            ],
        },
        "requestId": "req-1",
        "uuid": "a-bash",
        "timestamp": timestamp,
        "userType": "external",
        "entrypoint": "cli",
        "cwd": cwd,
        "sessionId": session_id,
        "version": "2.1.177",
        "gitBranch": branch,
    }


def assistant_non_bash_line(
    *,
    name="Read",
    timestamp="2026-06-13T17:52:05.000Z",
    session_id="sess-1234",
):
    """A ``type == "assistant"`` line with a NON-Bash ``tool_use`` block.

    The extractor must ignore this (e.g. a Read tool with a ``command`` key
    that should never leak into the bash command list).
    """
    return {
        "parentUuid": "u-string",
        "isSidechain": False,
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_read1",
                    "name": name,
                    # Deliberately include a 'command' key to prove the
                    # extractor keys off the tool NAME, not the input shape.
                    "input": {"command": "NOT_A_BASH_COMMAND", "file_path": "/x"},
                },
            ],
        },
        "uuid": "a-nonbash",
        "timestamp": timestamp,
        "sessionId": session_id,
    }


def write_session(path, lines):
    """Serialize ``lines`` to ``path`` as JSONL.

    Each element of ``lines`` may be a dict (json.dumps'd) or a raw string
    (written verbatim, used to inject a malformed line).
    """
    with open(path, "w") as f:
        for line in lines:
            if isinstance(line, str):
                f.write(line)
                if not line.endswith("\n"):
                    f.write("\n")
            else:
                f.write(json.dumps(line) + "\n")
    return path


# --- pytest fixtures -------------------------------------------------------


@pytest.fixture
def malformed_line():
    """A deliberately malformed JSON line that must be skipped, not raised on."""
    return '{"type": "assistant", "message": {"content": [ THIS IS NOT JSON }'


@pytest.fixture
def mixed_session(tmp_path, malformed_line):
    """A single JSONL session exercising every interesting line shape.

    Order matters: a meta line comes first (must be skipped for the title), a
    malformed line is interleaved (must be tolerated), then the real content.
    """
    path = tmp_path / "mixed.jsonl"
    write_session(
        path,
        [
            meta_line("file-history-snapshot"),
            meta_line("system"),
            malformed_line,
            user_string_line("Help me fix the failing CI on this branch"),
            assistant_bash_line("git status", "show working tree status"),
            assistant_non_bash_line(name="Read"),
            user_tool_result_line(),
            assistant_bash_line(
                "pytest -q",
                "run the test suite",
                timestamp="2026-06-13T17:53:00.000Z",
                tool_id="toolu_second",
            ),
        ],
    )
    return path


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Monkeypatch ``Path.home()`` to a hermetic temp dir.

    Returns the temp home path.  A ``.claude/projects`` tree can then be built
    under it without ever touching the real ``~/.claude``.
    """
    import pathlib

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(pathlib.Path, "home", lambda: home)
    return home


@pytest.fixture
def projects_dir(fake_home):
    """An empty ``<home>/.claude/projects`` directory under the fake home."""
    pdir = fake_home / ".claude" / "projects"
    pdir.mkdir(parents=True)
    return pdir

#!/usr/bin/env python3
import json
import sys

def extract_bash_commands(jsonl_file):
    commands = []

    with open(jsonl_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            try:
                data = json.loads(line)

                # Check if this is an assistant message with tool calls
                if data.get('type') == 'assistant' and 'message' in data:
                    message = data['message']
                    if 'content' in message and isinstance(message['content'], list):
                        for block in message['content']:
                            if isinstance(block, dict) and block.get('type') == 'tool_use':
                                if block.get('name') == 'Bash':
                                    params = block.get('input', {})
                                    if 'command' in params:
                                        commands.append({
                                            'line': line_num,
                                            'command': params['command'],
                                            'description': params.get('description', 'N/A'),
                                            'timestamp': data.get('timestamp', 'N/A')
                                        })
            except json.JSONDecodeError:
                print(f"Warning: Could not parse line {line_num}", file=sys.stderr)
                continue

    return commands

def extract_and_display_bash_commands(jsonl_file):
    """Extract and display bash commands from a JSONL file."""
    commands = extract_bash_commands(jsonl_file)

    print(f"Found {len(commands)} bash commands:\n")
    print("=" * 80)

    for i, cmd_info in enumerate(commands, 1):
        print(f"\n[Command {i}] (Line {cmd_info['line']}) - {cmd_info['timestamp']}")
        print(f"Description: {cmd_info['description']}")
        print(f"Command:\n{cmd_info['command']}")
        print("-" * 80)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python extract_bash_commands.py <jsonl_file>")
        sys.exit(1)

    extract_and_display_bash_commands(sys.argv[1])

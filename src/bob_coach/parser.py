"""Parser for Bob session markdown exports."""

import re
from datetime import datetime
from pathlib import Path
from typing import Literal

from .models import (
    EnvironmentDetails,
    ModeTransition,
    Session,
    ToolUse,
    Turn,
)


# Regex patterns for parsing
TURN_DELIMITER = re.compile(r'^---$')
USER_MARKER = re.compile(r'^\*\*User:\*\*$')
ASSISTANT_MARKER = re.compile(r'^\*\*Assistant:\*\*$')
ERROR_PATTERN = re.compile(r'\[ERROR\]')

# Environment details patterns
COST_PATTERN = re.compile(r'# Current Cost\s*\n\$(\d+\.\d+)')
TIMESTAMP_PATTERN = re.compile(r'Current time in ISO 8601 UTC format: (.+)')
MODE_SLUG_PATTERN = re.compile(r'<slug>(\w+)</slug>')
MODE_NAME_PATTERN = re.compile(r'<name>(.+?)</name>')
WORKSPACE_PATTERN = re.compile(r'# Current Workspace Directory \((.+?)\)')

# Tool use patterns (non-greedy to avoid over-capturing)
TOOL_PATTERN = re.compile(r'<(\w+)>\s*\n(.*?)\n</\1>', re.DOTALL)
PARAM_PATTERN = re.compile(r'<(\w+)>(.*?)</\1>', re.DOTALL)

# Slash command pattern
SLASH_CMD_PATTERN = re.compile(r'/(\w+)')

# File editing tool names
FILE_EDIT_TOOLS = {'write_to_file', 'apply_diff', 'insert_content'}


def parse_session(filepath: Path) -> Session:
    """Parse a Bob session markdown export into a Session object.
    
    Args:
        filepath: Path to the session markdown file
        
    Returns:
        Session object with all parsed turns and metadata
        
    Raises:
        FileNotFoundError: If filepath doesn't exist
    """
    if not filepath.exists():
        raise FileNotFoundError(f"Session file not found: {filepath}")
    
    content = filepath.read_text(encoding='utf-8')
    lines = content.split('\n')
    
    turns = _parse_turns(lines)
    _calculate_cost_deltas(turns)
    mode_transitions = _extract_mode_transitions(turns)
    
    # Extract workspace from first turn with environment details
    workspace = None
    for turn in turns:
        if turn.environment and turn.environment.workspace_dir:
            workspace = turn.environment.workspace_dir
            break
    
    # Count file edits and extract slash commands
    file_edits = sum(
        1 for turn in turns
        for tool in turn.tool_uses
        if tool.name in FILE_EDIT_TOOLS
    )
    
    # Extract slash commands from user turns (only at start of line or after whitespace)
    slash_commands = []
    for turn in turns:
        if turn.speaker == "user":
            # Only match /command at start of line or after whitespace
            for line in turn.content.split('\n'):
                line = line.strip()
                if line.startswith('/'):
                    # Extract the command (word after /)
                    match = re.match(r'/(\w+)', line)
                    if match:
                        slash_commands.append(match.group(1))
    
    # Total cost is the maximum cumulative cost seen across all turns
    total_cost = max((turn.cumulative_cost for turn in turns), default=0.0)
    
    return Session(
        turns=turns,
        total_cost=total_cost,
        mode_transitions=mode_transitions,
        workspace=workspace,
        file_edits=file_edits,
        slash_commands=slash_commands,
    )


def _parse_turns(lines: list[str]) -> list[Turn]:
    """Parse lines into Turn objects using state machine.
    
    Args:
        lines: All lines from the markdown file
        
    Returns:
        List of parsed Turn objects
    """
    turns: list[Turn] = []
    current_turn: Turn | None = None
    content_lines: list[str] = []
    environment_lines: list[str] = []
    in_environment = False
    turn_index = 0
    
    for line in lines:
        # Check for turn delimiter
        if TURN_DELIMITER.match(line):
            if current_turn is not None:
                # Finalize current turn
                current_turn.content = '\n'.join(content_lines).strip()
                # Only extract tools from assistant turns
                if current_turn.speaker == "assistant":
                    current_turn.tool_uses = _extract_tools(current_turn.content, turn_index)
                current_turn.has_error = bool(ERROR_PATTERN.search(current_turn.content))
                turns.append(current_turn)
                turn_index += 1
            
            current_turn = None
            content_lines = []
            environment_lines = []
            in_environment = False
            continue
        
        # Check for speaker markers
        if USER_MARKER.match(line):
            current_turn = Turn(
                index=turn_index,
                speaker="user",
                content="",
                mode=None,
                cost_delta=0.0,
                cumulative_cost=0.0,
                timestamp=None,
            )
            continue
        
        if ASSISTANT_MARKER.match(line):
            current_turn = Turn(
                index=turn_index,
                speaker="assistant",
                content="",
                mode=None,
                cost_delta=0.0,
                cumulative_cost=0.0,
                timestamp=None,
            )
            continue
        
        # Handle environment_details blocks
        if line.strip() == '<environment_details>':
            in_environment = True
            environment_lines = []
            continue
        
        if line.strip() == '</environment_details>':
            in_environment = False
            if current_turn is not None:
                env_content = '\n'.join(environment_lines)
                current_turn.environment = _parse_environment(env_content)
                if current_turn.environment:
                    current_turn.mode = current_turn.environment.mode_slug
                    current_turn.timestamp = current_turn.environment.timestamp
                    current_turn.cumulative_cost = current_turn.environment.cost
            environment_lines = []
            continue
        
        # Accumulate lines
        if in_environment:
            environment_lines.append(line)
        elif current_turn is not None:
            content_lines.append(line)
    
    # Finalize last turn if exists
    if current_turn is not None:
        current_turn.content = '\n'.join(content_lines).strip()
        # Only extract tools from assistant turns
        if current_turn.speaker == "assistant":
            current_turn.tool_uses = _extract_tools(current_turn.content, turn_index)
        current_turn.has_error = bool(ERROR_PATTERN.search(current_turn.content))
        turns.append(current_turn)
    
    return turns


def _parse_environment(content: str) -> EnvironmentDetails | None:
    """Parse environment_details block content.
    
    Args:
        content: Raw content from environment_details block
        
    Returns:
        EnvironmentDetails object or None if parsing fails
    """
    try:
        env = EnvironmentDetails()
        
        # Parse cost
        cost_match = COST_PATTERN.search(content)
        if cost_match:
            env.cost = float(cost_match.group(1))
        
        # Parse timestamp
        timestamp_match = TIMESTAMP_PATTERN.search(content)
        if timestamp_match:
            try:
                env.timestamp = datetime.fromisoformat(timestamp_match.group(1).replace('Z', '+00:00'))
            except ValueError:
                pass  # Invalid timestamp, leave as None
        
        # Parse mode
        mode_slug_match = MODE_SLUG_PATTERN.search(content)
        if mode_slug_match:
            env.mode_slug = mode_slug_match.group(1)
        
        mode_name_match = MODE_NAME_PATTERN.search(content)
        if mode_name_match:
            env.mode_name = mode_name_match.group(1)
        
        # Parse workspace
        workspace_match = WORKSPACE_PATTERN.search(content)
        if workspace_match:
            env.workspace_dir = workspace_match.group(1)
        
        # Parse visible files - section between "# VSCode Visible Files" and next "# " header
        visible_files_match = re.search(r'# VSCode Visible Files\s*\n(.*?)(?=\n# |\Z)', content, re.DOTALL)
        if visible_files_match:
            files_text = visible_files_match.group(1).strip()
            if files_text and files_text != '':
                # Split by newlines and filter out empty lines
                env.visible_files = [f.strip() for f in files_text.split('\n') if f.strip()]
        
        # Parse open tabs - section between "# VSCode Open Tabs" and next "# " header
        open_tabs_match = re.search(r'# VSCode Open Tabs\s*\n(.*?)(?=\n# |\Z)', content, re.DOTALL)
        if open_tabs_match:
            tabs_text = open_tabs_match.group(1).strip()
            if tabs_text and tabs_text != '':
                # Split by newlines, filter empty and lines starting with #
                env.open_tabs = [t.strip() for t in tabs_text.split('\n')
                                if t.strip() and not t.strip().startswith('#')]
        
        return env
    except Exception:
        # If parsing fails, return None rather than crashing
        return None


def _extract_tools(content: str, turn_index: int, in_code_block: bool = False) -> list[ToolUse]:
    """Extract tool uses from turn content.
    
    Only extracts actual Bob tools (not user XML like <task>).
    
    Args:
        content: Turn content to extract tools from
        turn_index: Index of the turn (for ToolUse objects)
        in_code_block: Whether we're inside a code block (skip extraction if True)
        
    Returns:
        List of ToolUse objects
    """
    if in_code_block:
        return []
    
    # Known Bob tool names (from Bob's tool list)
    KNOWN_TOOLS = {
        'read_file', 'write_to_file', 'apply_diff', 'insert_content',
        'execute_command', 'list_files', 'search_files', 'list_code_definition_names',
        'ask_followup_question', 'attempt_completion', 'switch_mode', 'update_todo_list',
        'codebase_search', 'obtain_git_diff', 'submit_review_findings'
    }
    
    tools: list[ToolUse] = []
    
    # Find all tool XML blocks
    for match in TOOL_PATTERN.finditer(content):
        tool_name = match.group(1)
        
        # Only extract known Bob tools, skip user XML like <task>, <environment_details>
        if tool_name not in KNOWN_TOOLS:
            continue
        
        tool_content = match.group(2)
        
        # Extract parameters
        parameters: dict[str, str] = {}
        for param_match in PARAM_PATTERN.finditer(tool_content):
            param_name = param_match.group(1)
            param_value = param_match.group(2).strip()
            parameters[param_name] = param_value
        
        tools.append(ToolUse(
            name=tool_name,
            parameters=parameters,
            turn_index=turn_index,
        ))
    
    return tools


def _calculate_cost_deltas(turns: list[Turn]) -> None:
    """Calculate cost deltas for each turn (modifies turns in place).
    
    Args:
        turns: List of Turn objects to update
    """
    previous_cost = 0.0
    
    for turn in turns:
        turn.cost_delta = turn.cumulative_cost - previous_cost
        previous_cost = turn.cumulative_cost


def _extract_mode_transitions(turns: list[Turn]) -> list[ModeTransition]:
    """Extract mode transitions from turn sequence.
    
    Args:
        turns: List of Turn objects
        
    Returns:
        List of ModeTransition objects
    """
    transitions: list[ModeTransition] = []
    previous_mode: str | None = None
    
    for turn in turns:
        if turn.mode is not None and turn.mode != previous_mode:
            mode_name = turn.environment.mode_name if turn.environment else turn.mode
            transitions.append(ModeTransition(
                from_mode=previous_mode,
                to_mode=turn.mode,
                to_mode_name=mode_name or turn.mode,
                turn_index=turn.index,
            ))
            previous_mode = turn.mode
    
    return transitions

# Made with Bob

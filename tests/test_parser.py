"""Tests for Bob session parser."""

import pytest
from pathlib import Path
from datetime import datetime

from bob_coach.parser import parse_session
from bob_coach.models import Session, Turn


@pytest.fixture
def fixture_dir():
    """Return path to fixtures directory."""
    return Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def sample_01(fixture_dir):
    """Return path to sample-session-01.md."""
    return fixture_dir / "sample-session-01.md"


@pytest.fixture
def sample_02(fixture_dir):
    """Return path to sample-session-02.md."""
    return fixture_dir / "sample-session-02.md"


def test_parse_simple_session(sample_01):
    """Test parsing simple 4-turn session."""
    session = parse_session(sample_01)
    
    assert len(session.turns) == 4  # User, Assistant, User ([ERROR]), Assistant (completion)
    assert session.turns[0].speaker == "user"
    assert session.turns[1].speaker == "assistant"
    assert session.turns[2].speaker == "user"  # [ERROR] reminder is a user turn
    assert session.turns[3].speaker == "assistant"
    assert session.total_cost == 0.03


def test_cost_tracking(sample_01):
    """Test cost delta and cumulative cost calculation."""
    session = parse_session(sample_01)
    
    # Turn 0: user turn, cost $0.00
    assert session.turns[0].cost_delta == 0.0
    assert session.turns[0].cumulative_cost == 0.0
    
    # Turn 1: assistant turn, no environment so cost stays 0
    assert session.turns[1].cost_delta == 0.0
    assert session.turns[1].cumulative_cost == 0.0
    
    # Turn 2: user turn with [ERROR], cost $0.03
    assert session.turns[2].cost_delta == 0.03
    assert session.turns[2].cumulative_cost == 0.03
    
    # Turn 3: assistant turn, no environment so cumulative_cost resets to 0
    # (cost_delta is calculated as current - previous = 0 - 0.03 = -0.03)
    assert session.turns[3].cumulative_cost == 0.0
    
    # Session total cost should be the maximum seen (0.03)
    assert session.total_cost == 0.03


def test_error_detection(sample_01):
    """Test [ERROR] message detection."""
    session = parse_session(sample_01)
    
    # Turn 0: user turn, no error
    assert session.turns[0].has_error is False
    
    # Turn 1: assistant turn, no error
    assert session.turns[1].has_error is False
    
    # Turn 2: user turn with [ERROR] reminder
    assert session.turns[2].has_error is True
    
    # Turn 3: assistant turn, no error
    assert session.turns[3].has_error is False


def test_tool_extraction(sample_01):
    """Test tool use extraction from assistant turns."""
    session = parse_session(sample_01)
    
    # Turn 0: user turn, no tools
    assert len(session.turns[0].tool_uses) == 0
    
    # Turn 3: assistant turn with attempt_completion
    assert len(session.turns[3].tool_uses) == 1
    tool = session.turns[3].tool_uses[0]
    assert tool.name == "attempt_completion"
    assert "result" in tool.parameters
    assert "README.md" in tool.parameters["result"]


def test_environment_parsing(sample_01):
    """Test environment_details block parsing."""
    session = parse_session(sample_01)
    
    # Turn 0: has environment details
    env = session.turns[0].environment
    assert env is not None
    assert env.timestamp is not None
    assert isinstance(env.timestamp, datetime)
    assert env.mode_slug == "plan"
    assert env.mode_name == "📝 Plan"
    assert env.workspace_dir is not None
    assert "Desktop" in env.workspace_dir


def test_complex_session(sample_02):
    """Test parsing complex multi-turn session."""
    session = parse_session(sample_02)
    
    # Should have many turns (planning session)
    assert len(session.turns) > 10
    
    # Should have mode transitions
    assert len(session.mode_transitions) > 0
    
    # Total cost should be the maximum cumulative cost seen
    assert session.total_cost >= 0.0
    if session.turns:
        max_cost = max(turn.cumulative_cost for turn in session.turns)
        assert session.total_cost == max_cost


def test_mode_transitions(sample_02):
    """Test mode transition extraction."""
    session = parse_session(sample_02)
    
    # Should have at least one mode transition
    assert len(session.mode_transitions) > 0
    
    # First transition should have from_mode == None
    first_transition = session.mode_transitions[0]
    assert first_transition.from_mode is None
    assert first_transition.to_mode == "plan"
    
    # Transition turn_index should be valid
    assert 0 <= first_transition.turn_index < len(session.turns)


def test_slash_command_extraction(sample_02):
    """Test slash command extraction from user turns."""
    session = parse_session(sample_02)
    
    # sample-02 is a planning session, may not have /review
    # But should extract any slash commands present
    # Check that slash_commands is a list (may be empty)
    assert isinstance(session.slash_commands, list)
    
    # All extracted commands should be strings
    for cmd in session.slash_commands:
        assert isinstance(cmd, str)
        assert cmd.isalnum() or '_' in cmd


def test_file_edit_counting(sample_02):
    """Test file edit counting (write_to_file, apply_diff, insert_content)."""
    session = parse_session(sample_02)
    
    # Count should match actual write_to_file/apply_diff/insert_content uses
    actual_edits = sum(
        1 for turn in session.turns
        for tool in turn.tool_uses
        if tool.name in {'write_to_file', 'apply_diff', 'insert_content'}
    )
    assert session.file_edits == actual_edits
    
    # sample-02 is a planning session, may or may not have file edits
    # Just verify the count is consistent
    assert session.file_edits >= 0


def test_empty_environment_fields(sample_01):
    """Test handling of empty environment fields."""
    session = parse_session(sample_01)
    
    # Turn 0 has empty visible files and open tabs
    env = session.turns[0].environment
    assert env is not None
    assert isinstance(env.visible_files, list)
    assert isinstance(env.open_tabs, list)
    # May be empty or have content, just check they're lists


def test_multi_line_tool_parameters(sample_01):
    """Test extraction of multi-line tool parameters."""
    session = parse_session(sample_01)
    
    # Turn 3: attempt_completion with multi-line result
    tool = session.turns[3].tool_uses[0]
    assert tool.name == "attempt_completion"
    result = tool.parameters["result"]
    
    # Should contain newlines (multi-line content)
    assert "\n" in result
    
    # Should contain expected content
    assert "README.md" in result
    assert "requirements.txt" in result


def test_workspace_extraction(sample_01):
    """Test workspace directory extraction."""
    session = parse_session(sample_01)
    
    # Workspace should be extracted from first turn with environment
    assert session.workspace is not None
    assert "Desktop" in session.workspace

# Made with Bob

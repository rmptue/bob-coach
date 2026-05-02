"""Tests for anti-pattern detectors."""

import pytest
from pathlib import Path
from datetime import datetime

from bob_coach.parser import parse_session
from bob_coach.detectors import (
    detect_missing_plan_file,
    detect_cost_drift,
    detect_missing_review,
    detect_tool_errors,
    detect_conversation_loops,
    detect_mode_thrashing,
    detect_plan_mode_violations,
    detect_repeated_file_reads,
)
from bob_coach.models import (
    Session, Turn, ToolUse, ModeTransition, 
    EnvironmentDetails, AntiPattern
)


@pytest.fixture
def fixture_dir():
    """Path to fixtures directory."""
    return Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def sample_01_session(fixture_dir):
    """Simple 2-turn session fixture."""
    return parse_session(fixture_dir / "sample-session-01.md")


@pytest.fixture
def sample_02_session(fixture_dir):
    """Complex planning session fixture."""
    return parse_session(fixture_dir / "sample-session-02.md")


# Test 1: Missing Plan File - No detection in Plan mode
def test_missing_plan_file_not_detected_in_plan_mode(sample_02_session):
    """Plan mode sessions should not be flagged for missing plan files."""
    findings = detect_missing_plan_file(sample_02_session)
    assert len(findings) == 0


# Test 2: Missing Plan File - Detection in Code mode
def test_missing_plan_file_detected_in_code_mode():
    """Code mode sessions with >3 turns and no plan files should be flagged."""
    session = Session(
        turns=[
            Turn(
                index=i,
                speaker="assistant",
                content="",
                mode="code",
                cost_delta=0.01,
                cumulative_cost=0.01 * (i + 1),
                timestamp=None,
                environment=EnvironmentDetails(
                    mode_slug="code",
                    visible_files=["src/main.py"],
                    open_tabs=["src/main.py"]
                )
            )
            for i in range(5)  # 5 Code turns, >3 threshold
        ]
    )
    
    findings = detect_missing_plan_file(session)
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert "PLAN.md" in findings[0].recommendation
    assert "5 Code mode turns" in findings[0].evidence[0]


# Test 3: Cost Drift - Single turn detection
def test_cost_drift_single_turn_detected(sample_02_session):
    """Turns with cost >$0.30 should be flagged."""
    findings = detect_cost_drift(sample_02_session)
    
    # sample-02 has a $0.31 turn
    single_turn_findings = [f for f in findings if "Single Turn" in f.name]
    assert len(single_turn_findings) >= 1
    assert any("$0.3" in ev for f in single_turn_findings for ev in f.evidence)


# Test 4: Cost Drift - Negative delta handling
def test_cost_drift_negative_delta_ignored():
    """Negative cost deltas should not be flagged as drift."""
    session = Session(
        turns=[
            Turn(index=0, speaker="assistant", content="", mode="plan",
                 cost_delta=0.5, cumulative_cost=0.5, timestamp=None),
            Turn(index=1, speaker="assistant", content="", mode="plan",
                 cost_delta=-0.3, cumulative_cost=0.2, timestamp=None),  # Negative
        ],
        total_cost=0.2
    )
    
    findings = detect_cost_drift(session)
    # Turn 0 ($0.50) should be flagged, but turn 1 (negative) should not
    single_turn_findings = [f for f in findings if "Single Turn" in f.name]
    assert len(single_turn_findings) == 1
    # Verify only turn 0 is in evidence, not turn 1
    assert "Turn 0" in single_turn_findings[0].evidence[0]
    assert "Turn 1" not in str(single_turn_findings[0].evidence)


# Test 5: Missing Review - Detection
def test_missing_review_detected():
    """Sessions with >5 file edits and no /review should be flagged."""
    session = Session(
        turns=[
            Turn(
                index=i,
                speaker="assistant",
                content="",
                mode="code",
                cost_delta=0.01,
                cumulative_cost=0.01 * (i + 1),
                timestamp=None,
                tool_uses=[ToolUse(name="write_to_file", parameters={"path": f"file{i}.py"}, turn_index=i)]
            )
            for i in range(6)  # 6 file edits
        ],
        slash_commands=[],  # No /review
        file_edits=6
    )
    
    findings = detect_missing_review(session)
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert "6 file edits" in findings[0].evidence[0]
    assert "No /review command" in findings[0].evidence[1]


# Test 6: Missing Review - Not detected when /review present
def test_missing_review_not_detected_with_review():
    """Sessions with /review should not be flagged."""
    session = Session(
        turns=[
            Turn(
                index=i,
                speaker="assistant",
                content="",
                mode="code",
                cost_delta=0.01,
                cumulative_cost=0.01 * (i + 1),
                timestamp=None,
                tool_uses=[ToolUse(name="write_to_file", parameters={}, turn_index=i)]
            )
            for i in range(6)
        ],
        slash_commands=["review"],  # Has /review
        file_edits=6
    )
    
    findings = detect_missing_review(session)
    assert len(findings) == 0


# Test 7: Tool Errors - Detection
def test_tool_errors_detected():
    """[ERROR] after tool use should be flagged."""
    # Create session with tool use followed by error
    session = Session(
        turns=[
            Turn(index=0, speaker="assistant", content="", mode="plan",
                 cost_delta=0.01, cumulative_cost=0.01, timestamp=None,
                 tool_uses=[ToolUse(name="read_file", parameters={}, turn_index=0)],
                 has_error=False),
            Turn(index=1, speaker="user", content="[ERROR] File not found", mode="plan",
                 cost_delta=0.0, cumulative_cost=0.01, timestamp=None,
                 has_error=True),
        ]
    )
    
    findings = detect_tool_errors(session)
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert "Turn 1" in findings[0].evidence[0]


# Test 8: Tool Errors - Not detected without errors
def test_tool_errors_not_detected_clean_session():
    """Sessions without errors should not be flagged."""
    session = Session(
        turns=[
            Turn(index=0, speaker="assistant", content="", mode="plan",
                 cost_delta=0.01, cumulative_cost=0.01, timestamp=None,
                 tool_uses=[ToolUse(name="read_file", parameters={}, turn_index=0)],
                 has_error=False),
            Turn(index=1, speaker="user", content="", mode="plan",
                 cost_delta=0.0, cumulative_cost=0.01, timestamp=None,
                 has_error=False),
        ]
    )
    
    findings = detect_tool_errors(session)
    assert len(findings) == 0


# Test 9: Conversation Loops - Detection
def test_conversation_loops_detected():
    """>3 consecutive ask_followup_question should be flagged."""
    session = Session(
        turns=[
            Turn(
                index=i,
                speaker="assistant",
                content="",
                mode="plan",
                cost_delta=0.01,
                cumulative_cost=0.01 * (i + 1),
                timestamp=None,
                tool_uses=[ToolUse(name="ask_followup_question", parameters={}, turn_index=i)]
            )
            for i in range(5)  # 5 consecutive asks
        ]
    )
    
    findings = detect_conversation_loops(session)
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert "5 consecutive" in findings[0].evidence[0]


# Test 10: Conversation Loops - Not detected with breaks
def test_conversation_loops_not_detected_with_breaks():
    """Asks with breaks should not be flagged."""
    session = Session(
        turns=[
            Turn(index=0, speaker="assistant", content="", mode="plan",
                 cost_delta=0.01, cumulative_cost=0.01, timestamp=None,
                 tool_uses=[ToolUse(name="ask_followup_question", parameters={}, turn_index=0)]),
            Turn(index=1, speaker="assistant", content="", mode="plan",
                 cost_delta=0.01, cumulative_cost=0.02, timestamp=None,
                 tool_uses=[ToolUse(name="read_file", parameters={}, turn_index=1)]),  # Break
            Turn(index=2, speaker="assistant", content="", mode="plan",
                 cost_delta=0.01, cumulative_cost=0.03, timestamp=None,
                 tool_uses=[ToolUse(name="ask_followup_question", parameters={}, turn_index=2)]),
        ]
    )
    
    findings = detect_conversation_loops(session)
    assert len(findings) == 0


# Test 11: Mode Thrashing - Detection
def test_mode_thrashing_detected():
    """>4 mode switches in 10 turns should be flagged."""
    turns = []
    modes = ["plan", "code", "plan", "ask", "code", "plan", "code"]  # 6 switches
    
    for i, mode in enumerate(modes):
        turns.append(Turn(
            index=i,
            speaker="assistant",
            content="",
            mode=mode,
            cost_delta=0.01,
            cumulative_cost=0.01 * (i + 1),
            timestamp=None
        ))
    
    transitions = [
        ModeTransition(from_mode=None, to_mode="plan", to_mode_name="Plan", turn_index=0)
    ]
    for i in range(1, len(modes)):
        if modes[i] != modes[i-1]:
            transitions.append(ModeTransition(
                from_mode=modes[i-1],
                to_mode=modes[i],
                to_mode_name=modes[i].title(),
                turn_index=i
            ))
    
    session = Session(turns=turns, mode_transitions=transitions)
    
    findings = detect_mode_thrashing(session)
    assert len(findings) == 1
    assert findings[0].severity == "low"


# Test 12: Mode Thrashing - Not detected in stable session
def test_mode_thrashing_not_detected_stable_session(sample_02_session):
    """Plan-only sessions should not be flagged."""
    findings = detect_mode_thrashing(sample_02_session)
    assert len(findings) == 0


# Test 13: Plan Mode Violation - High confidence (both signals)
def test_plan_mode_violation_high_confidence():
    """Tool use + error in Plan mode should be flagged with high confidence."""
    session = Session(
        turns=[
            Turn(
                index=0,
                speaker="assistant",
                content="",
                mode="plan",
                cost_delta=0.01,
                cumulative_cost=0.01,
                timestamp=None,
                tool_uses=[ToolUse(
                    name="write_to_file",
                    parameters={"path": "src/main.py"},
                    turn_index=0
                )],
                has_error=True
            )
        ]
    )
    
    findings = detect_plan_mode_violations(session)
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert "write_to_file('src/main.py')" in findings[0].evidence[0]
    assert "[ERROR]" in findings[0].evidence[0]


# Test 14: Plan Mode Violation - Tool only (possible)
def test_plan_mode_violation_tool_only():
    """Tool use without error should be flagged as possible violation."""
    session = Session(
        turns=[
            Turn(
                index=0,
                speaker="assistant",
                content="",
                mode="plan",
                cost_delta=0.01,
                cumulative_cost=0.01,
                timestamp=None,
                tool_uses=[ToolUse(
                    name="write_to_file",
                    parameters={"path": "src/main.py"},
                    turn_index=0
                )],
                has_error=False
            )
        ]
    )
    
    findings = detect_plan_mode_violations(session)
    assert len(findings) == 1
    assert "Possible violation" in findings[0].evidence[0]


# Test 15: Plan Mode Violation - Error only (possible)
def test_plan_mode_violation_error_only():
    """Error without path extraction should be flagged as possible violation."""
    session = Session(
        turns=[
            Turn(
                index=0,
                speaker="assistant",
                content="",
                mode="plan",
                cost_delta=0.01,
                cumulative_cost=0.01,
                timestamp=None,
                tool_uses=[ToolUse(
                    name="write_to_file",
                    parameters={},  # No path
                    turn_index=0
                )],
                has_error=True
            )
        ]
    )
    
    findings = detect_plan_mode_violations(session)
    assert len(findings) == 1
    assert "Possible violation" in findings[0].evidence[0]
    assert "path not extracted" in findings[0].evidence[0]


# Test 16: All detectors return list
def test_all_detectors_return_list(sample_01_session):
    """All detectors must return list[AntiPattern], not None."""
    detectors = [
        detect_missing_plan_file,
        detect_cost_drift,
        detect_missing_review,
        detect_tool_errors,
        detect_conversation_loops,
        detect_mode_thrashing,
        detect_plan_mode_violations,
    ]
    
    for detector in detectors:
        result = detector(sample_01_session)
        assert isinstance(result, list)
        assert all(isinstance(ap, AntiPattern) for ap in result)


# Test 17: Missing Plan File - Threshold boundary
def test_missing_plan_file_threshold():
    """Exactly 3 Code turns should NOT flag, 4 should flag."""
    # 3 turns - should not flag
    session = Session(
        turns=[
            Turn(
                index=i,
                speaker="assistant",
                content="",
                mode="code",
                cost_delta=0.01,
                cumulative_cost=0.01 * (i + 1),
                timestamp=None,
                environment=EnvironmentDetails(
                    mode_slug="code",
                    visible_files=["src/main.py"],
                    open_tabs=[]
                )
            )
            for i in range(3)
        ]
    )
    
    findings = detect_missing_plan_file(session)
    assert len(findings) == 0
    
    # 4 turns - should flag
    session.turns.append(Turn(
        index=3,
        speaker="assistant",
        content="",
        mode="code",
        cost_delta=0.01,
        cumulative_cost=0.04,
        timestamp=None,
        environment=EnvironmentDetails(
            mode_slug="code",
            visible_files=["src/main.py"],
            open_tabs=[]
        )
    ))
    
    findings = detect_missing_plan_file(session)
    assert len(findings) == 1


# Test 18: Cost Drift - Negative delta note in evidence
def test_cost_drift_with_negative_deltas_note():
    """Session with negative deltas should note this in evidence."""
    session = Session(
        turns=[
            Turn(index=0, speaker="assistant", content="", mode="plan",
                 cost_delta=0.5, cumulative_cost=0.5, timestamp=None),
            Turn(index=1, speaker="assistant", content="", mode="plan",
                 cost_delta=-0.3, cumulative_cost=0.2, timestamp=None),  # Negative
            Turn(index=2, speaker="assistant", content="", mode="plan",
                 cost_delta=1.0, cumulative_cost=1.2, timestamp=None),
        ],
        total_cost=1.7  # Over threshold
    )
    
    findings = detect_cost_drift(session)
    
    # Should have session-level finding
    session_findings = [f for f in findings if "Session" in f.name]
    assert len(session_findings) >= 1
    
    # Should mention negative deltas in evidence
    assert any(
        "negative" in ev.lower() 
        for f in session_findings 
        for ev in f.evidence
    )


# Made with Bob

# Test 19: Repeated File Reads - Positive case (4 reads)
def test_repeated_file_reads_detected():
    """Files read 4 times should be flagged."""
    session = Session(
        turns=[
            Turn(
                index=i,
                speaker="assistant",
                content="",
                mode="code",
                cost_delta=0.01,
                cumulative_cost=0.01 * (i + 1),
                timestamp=None,
                tool_uses=[
                    ToolUse(
                        name="read_file",
                        parameters={"args": "<file>\n<path>src/main.py</path>\n</file>"},
                        turn_index=i
                    )
                ]
            )
            for i in range(4)
        ]
    )
    
    findings = detect_repeated_file_reads(session)
    assert len(findings) == 1
    assert findings[0].name == "Repeated File Reads"
    assert findings[0].severity == "medium"
    assert "src/main.py: 4 reads" in findings[0].evidence[0]


# Test 20: Repeated File Reads - Negative case (2 reads)
def test_repeated_file_reads_not_detected():
    """Files read only 2 times should NOT be flagged."""
    session = Session(
        turns=[
            Turn(
                index=i,
                speaker="assistant",
                content="",
                mode="code",
                cost_delta=0.01,
                cumulative_cost=0.01 * (i + 1),
                timestamp=None,
                tool_uses=[
                    ToolUse(
                        name="read_file",
                        parameters={"args": "<file>\n<path>src/utils.py</path>\n</file>"},
                        turn_index=i
                    )
                ]
            )
            for i in range(2)
        ]
    )
    
    findings = detect_repeated_file_reads(session)
    assert len(findings) == 0


# Test 21: Repeated File Reads - Edge case (exactly 3 reads)
def test_repeated_file_reads_threshold():
    """Files read exactly 3 times should be flagged (boundary test)."""
    session = Session(
        turns=[
            Turn(
                index=i,
                speaker="assistant",
                content="",
                mode="code",
                cost_delta=0.01,
                cumulative_cost=0.01 * (i + 1),
                timestamp=None,
                tool_uses=[
                    ToolUse(
                        name="read_file",
                        parameters={"args": "<file>\n<path>config.json</path>\n</file>"},
                        turn_index=i
                    )
                ]
            )
            for i in range(3)
        ]
    )
    
    findings = detect_repeated_file_reads(session)
    assert len(findings) == 1
    assert "config.json: 3 reads" in findings[0].evidence[0]


# Made with Bob
"""Tests for metrics calculation and report generation."""

import json
from pathlib import Path

import pytest

from bob_coach.models import Session, Turn, AntiPattern, ToolUse
from bob_coach.metrics import (
    calculate_plan_to_code_ratio,
    calculate_bobcoin_efficiency,
    calculate_conversation_count,
    calculate_slash_command_usage,
    calculate_error_rate,
    calculate_all_metrics,
    calculate_overall_score,
)
from bob_coach.report import render_terminal_report, render_json_report
from bob_coach.parser import parse_session


@pytest.fixture
def sample_01_session():
    """Simple 2-turn session fixture."""
    return parse_session(Path("fixtures/sample-session-01.md"))


@pytest.fixture
def sample_02_session():
    """Complex planning session fixture."""
    return parse_session(Path("fixtures/sample-session-02.md"))


# Metric Tests

def test_plan_to_code_ratio_all_plan():
    """Test plan-to-code ratio when all turns are in plan mode."""
    session = Session(turns=[
        Turn(index=0, speaker="user", content="", mode="plan", 
             cost_delta=0.0, cumulative_cost=0.0, timestamp=None),
        Turn(index=1, speaker="assistant", content="", mode="plan",
             cost_delta=0.01, cumulative_cost=0.01, timestamp=None),
    ])
    ratio = calculate_plan_to_code_ratio(session)
    assert ratio == 100.0


def test_plan_to_code_ratio_no_plan():
    """Test plan-to-code ratio when no planning occurs."""
    session = Session(turns=[
        Turn(index=0, speaker="user", content="", mode="code",
             cost_delta=0.0, cumulative_cost=0.0, timestamp=None),
        Turn(index=1, speaker="assistant", content="", mode="code",
             cost_delta=0.01, cumulative_cost=0.01, timestamp=None),
    ])
    ratio = calculate_plan_to_code_ratio(session)
    assert ratio == 0.0


def test_plan_to_code_ratio_mixed():
    """Test plan-to-code ratio with mixed modes."""
    session = Session(turns=[
        Turn(index=0, speaker="user", content="", mode="plan",
             cost_delta=0.0, cumulative_cost=0.0, timestamp=None),
        Turn(index=1, speaker="assistant", content="", mode="code",
             cost_delta=0.01, cumulative_cost=0.01, timestamp=None),
        Turn(index=2, speaker="user", content="", mode="code",
             cost_delta=0.01, cumulative_cost=0.02, timestamp=None),
    ])
    ratio = calculate_plan_to_code_ratio(session)
    # 1 plan turn / 2 code turns = 50%
    assert ratio == 50.0


def test_bobcoin_efficiency_zero_cost():
    """Test bobcoin efficiency with zero cost."""
    session = Session(total_cost=0.0, file_edits=5)
    efficiency = calculate_bobcoin_efficiency(session)
    assert efficiency == 0.0


def test_bobcoin_efficiency_calculation():
    """Test bobcoin efficiency calculation with deliverables."""
    session = Session(
        total_cost=0.30,
        file_edits=10,
        turns=[
            Turn(index=0, speaker="assistant", content="",
                 mode="code", cost_delta=0.15, cumulative_cost=0.15,
                 timestamp=None,
                 tool_uses=[ToolUse(name="read_file", parameters={}, turn_index=0)]),
            Turn(index=1, speaker="user", content="", mode="code",
                 cost_delta=0.15, cumulative_cost=0.30, timestamp=None,
                 has_error=False),
        ]
    )
    efficiency = calculate_bobcoin_efficiency(session)
    # (10 file_edits + 1 successful_tool) / 0.30 * 0.10 = 3.7
    assert efficiency == 3.7


def test_bobcoin_efficiency_excludes_error_tools():
    """Test that tools followed by errors are not counted."""
    session = Session(
        total_cost=0.10,
        file_edits=0,
        turns=[
            Turn(index=0, speaker="assistant", content="",
                 mode="code", cost_delta=0.05, cumulative_cost=0.05,
                 timestamp=None,
                 tool_uses=[ToolUse(name="write_to_file", parameters={}, turn_index=0)]),
            Turn(index=1, speaker="user", content="", mode="code",
                 cost_delta=0.05, cumulative_cost=0.10, timestamp=None,
                 has_error=True),  # Error after tool use
        ]
    )
    efficiency = calculate_bobcoin_efficiency(session)
    # 0 file_edits + 0 successful_tools (error occurred) = 0
    assert efficiency == 0.0


def test_conversation_count_no_users():
    """Test conversation count with no user turns."""
    session = Session(turns=[
        Turn(index=0, speaker="assistant", content="", mode="plan",
             cost_delta=0.0, cumulative_cost=0.0, timestamp=None),
    ])
    count = calculate_conversation_count(session)
    assert count == 0


def test_conversation_count_multiple_users():
    """Test conversation count with multiple user turns."""
    session = Session(turns=[
        Turn(index=0, speaker="user", content="", mode="plan",
             cost_delta=0.0, cumulative_cost=0.0, timestamp=None),
        Turn(index=1, speaker="assistant", content="", mode="plan",
             cost_delta=0.01, cumulative_cost=0.01, timestamp=None),
        Turn(index=2, speaker="user", content="", mode="plan",
             cost_delta=0.01, cumulative_cost=0.02, timestamp=None),
    ])
    count = calculate_conversation_count(session)
    assert count == 2


def test_slash_command_usage_zero_users():
    """Test slash command usage with no user turns."""
    session = Session(slash_commands=["review"], turns=[])
    usage = calculate_slash_command_usage(session)
    assert usage == 0.0


def test_slash_command_usage_calculation():
    """Test slash command usage percentage calculation."""
    session = Session(
        slash_commands=["review", "plan"],
        turns=[
            Turn(index=0, speaker="user", content="", mode="plan",
                 cost_delta=0.0, cumulative_cost=0.0, timestamp=None),
            Turn(index=1, speaker="assistant", content="", mode="plan",
                 cost_delta=0.01, cumulative_cost=0.01, timestamp=None),
            Turn(index=2, speaker="user", content="", mode="plan",
                 cost_delta=0.01, cumulative_cost=0.02, timestamp=None),
        ]
    )
    usage = calculate_slash_command_usage(session)
    # 2 slash commands / 2 user turns = 100%
    assert usage == 100.0


def test_error_rate_empty_session():
    """Test error rate with empty session."""
    session = Session(turns=[])
    rate = calculate_error_rate(session)
    assert rate == 0.0


def test_error_rate_calculation():
    """Test error rate percentage calculation."""
    session = Session(turns=[
        Turn(index=0, speaker="user", content="", mode="plan",
             cost_delta=0.0, cumulative_cost=0.0, timestamp=None,
             has_error=False),
        Turn(index=1, speaker="assistant", content="", mode="plan",
             cost_delta=0.01, cumulative_cost=0.01, timestamp=None,
             has_error=True),
        Turn(index=2, speaker="user", content="", mode="plan",
             cost_delta=0.01, cumulative_cost=0.02, timestamp=None,
             has_error=False),
        Turn(index=3, speaker="assistant", content="", mode="plan",
             cost_delta=0.01, cumulative_cost=0.03, timestamp=None,
             has_error=False),
    ])
    rate = calculate_error_rate(session)
    # 1 error / 4 turns = 25%
    assert rate == 25.0


def test_overall_score_calculation():
    """Test overall score with metrics and anti-patterns."""
    # 4/5 metrics passing = 80% base
    # 1 critical anti-pattern = -10
    # 1 medium anti-pattern = -3
    # Expected: 80 - 10 - 3 = 67
    
    anti_patterns = [
        AntiPattern(
            name="Test Critical",
            severity="critical",
            description="Test",
            evidence=["Turn 1"],
            recommendation="Fix it"
        ),
        AntiPattern(
            name="Test Medium",
            severity="medium",
            description="Test",
            evidence=["Turn 2"],
            recommendation="Fix it"
        ),
    ]
    
    score = calculate_overall_score(4, 5, anti_patterns)
    assert score == 67


def test_overall_score_bounds():
    """Test that overall score is bounded between 0 and 100."""
    # Test lower bound
    anti_patterns = [
        AntiPattern(
            name=f"Test {i}",
            severity="critical",
            description="Test",
            evidence=[],
            recommendation="Fix"
        )
        for i in range(20)  # 20 critical = -200 points
    ]
    score = calculate_overall_score(0, 5, anti_patterns)
    assert score == 0
    
    # Test upper bound (already at 100)
    score = calculate_overall_score(5, 5, [])
    assert score == 100


def test_calculate_all_metrics_structure():
    """Test that calculate_all_metrics returns correct structure."""
    session = Session(
        turns=[
            Turn(index=0, speaker="user", content="", mode="plan",
                 cost_delta=0.0, cumulative_cost=0.0, timestamp=None),
        ],
        total_cost=0.01,
        slash_commands=[]
    )
    
    metrics = calculate_all_metrics(session)
    
    # Check all expected metrics are present
    expected_metrics = [
        "plan_to_code_ratio",
        "bobcoin_efficiency",
        "conversation_count",
        "slash_command_usage",
        "error_rate"
    ]
    
    for metric_name in expected_metrics:
        assert metric_name in metrics
        metric = metrics[metric_name]
        assert "value" in metric
        assert "target" in metric
        assert "unit" in metric
        assert "pass" in metric
        assert isinstance(metric["pass"], bool)


# Report Tests

def test_terminal_report_contains_sections(sample_01_session):
    """Test that terminal report contains all expected sections."""
    metrics = calculate_all_metrics(sample_01_session)
    findings = []
    
    report = render_terminal_report(
        sample_01_session, metrics, findings, "sample-01.md"
    )
    
    assert "Bob Coach Report" in report
    assert "Metrics Summary" in report
    assert "Plan-to-Code Ratio" in report
    assert "Bobcoin Efficiency" in report
    assert "Conversation Count" in report
    assert "Slash Command Usage" in report
    assert "Error Rate" in report
    assert "Session Score" in report


def test_terminal_report_empty_anti_patterns(sample_01_session):
    """Test terminal report with no anti-patterns."""
    metrics = calculate_all_metrics(sample_01_session)
    findings = []
    
    report = render_terminal_report(
        sample_01_session, metrics, findings, "sample-01.md"
    )
    
    assert "No Anti-Patterns Detected" in report
    assert "✅" in report


def test_terminal_report_with_anti_patterns(sample_01_session):
    """Test terminal report with anti-patterns."""
    metrics = calculate_all_metrics(sample_01_session)
    findings = [
        AntiPattern(
            name="Test Pattern",
            severity="high",
            description="Test description",
            evidence=["Turn 1: Test evidence"],
            recommendation="Test recommendation"
        )
    ]
    
    report = render_terminal_report(
        sample_01_session, metrics, findings, "sample-01.md"
    )
    
    assert "Anti-Patterns Detected (1)" in report
    assert "Test Pattern" in report
    assert "Test evidence" in report
    assert "Test recommendation" in report


def test_json_report_validates_schema(sample_01_session):
    """Test that JSON report conforms to schema v1.0.0."""
    metrics = calculate_all_metrics(sample_01_session)
    findings = []
    
    report_json = render_json_report(
        sample_01_session, metrics, findings, "sample-01.md"
    )
    
    data = json.loads(report_json)
    
    # Validate top-level structure
    assert "version" in data
    assert data["version"] == "1.0.0"
    assert "session_metadata" in data
    assert "metrics" in data
    assert "anti_patterns" in data
    assert "summary" in data
    
    # Validate session_metadata
    metadata = data["session_metadata"]
    assert "filename" in metadata
    assert "total_cost" in metadata
    assert "turn_count" in metadata
    assert "user_turns" in metadata
    assert "assistant_turns" in metadata
    
    # Validate metrics structure
    for metric_name in ["plan_to_code_ratio", "bobcoin_efficiency", 
                        "conversation_count", "slash_command_usage", "error_rate"]:
        assert metric_name in data["metrics"]
        metric = data["metrics"][metric_name]
        assert "value" in metric
        assert "target" in metric
        assert "unit" in metric
        assert "pass" in metric
        assert isinstance(metric["pass"], bool)
    
    # Validate summary
    summary = data["summary"]
    assert "overall_score" in summary
    assert "passing_metrics_count" in summary
    assert "total_metrics_count" in summary
    assert "anti_pattern_count_by_severity" in summary
    assert "total_anti_patterns" in summary


def test_json_report_with_anti_patterns(sample_01_session):
    """Test JSON report includes anti-patterns correctly."""
    metrics = calculate_all_metrics(sample_01_session)
    findings = [
        AntiPattern(
            name="Test Pattern",
            severity="medium",
            description="Test description",
            evidence=["Evidence 1", "Evidence 2"],
            recommendation="Test recommendation"
        )
    ]
    
    report_json = render_json_report(
        sample_01_session, metrics, findings, "sample-01.md"
    )
    
    data = json.loads(report_json)
    
    assert len(data["anti_patterns"]) == 1
    pattern = data["anti_patterns"][0]
    assert pattern["name"] == "Test Pattern"
    assert pattern["severity"] == "medium"
    assert pattern["description"] == "Test description"
    assert len(pattern["evidence"]) == 2
    assert pattern["recommendation"] == "Test recommendation"
    
    # Check summary counts
    assert data["summary"]["total_anti_patterns"] == 1
    assert data["summary"]["anti_pattern_count_by_severity"]["medium"] == 1


# Made with Bob
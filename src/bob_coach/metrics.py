"""Metric calculation functions for Bob Coach reports."""

from bob_coach.models import Session, AntiPattern


def calculate_plan_to_code_ratio(session: Session) -> float:
    """Calculate percentage of plan mode turns vs code mode turns.
    
    Formula: (plan_turns / code_turns) * 100
    Target: >20% (healthy planning discipline)
    
    Edge cases:
    - code_turns == 0: Return 100.0 (all planning, no code)
    - plan_turns == 0 and code_turns > 0: Return 0.0 (no planning)
    - Both zero: Return 0.0 (no mode data)
    
    Args:
        session: Parsed session object
        
    Returns:
        Percentage ratio rounded to 1 decimal place
    """
    plan_turns = sum(1 for t in session.turns if t.mode == "plan")
    code_turns = sum(1 for t in session.turns if t.mode == "code")
    
    if code_turns == 0:
        return 100.0 if plan_turns > 0 else 0.0
    
    return round((plan_turns / code_turns) * 100, 1)


def calculate_bobcoin_efficiency(session: Session) -> float:
    """Calculate deliverables per $0.10 spent.
    
    Formula: (file_edits + successful_tool_uses) / total_cost * 0.10
    Target: >5 deliverables per $0.10
    
    Deliverables:
    - File edits: write_to_file, apply_diff, insert_content
    - Successful tool uses: All tools NOT followed by [ERROR] in next turn
    
    Edge cases:
    - total_cost == 0.0: Return 0.0 (avoid division by zero)
    - No deliverables: Return 0.0
    
    Args:
        session: Parsed session object
        
    Returns:
        Efficiency metric rounded to 1 decimal place
    """
    if session.total_cost == 0.0:
        return 0.0
    
    # Count successful tool uses (not followed by error)
    successful_tools = 0
    for i, turn in enumerate(session.turns):
        if turn.speaker == "assistant" and turn.tool_uses:
            # Check if next turn has error
            next_turn_has_error = (
                i + 1 < len(session.turns) and 
                session.turns[i + 1].has_error
            )
            if not next_turn_has_error:
                successful_tools += len(turn.tool_uses)
    
    deliverables = session.file_edits + successful_tools
    
    # Scale to per $0.10
    efficiency = (deliverables / session.total_cost) * 0.10
    return round(efficiency, 1)


def calculate_conversation_count(session: Session) -> int:
    """Count user turns in session.
    
    Formula: user_turns_count
    Target: <15 for focused sessions
    
    Edge cases:
    - No user turns: Return 0
    - Assistant-only session: Return 0
    
    Args:
        session: Parsed session object
        
    Returns:
        Number of user turns
    """
    return sum(1 for t in session.turns if t.speaker == "user")


def calculate_slash_command_usage(session: Session) -> float:
    """Calculate percentage of user turns with slash commands.
    
    Formula: (slash_commands_used / user_turns) * 100
    Target: >30% (power user behavior)
    
    Edge cases:
    - user_turns == 0: Return 0.0 (no user interaction)
    - No slash commands: Return 0.0
    
    Args:
        session: Parsed session object
        
    Returns:
        Percentage rounded to 1 decimal place
    """
    user_turns = sum(1 for t in session.turns if t.speaker == "user")
    
    if user_turns == 0:
        return 0.0
    
    return round((len(session.slash_commands) / user_turns) * 100, 1)


def calculate_error_rate(session: Session) -> float:
    """Calculate percentage of turns with errors.
    
    Formula: (turns_with_error / total_turns) * 100
    Target: <10%
    
    Edge cases:
    - total_turns == 0: Return 0.0 (empty session)
    - No errors: Return 0.0
    
    Args:
        session: Parsed session object
        
    Returns:
        Percentage rounded to 1 decimal place
    """
    if len(session.turns) == 0:
        return 0.0
    
    error_turns = sum(1 for t in session.turns if t.has_error)
    return round((error_turns / len(session.turns)) * 100, 1)


def calculate_overall_score(
    passing_metrics: int,
    total_metrics: int,
    anti_patterns: list[AntiPattern]
) -> int:
    """Calculate overall session score (0-100).
    
    Formula: (passing_metrics / total_metrics) * 100 - anti_pattern_penalty
    
    Anti-pattern penalties:
    - Critical: -10 points each
    - High: -5 points each
    - Medium: -3 points each
    - Low: -1 point each
    
    Score bounds: max(0, min(100, score))
    
    Args:
        passing_metrics: Number of metrics that passed their targets
        total_metrics: Total number of metrics evaluated
        anti_patterns: List of detected anti-patterns
        
    Returns:
        Overall score as integer (0-100)
    """
    base_score = (passing_metrics / total_metrics) * 100
    
    penalty = sum(
        {"critical": 10, "high": 5, "medium": 3, "low": 1}[ap.severity]
        for ap in anti_patterns
    )
    
    final_score = base_score - penalty
    return max(0, min(100, int(final_score)))


def calculate_all_metrics(session: Session) -> dict[str, dict[str, float | int | bool | str]]:
    """Calculate all metrics for a session.
    
    Returns a dictionary with metric names as keys and metric data as values.
    Each metric contains: value, target, unit, pass status.
    
    Args:
        session: Parsed session object
        
    Returns:
        Dictionary of all calculated metrics
    """
    plan_to_code = calculate_plan_to_code_ratio(session)
    efficiency = calculate_bobcoin_efficiency(session)
    conversation = calculate_conversation_count(session)
    slash_usage = calculate_slash_command_usage(session)
    error_rate = calculate_error_rate(session)
    
    return {
        "plan_to_code_ratio": {
            "value": plan_to_code,
            "target": 20.0,
            "unit": "percent",
            "pass": plan_to_code >= 20.0
        },
        "bobcoin_efficiency": {
            "value": efficiency,
            "target": 5.0,
            "unit": "deliverables_per_0.1_dollars",
            "pass": efficiency >= 5.0
        },
        "conversation_count": {
            "value": conversation,
            "target": 15,
            "unit": "turns",
            "pass": conversation <= 15
        },
        "slash_command_usage": {
            "value": slash_usage,
            "target": 30.0,
            "unit": "percent",
            "pass": slash_usage >= 30.0
        },
        "error_rate": {
            "value": error_rate,
            "target": 10.0,
            "unit": "percent",
            "pass": error_rate <= 10.0
        }
    }


# Made with Bob
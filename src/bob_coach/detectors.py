"""Anti-pattern detectors for Bob Coach.

Each detector analyzes a parsed Session and returns a list of AntiPattern findings.
All detection is rule-based (no LLM calls) and produces explainable evidence.
"""

from bob_coach.models import Session, AntiPattern
from bob_coach.rules import (
    COST_DRIFT_THRESHOLD_PER_TURN,
    COST_DRIFT_THRESHOLD_SESSION,
    PLAN_FILE_NAMES,
    CODE_MODE_TURN_THRESHOLD,
    FILE_EDIT_THRESHOLD,
    CONSECUTIVE_ASK_THRESHOLD,
    MODE_SWITCH_THRESHOLD,
    MODE_SWITCH_WINDOW_SIZE,
    FILE_EDIT_TOOLS,
    MARKDOWN_EXTENSIONS,
)


def detect_missing_plan_file(session: Session) -> list[AntiPattern]:
    """Detect Code mode sessions without plan file references.
    
    Rule: Sessions with >3 Code mode turns where no PLAN.md/TODO.md/AGENTS.md
          appears in visible_files or open_tabs.
    
    Args:
        session: Parsed session object from Phase 1
        
    Returns:
        List of AntiPattern findings (empty if no issues detected)
    """
    findings = []
    
    # Count Code mode turns and check for plan files
    code_turns = []
    has_plan_file = False
    
    for turn in session.turns:
        if turn.mode == "code":
            code_turns.append(turn.index)
            
            # Check if this turn has plan files visible
            if turn.environment:
                all_files = turn.environment.visible_files + turn.environment.open_tabs
                # Case-insensitive matching
                if any(pf.lower() in [f.lower() for f in all_files] for pf in PLAN_FILE_NAMES):
                    has_plan_file = True
                    break
    
    # Only flag if >3 Code mode turns without plan file
    if len(code_turns) > CODE_MODE_TURN_THRESHOLD and not has_plan_file:
        evidence = [
            f"{len(code_turns)} Code mode turns detected (turns {min(code_turns)}-{max(code_turns)})",
            f"No plan files found in visible files or open tabs"
        ]
        
        findings.append(AntiPattern(
            name="Missing Plan File",
            severity="high",
            description="Code mode session without PLAN.md, TODO.md, or AGENTS.md reference",
            evidence=evidence,
            recommendation=(
                "Create PLAN.md or TODO.md before starting Code mode. Use 'update_todo_list' tool "
                "or switch to Plan mode with '/plan' to document your approach before coding."
            )
        ))
    
    return findings


def detect_cost_drift(session: Session) -> list[AntiPattern]:
    """Detect high-cost turns or sessions (cost-based drift).
    
    Rule: Single turn cost_delta >$0.30 OR session total_cost >$1.50.
    Handles negative deltas (parser artifacts) by using max(0, delta).
    
    Args:
        session: Parsed session object from Phase 1
        
    Returns:
        List of AntiPattern findings (empty if no issues detected)
    """
    findings = []
    
    # Check for single-turn drift
    high_cost_turns = []
    has_negative_deltas = False
    
    for turn in session.turns:
        effective_delta = max(0.0, turn.cost_delta)
        
        if turn.cost_delta < 0:
            has_negative_deltas = True
        
        if effective_delta > COST_DRIFT_THRESHOLD_PER_TURN:
            high_cost_turns.append((turn.index, effective_delta))
    
    if high_cost_turns:
        evidence = [
            f"Turn {idx}: ${delta:.2f} cost increase"
            for idx, delta in high_cost_turns
        ]
        
        findings.append(AntiPattern(
            name="Cost-Based Drift (Single Turn)",
            severity="critical",
            description=f"Turn(s) with cost increase >${COST_DRIFT_THRESHOLD_PER_TURN:.2f}",
            evidence=evidence,
            recommendation=(
                "High cost suggests unfocused task or missing decomposition. Break work into "
                "smaller phases. Use '/review' to checkpoint progress. Consider switching to "
                "Plan mode to refine approach."
            )
        ))
    
    # Check for session-level drift
    if session.total_cost > COST_DRIFT_THRESHOLD_SESSION:
        evidence = [f"Total session cost: ${session.total_cost:.2f} across {len(session.turns)} turns"]
        
        if has_negative_deltas:
            evidence.append("Note: Session contains negative cost deltas (missing environment blocks)")
        
        findings.append(AntiPattern(
            name="Cost-Based Drift (Session)",
            severity="critical",
            description=f"Session total cost >${COST_DRIFT_THRESHOLD_SESSION:.2f}",
            evidence=evidence,
            recommendation=(
                "High session cost suggests unfocused work or missing phase breaks. Export session "
                "history and start a new focused session for the next phase."
            )
        ))
    
    return findings


def detect_missing_review(session: Session) -> list[AntiPattern]:
    """Detect Code sessions with >5 file edits but no /review command.
    
    Rule: Count write_to_file/apply_diff/insert_content uses, check for 'review'
          in session.slash_commands.
    
    Args:
        session: Parsed session object from Phase 1
        
    Returns:
        List of AntiPattern findings (empty if no issues detected)
    """
    findings = []
    
    # Count file edit tools
    edit_count = session.file_edits
    
    # Check for /review command
    has_review = "review" in session.slash_commands
    
    if edit_count > FILE_EDIT_THRESHOLD and not has_review:
        # Count by tool type for detailed evidence
        tool_counts = {}
        for turn in session.turns:
            if turn.speaker == "assistant":
                for tool in turn.tool_uses:
                    if tool.name in FILE_EDIT_TOOLS:
                        tool_counts[tool.name] = tool_counts.get(tool.name, 0) + 1
        
        tool_breakdown = ", ".join(f"{name}: {count}" for name, count in tool_counts.items())
        
        evidence = [
            f"{edit_count} file edits detected ({tool_breakdown})",
            "No /review command found in user messages"
        ]
        
        findings.append(AntiPattern(
            name="Missing /review Command",
            severity="medium",
            description=f"Code session with >{FILE_EDIT_THRESHOLD} file edits without review",
            evidence=evidence,
            recommendation=(
                "Run '/review' after making >5 file changes to catch bugs early. Code review "
                "reduces rework and improves quality."
            )
        ))
    
    return findings


def detect_tool_errors(session: Session) -> list[AntiPattern]:
    """Detect [ERROR] messages following assistant tool use.
    
    Rule: If turn.has_error and previous turn was assistant with tool_uses.
    
    Args:
        session: Parsed session object from Phase 1
        
    Returns:
        List of AntiPattern findings (empty if no issues detected)
    """
    findings = []
    error_turns = []
    
    for i, turn in enumerate(session.turns):
        if turn.has_error:
            # Check if previous turn was assistant with tool use
            if i > 0:
                prev_turn = session.turns[i - 1]
                if prev_turn.speaker == "assistant" and prev_turn.tool_uses:
                    tool_names = [tool.name for tool in prev_turn.tool_uses]
                    error_turns.append((turn.index, prev_turn.index, tool_names))
            else:
                # Error in first turn (no previous turn)
                error_turns.append((turn.index, None, []))
    
    if error_turns:
        evidence = []
        for error_idx, tool_idx, tool_names in error_turns:
            if tool_idx is not None:
                tools_str = ", ".join(tool_names)
                evidence.append(f"Turn {error_idx}: [ERROR] after {tools_str} in Turn {tool_idx}")
            else:
                evidence.append(f"Turn {error_idx}: [ERROR] (no previous tool use)")
        
        findings.append(AntiPattern(
            name="Tool Use Errors",
            severity="high",
            description="[ERROR] messages following tool invocations",
            evidence=evidence,
            recommendation=(
                "Tool errors indicate unclear requirements or incorrect parameters. Review tool "
                "documentation and task context before retrying. Use 'ask_followup_question' if "
                "requirements are ambiguous."
            )
        ))
    
    return findings


def detect_conversation_loops(session: Session) -> list[AntiPattern]:
    """Detect >3 consecutive ask_followup_question uses.
    
    Rule: Track consecutive ask_followup_question tool uses in assistant turns.
    
    Args:
        session: Parsed session object from Phase 1
        
    Returns:
        List of AntiPattern findings (empty if no issues detected)
    """
    findings = []
    
    consecutive_asks = 0
    max_consecutive = 0
    loop_start = None
    loop_end = None
    
    for turn in session.turns:
        if turn.speaker == "assistant":
            has_ask = any(tool.name == "ask_followup_question" for tool in turn.tool_uses)
            
            if has_ask:
                if consecutive_asks == 0:
                    loop_start = turn.index
                consecutive_asks += 1
                loop_end = turn.index
                
                if consecutive_asks > max_consecutive:
                    max_consecutive = consecutive_asks
            else:
                consecutive_asks = 0
    
    if max_consecutive > CONSECUTIVE_ASK_THRESHOLD:
        evidence = [
            f"{max_consecutive} consecutive ask_followup_question uses in turns {loop_start}-{loop_end}"
        ]
        
        findings.append(AntiPattern(
            name="Conversation Loops",
            severity="medium",
            description=f">{CONSECUTIVE_ASK_THRESHOLD} consecutive clarification questions",
            evidence=evidence,
            recommendation=(
                "Excessive back-and-forth suggests unclear task specification. Provide more "
                "context upfront or use 'read_file' to gather information independently before "
                "asking questions."
            )
        ))
    
    return findings


def detect_mode_thrashing(session: Session) -> list[AntiPattern]:
    """Detect >4 mode switches in <10 turns (mode thrashing).
    
    Rule: Count mode transitions in sliding 10-turn windows.
    
    Args:
        session: Parsed session object from Phase 1
        
    Returns:
        List of AntiPattern findings (empty if no issues detected)
    """
    findings = []
    
    # For short sessions, check entire session
    if len(session.turns) < MODE_SWITCH_WINDOW_SIZE:
        if len(session.mode_transitions) > MODE_SWITCH_THRESHOLD:
            mode_sequence = " → ".join(
                f"{t.to_mode}" for t in session.mode_transitions
            )
            
            evidence = [
                f"{len(session.mode_transitions)} mode switches in {len(session.turns)} turns: {mode_sequence}"
            ]
            
            findings.append(AntiPattern(
                name="Mode Thrashing",
                severity="low",
                description=f">{MODE_SWITCH_THRESHOLD} mode switches in short session",
                evidence=evidence,
                recommendation=(
                    "Frequent mode changes suggest task scope uncertainty. Spend more time in Plan "
                    "mode to clarify approach before switching to Code or Ask modes."
                )
            ))
    else:
        # Check sliding windows
        for i in range(len(session.turns) - MODE_SWITCH_WINDOW_SIZE + 1):
            window_end = i + MODE_SWITCH_WINDOW_SIZE
            transitions_in_window = [
                t for t in session.mode_transitions
                if i <= t.turn_index < window_end
            ]
            
            if len(transitions_in_window) > MODE_SWITCH_THRESHOLD:
                mode_sequence = " → ".join(t.to_mode for t in transitions_in_window)
                
                evidence = [
                    f"{len(transitions_in_window)} mode switches in turns {i}-{window_end-1}: {mode_sequence}"
                ]
                
                findings.append(AntiPattern(
                    name="Mode Thrashing",
                    severity="low",
                    description=f">{MODE_SWITCH_THRESHOLD} mode switches in {MODE_SWITCH_WINDOW_SIZE}-turn window",
                    evidence=evidence,
                    recommendation=(
                        "Frequent mode changes suggest task scope uncertainty. Spend more time in Plan "
                        "mode to clarify approach before switching to Code or Ask modes."
                    )
                ))
                break  # Only report first window with thrashing
    
    return findings


def detect_plan_mode_violations(session: Session) -> list[AntiPattern]:
    """Detect write_to_file/apply_diff attempts in Plan mode for non-markdown files.
    
    Rule: Check both tool_uses (primary signal) and has_error (fallback signal).
          Weight evidence by confidence: both signals = high confidence,
          one signal = possible violation.
    
    Args:
        session: Parsed session object from Phase 1
        
    Returns:
        List of AntiPattern findings (empty if no issues detected)
    """
    findings = []
    violations = []
    
    for turn in session.turns:
        if turn.mode == "plan" and turn.speaker == "assistant":
            # Check for write tools
            write_tools = [
                tool for tool in turn.tool_uses
                if tool.name in ["write_to_file", "apply_diff"]
            ]
            
            for tool in write_tools:
                path = tool.parameters.get("path", "")
                
                # Check if path is non-markdown
                is_markdown = any(path.lower().endswith(ext) for ext in MARKDOWN_EXTENSIONS)
                
                if path and not is_markdown:
                    # Tool signal present
                    if turn.has_error:
                        # Both signals: high confidence
                        violations.append((
                            turn.index,
                            f"Turn {turn.index}: {tool.name}('{path}') in Plan mode + [ERROR] detected",
                            "high"
                        ))
                    else:
                        # Tool only: possible violation
                        violations.append((
                            turn.index,
                            f"Turn {turn.index}: Possible violation - {tool.name}('{path}') in Plan mode (no error detected)",
                            "possible"
                        ))
                elif not path and turn.has_error:
                    # Error only: possible violation (path not extracted)
                    violations.append((
                        turn.index,
                        f"Turn {turn.index}: Possible violation - [ERROR] in Plan mode after {tool.name} (path not extracted)",
                        "possible"
                    ))
    
    if violations:
        evidence = [v[1] for v in violations]
        
        findings.append(AntiPattern(
            name="Plan-Mode Write Violation",
            severity="medium",
            description="Attempted to edit non-markdown files in Plan mode",
            evidence=evidence,
            recommendation=(
                "Switch to Code mode before editing non-markdown files. Use 'switch_mode' tool "
                "or '/code' command to transition modes."
            )
        ))
    
    return findings


# Made with Bob

def detect_repeated_file_reads(session: Session) -> list[AntiPattern]:
    """Detect files read 3+ times in a session (suggests context loss).
    
    Rule: Same file path appears in read_file tool uses ≥3 times across session.
    
    Parameter structure verified from phase-1.md parsing:
    - read_file stores content in parameters['args']
    - args contains nested XML: <file><path>filename</path></file>
    - Multiple files can be in single read_file call
    
    Args:
        session: Parsed session object from Phase 1
        
    Returns:
        List of AntiPattern findings (empty if no issues detected)
    """
    import re
    
    findings = []
    
    # Count file reads across all turns
    file_read_counts: dict[str, int] = {}
    
    for turn in session.turns:
        if turn.speaker == "assistant":
            for tool in turn.tool_uses:
                if tool.name == "read_file":
                    # Extract file paths from nested XML in args parameter
                    args_content = tool.parameters.get("args", "")
                    
                    # Find all <path>...</path> tags
                    for match in re.finditer(r'<path>(.+?)</path>', args_content):
                        file_path = match.group(1)
                        file_read_counts[file_path] = file_read_counts.get(file_path, 0) + 1
    
    # Find files read 3+ times
    repeated_files = {path: count for path, count in file_read_counts.items() if count >= 3}
    
    if repeated_files:
        # Sort by count (descending) for evidence
        sorted_files = sorted(repeated_files.items(), key=lambda x: -x[1])
        
        evidence = [
            f"{path}: {count} reads"
            for path, count in sorted_files
        ]
        
        findings.append(AntiPattern(
            name="Repeated File Reads",
            severity="medium",
            description=f"{len(repeated_files)} file(s) read 3+ times in session",
            evidence=evidence,
            recommendation=(
                "Cache file context. Re-reading suggests context loss between turns. "
                "Consider using read_file with line ranges for targeted updates, or "
                "reference previous reads in your prompts to maintain context."
            )
        ))
    
    return findings


# Made with Bob
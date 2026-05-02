"""Report generation for Bob Coach (terminal and JSON formats)."""

import json
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from bob_coach.models import Session, AntiPattern
from bob_coach.metrics import calculate_overall_score


def _calculate_duration_minutes(session: Session) -> int | None:
    """Calculate session duration from first to last turn timestamps.
    
    Returns None if timestamps are missing or unreliable.
    """
    timestamps = [t.timestamp for t in session.turns if t.timestamp is not None]
    
    if len(timestamps) < 2:
        return None
    
    duration = timestamps[-1] - timestamps[0]
    return int(duration.total_seconds() / 60)


def _get_mode_distribution(session: Session) -> dict[str, int]:
    """Count turns per mode."""
    modes: dict[str, int] = {}
    for turn in session.turns:
        if turn.mode:
            modes[turn.mode] = modes.get(turn.mode, 0) + 1
    return modes


def render_terminal_report(
    session: Session,
    metrics: dict[str, dict[str, float | int | bool | str]],
    anti_patterns: list[AntiPattern],
    session_filename: str
) -> str:
    """Render coaching report for terminal display using Rich library.
    
    Args:
        session: Parsed session object
        metrics: Calculated metrics from calculate_all_metrics()
        anti_patterns: List of detected anti-patterns
        session_filename: Name of the session file being analyzed
        
    Returns:
        Formatted string with Rich markup for terminal display
    """
    # Force UTF-8 for Rich console to handle emojis on Windows
    import io
    console = Console(record=True, file=io.StringIO(), force_terminal=True, legacy_windows=False)
    
    # Header Panel
    duration = _calculate_duration_minutes(session)
    duration_str = f" | Duration: {duration}m" if duration else ""
    
    header = Panel(
        f"[bold]🎯 Bob Coach Report[/bold]\n"
        f"Session: {Path(session_filename).name}\n"
        f"Cost: ${session.total_cost:.2f} | Turns: {len(session.turns)}{duration_str}",
        border_style="blue"
    )
    console.print(header)
    console.print()
    
    # Metrics Table
    metrics_table = Table(
        title="📊 Metrics Summary",
        show_header=True,
        header_style="bold cyan"
    )
    metrics_table.add_column("Metric", style="white", width=25)
    metrics_table.add_column("Target", justify="right", style="dim", width=9)
    metrics_table.add_column("Actual", justify="right", style="white", width=9)
    metrics_table.add_column("Status", justify="center", width=8)
    
    metric_names = {
        "plan_to_code_ratio": "Plan-to-Code Ratio",
        "bobcoin_efficiency": "Bobcoin Efficiency",
        "conversation_count": "Conversation Count",
        "slash_command_usage": "Slash Command Usage",
        "error_rate": "Error Rate"
    }
    
    for key, display_name in metric_names.items():
        metric = metrics[key]
        value = metric["value"]
        target = metric["target"]
        passed = metric["pass"]
        
        # Format value based on unit
        if metric["unit"] == "percent":
            value_str = f"{value:.1f}%"
            target_str = f">{target:.0f}%" if key in ["plan_to_code_ratio", "slash_command_usage"] else f"<{target:.0f}%"
        elif key == "bobcoin_efficiency":
            value_str = f"{value:.1f}/$0.1"
            target_str = f">{target:.0f}/$0.1"
        else:
            value_str = str(int(value))
            target_str = f"<{int(target)}"
        
        status = "[green]✓ Pass[/green]" if passed else "[red]✗ Fail[/red]"
        
        metrics_table.add_row(display_name, target_str, value_str, status)
    
    console.print(metrics_table)
    console.print()
    
    # Anti-Patterns Section
    if anti_patterns:
        # Group by severity
        severity_order = ["critical", "high", "medium", "low"]
        grouped = {sev: [] for sev in severity_order}
        for ap in anti_patterns:
            grouped[ap.severity].append(ap)
        
        # Count for header
        console.print(f"[bold]⚠️  Anti-Patterns Detected ({len(anti_patterns)})[/bold]")
        console.print()
        
        # Render each severity group
        severity_colors = {
            "critical": "bold red",
            "high": "red",
            "medium": "yellow",
            "low": "dim yellow"
        }
        
        for severity in severity_order:
            patterns = grouped[severity]
            if not patterns:
                continue
            
            for pattern in patterns:
                color = severity_colors[severity]
                console.print(f"[{color}][{severity.upper()}] {pattern.name}[/{color}]")
                
                # Evidence
                console.print("  Evidence:")
                for evidence in pattern.evidence:
                    console.print(f"    [dim white]• {evidence}[/dim white]")
                
                # Recommendation (wrapped at 60 chars, indented)
                console.print("  Recommendation:")
                # Simple word wrapping
                words = pattern.recommendation.split()
                line = "    "
                for word in words:
                    if len(line) + len(word) + 1 > 64:
                        console.print(f"[white]{line}[/white]")
                        line = "    " + word
                    else:
                        line += (" " if line != "    " else "") + word
                if line.strip():
                    console.print(f"[white]{line}[/white]")
                
                console.print()
    else:
        console.print("[bold green]✅ No Anti-Patterns Detected[/bold green]")
        console.print()
        console.print("All checks passed! This session demonstrates good Bob usage practices.")
        console.print()
    
    # Summary Score
    passing_count = sum(1 for m in metrics.values() if m["pass"])
    total_count = len(metrics)
    overall_score = calculate_overall_score(passing_count, total_count, anti_patterns)
    
    console.print(f"[bold]✅ Session Score: {overall_score}/100[/bold]")
    console.print(f"   {passing_count}/{total_count} metrics passing | {len(anti_patterns)} anti-patterns detected")
    
    return console.export_text()


def render_json_report(
    session: Session,
    metrics: dict[str, dict[str, float | int | bool | str]],
    anti_patterns: list[AntiPattern],
    session_filename: str
) -> str:
    """Render coaching report as JSON.
    
    Args:
        session: Parsed session object
        metrics: Calculated metrics from calculate_all_metrics()
        anti_patterns: List of detected anti-patterns
        session_filename: Name of the session file being analyzed
        
    Returns:
        JSON string conforming to schema v1.0.0
    """
    # Session metadata
    user_turns = sum(1 for t in session.turns if t.speaker == "user")
    assistant_turns = sum(1 for t in session.turns if t.speaker == "assistant")
    duration = _calculate_duration_minutes(session)
    modes_used = list(_get_mode_distribution(session).keys())
    
    # Anti-pattern counts by severity
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for ap in anti_patterns:
        severity_counts[ap.severity] += 1
    
    # Overall score
    passing_count = sum(1 for m in metrics.values() if m["pass"])
    total_count = len(metrics)
    overall_score = calculate_overall_score(passing_count, total_count, anti_patterns)
    
    # Build JSON structure
    report = {
        "version": "1.0.0",
        "session_metadata": {
            "filename": Path(session_filename).name,
            "total_cost": round(session.total_cost, 2),
            "turn_count": len(session.turns),
            "user_turns": user_turns,
            "assistant_turns": assistant_turns,
            "duration_minutes": duration,
            "workspace": session.workspace,
            "modes_used": modes_used
        },
        "metrics": metrics,
        "anti_patterns": [
            {
                "name": ap.name,
                "severity": ap.severity,
                "description": ap.description,
                "evidence": ap.evidence,
                "recommendation": ap.recommendation
            }
            for ap in anti_patterns
        ],
        "summary": {
            "overall_score": overall_score,
            "passing_metrics_count": passing_count,
            "total_metrics_count": total_count,
            "anti_pattern_count_by_severity": severity_counts,
            "total_anti_patterns": len(anti_patterns)
        }
    }
    
    return json.dumps(report, indent=2)


# Made with Bob
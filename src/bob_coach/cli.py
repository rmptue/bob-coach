"""CLI entry point for Bob Coach."""

from pathlib import Path

import click

from bob_coach import __version__
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
from bob_coach.metrics import calculate_all_metrics
from bob_coach.report import render_terminal_report, render_json_report


@click.command()
@click.argument("session_file", type=click.Path(exists=True))
@click.option(
    "--format",
    type=click.Choice(["terminal", "json"], case_sensitive=False),
    default="terminal",
    help="Output format (terminal or json)",
)
@click.option(
    "--output",
    type=click.Path(),
    help="Output file path (default: stdout)",
)
@click.option(
    "--compact",
    is_flag=True,
    default=False,
    help="Compact terminal output (~40 lines, for demo videos)",
)
@click.version_option(version=__version__)
def main(session_file: str, format: str, output: str | None, compact: bool) -> None:
    """Analyze IBM Bob session exports for anti-patterns and metrics."""
    try:
        # 1. Parse session
        session = parse_session(Path(session_file))
        
        # 2. Run all detectors
        all_findings = []
        detectors = [
            detect_missing_plan_file,
            detect_cost_drift,
            detect_missing_review,
            detect_tool_errors,
            detect_conversation_loops,
            detect_mode_thrashing,
            detect_plan_mode_violations,
            detect_repeated_file_reads,
        ]
        for detector in detectors:
            all_findings.extend(detector(session))
        
        # 3. Calculate metrics
        metrics = calculate_all_metrics(session)
        
        # 4. Render report
        if format.lower() == "terminal":
            report = render_terminal_report(session, metrics, all_findings, session_file, compact=compact)
        else:
            report = render_json_report(session, metrics, all_findings, session_file)
        
        # 5. Output
        if output:
            Path(output).write_text(report, encoding="utf-8")
            click.echo(f"Report written to {output}")
        else:
            # Write to stdout with UTF-8 encoding (handles emojis on Windows)
            import sys
            try:
                click.echo(report)
            except UnicodeEncodeError:
                # Fallback: write bytes directly with UTF-8
                sys.stdout.buffer.write(report.encode("utf-8"))
                sys.stdout.buffer.write(b"\n")
            
    except FileNotFoundError:
        click.echo(f"Error: Session file not found: {session_file}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"Error analyzing session: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    main()

# Made with Bob

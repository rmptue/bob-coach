"""CLI entry point for Bob Coach."""

import click
from bob_coach import __version__


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
@click.version_option(version=__version__)
def main(session_file: str, format: str, output: str | None) -> None:
    """Analyze IBM Bob session exports for anti-patterns and metrics."""
    click.echo(f"Bob Coach v{__version__} — Phase 0 stub")
    click.echo(f"Session file: {session_file}")
    click.echo(f"Format: {format}")
    if output:
        click.echo(f"Output: {output}")


if __name__ == "__main__":
    main()

# Made with Bob

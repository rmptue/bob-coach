"""Regenerate all demo outputs as clean UTF-8.

Bypasses PowerShell's encoding chain by running the CLI as a Python subprocess
and writing files directly via Python's UTF-8 file handling.
"""
import subprocess
import sys
from pathlib import Path

SESSIONS = [
    "phase-0",
    "phase-1",
    "phase-2",
    "phase-3",
    "phase-planning",
    "sample-session-01",
    "sample-session-02",
]

def run_bob_coach(session_path: Path, compact: bool = False, json_output: bool = False) -> str:
    """Run bob-coach and return stdout as a UTF-8 string."""
    cmd = ["bob-coach", str(session_path)]
    if compact:
        cmd.append("--compact")
    if json_output:
        cmd.append("--json")

    result = subprocess.run(
        cmd,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr}", file=sys.stderr)
        return ""
    return result.stdout

def main() -> int:
    out_dir = Path("demo/outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    sessions_dir = Path("bob_sessions")

    for s in SESSIONS:
        src = sessions_dir / f"{s}.md"
        if not src.exists():
            print(f"SKIP {src} (not found)")
            continue

        # Full mode .txt
        text = run_bob_coach(src, compact=False)
        (out_dir / f"{s}-report.txt").write_text(text, encoding="utf-8")

        # JSON mode .json
        json_text = run_bob_coach(src, json_output=True)
        (out_dir / f"{s}-report.json").write_text(json_text, encoding="utf-8")

        print(f"OK   {s}")

    # Compact mode (only the demo target)
    text = run_bob_coach(sessions_dir / "phase-1.md", compact=True)
    (out_dir / "phase-1-compact.txt").write_text(text, encoding="utf-8")
    print("OK   phase-1-compact")

    print(f"\nDone. {len(SESSIONS) + 1} files written to {out_dir}/")
    return 0

if __name__ == "__main__":
    sys.exit(main())
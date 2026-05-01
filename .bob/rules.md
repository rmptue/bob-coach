# Bob Coach Development Rules

## Core Constraints
- **No LLM calls** - All detection is rule-based (regex, thresholds, counts)
- **Offline demo** - Must work without network access
- **Python 3.10+** - Use modern type hints: `list[str]`, `dict[str, int]`, `X | None`
- **Explainable** - Every anti-pattern must cite evidence and recommendation

## Anti-Pattern Detection
Each detector follows this pattern:
```python
def detect_pattern(session: Session) -> list[AntiPattern]:
    """Rule: [explicit condition] | Evidence: [what to extract] | Recommendation: [fix]"""
    findings = []
    # Rule logic (no LLM calls)
    return findings
```

## Cost-Based Detection
- Token counts NOT in exports (only in IDE)
- Use cost deltas and cumulative costs only
- Thresholds: >$0.30/turn, >$1.50/session

## File Conventions
- **Parser**: Handle malformed input gracefully (try/except, skip bad turns)
- **Models**: All fields have type hints, use `| None` for optional
- **Reports**: Terminal (rich) and JSON must contain identical data

## Testing
- Commit 2+ fixtures: simple (2-turn) and complex (planning session)
- Every detector has unit tests
- Parser handles malformed input without crashing

## Session Discipline
- Export to `bob_sessions/<phase>.md` after each phase
- Run `/review` before completing phases with >5 file changes
- Reference PLAN.md at start of each phase
- Keep sessions focused (avoid conversation loops)

## Budget
- Total: 40 coins | Planned: 35 coins | Buffer: 5 coins
- Track cumulative spend after each phase
- Prioritize Phase 1-3 if approaching 35 coins
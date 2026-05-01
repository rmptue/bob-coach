# Bob Coach - Agent Context

This file provides persistent context for IBM Bob across all development sessions.

## Project Identity

**Name:** Bob Coach  
**Type:** Python CLI tool  
**Purpose:** Analyze IBM Bob session exports to surface anti-patterns, bobcoin efficiency metrics, and plan-discipline scores  
**Target:** IBM Bob Dev Day Hackathon (May 1-3, 2026)

## Technical Constraints

### Language & Runtime
- **Python 3.10+** (use modern type hints: `list[str]`, `dict[str, int]`, `X | None`)
- **Standard library preferred** for parsing (no heavy frameworks)
- **Lightweight dependencies only:**
  - `click` - CLI framework
  - `rich` - Terminal formatting
  - `pytest` - Testing

### Architecture Principles
- **Rule-based detection only** - No LLM calls inside the tool
- **Explainable anti-patterns** - Every detection must have clear evidence and recommendation
- **Offline-first** - Demo must work without network access
- **CLI-first design** - Terminal is primary interface, JSON is secondary

### Input/Output
- **Input:** Bob session markdown exports (from Views → More Actions → History → Export task history)
- **Output:** 
  - Human-readable terminal reports (rich formatting)
  - Machine-readable JSON (for automation)

## Project Structure

```
bob-coach/
├── src/bob_coach/
│   ├── __init__.py          # Package marker, version
│   ├── cli.py               # Click CLI entry point
│   ├── parser.py            # Session markdown parser
│   ├── models.py            # Data classes (Session, Turn, etc.)
│   ├── detectors.py         # Anti-pattern detection logic
│   ├── rules.py             # Anti-pattern rule definitions
│   ├── metrics.py           # Metric calculation functions
│   └── report.py            # Report generation (terminal + JSON)
├── tests/
│   ├── test_parser.py
│   ├── test_detectors.py
│   └── test_report.py
├── fixtures/
│   └── sample-session-01.md # Sample Bob export for testing
├── bob_sessions/            # Bob Coach's own session exports (for demo)
├── .bob/
│   ├── rules.md             # Bob-specific project rules
│   └── commands/            # Custom slash commands
├── pyproject.toml           # Project config, dependencies
├── PLAN.md                  # Implementation plan (5 phases)
├── AGENTS.md                # This file
└── README.md                # User documentation
```

## Development Workflow

### Session Organization
Each phase should be a focused Bob session producing shippable code:
- **Phase 0:** Project skeleton (pyproject.toml, CLI stub, tests)
- **Phase 1:** Parser (extract turns, modes, costs, tools from markdown)
- **Phase 2:** Anti-pattern detectors (6 rule-based detectors)
- **Phase 3:** Report renderer (terminal + JSON output)
- **Phase 4:** Recursive demo (analyze Bob Coach's own sessions)
- **Phase 5:** Polish (README, docs, packaging)

### Bobcoin Budget
- **Total:** 40 coins
- **Planned spend:** 35 coins (5-coin safety buffer)
- **Per phase:** See [`PLAN.md`](PLAN.md) budget table

### Quality Gates
- All code must have type hints
- Parser must handle malformed input gracefully
- Anti-patterns must have clear recommendations
- Demo must complete in <3 minutes
- Tests must pass before phase completion

## Anti-Pattern Detection Rules

Bob Coach detects these anti-patterns (see [`PLAN.md`](PLAN.md) Phase 2 for details):

1. **Missing Plan File** - Code mode without PLAN.md/TODO.md reference
2. **Cost-Based Drift** - Single turn >$0.30 OR session >$1.50 (token counts not in exports)
3. **Missing /review** - >5 file edits without review command
4. **Tool Use Errors** - [ERROR] messages after tool use
5. **Conversation Loops** - >3 consecutive ask_followup_question uses
6. **Mode Thrashing** - >4 mode switches in <10 turns
7. **Plan-Mode Write Violation** - write_to_file/apply_diff in Plan mode for non-markdown

All detectors are **rule-based** (no LLM inference) and **explainable** (evidence + recommendation).

## Key Metrics

- **Plan-to-Code Ratio:** `(plan_turns / code_turns) * 100` (target: >20%)
- **Bobcoin Efficiency:** `deliverables / total_cost` (target: >5 per $0.10)
- **Conversation Count:** `user_turns` (target: <15)
- **Slash Command Usage:** `slash_commands / user_turns` (target: >30%)
- **Error Rate:** `error_turns / total_turns * 100` (target: <10%)

## Demo Requirements

The recursive demo must:
- Run offline against fixture files
- Analyze Bob Coach's own development sessions
- Fit within 3-minute video limit
- Showcase all key features (parsing, detection, metrics, reports)
- Output both terminal and JSON formats

## Bob-Specific Rules

### File Editing
- Use [`apply_diff`](PLAN.md) for surgical edits to existing files
- Use [`write_to_file`](PLAN.md) only for new files or complete rewrites
- Use [`insert_content`](PLAN.md) for adding lines without modifying existing content

### Session Discipline
- Export session history after each phase to [`bob_sessions/`](bob_sessions/)
- Use `/review` before completing phases with >5 file changes
- Keep sessions focused (avoid conversation loops)
- Reference [`PLAN.md`](PLAN.md) at start of each phase

### Testing
- Write tests alongside implementation (not after)
- Use pytest fixtures for sample session data
- Test edge cases (malformed input, missing fields)

## Common Pitfalls to Avoid

1. **Over-engineering:** Keep it simple - rule-based detection, no ML
2. **Scope creep:** Stick to 6 anti-patterns, don't add more mid-development
3. **Parser brittleness:** Handle missing/malformed fields gracefully
4. **Demo complexity:** Pre-generate outputs, don't compute live in video
5. **Budget overrun:** Use `/review` proactively, avoid rework

## Success Criteria

The project is complete when:
- ✅ Parser extracts all key elements from sample fixture
- ✅ All 6 anti-pattern detectors work with zero false positives
- ✅ Terminal and JSON reports contain identical data
- ✅ Recursive demo runs offline and fits 3-minute limit
- ✅ README provides clear installation and usage instructions
- ✅ Total bobcoin spend ≤35 coins

---

*Context file for IBM Bob | Updated: 2026-05-01*
# Bob Coach - Implementation Plan

## Project Overview

**Bob Coach** is a CLI tool that analyzes IBM Bob session exports to produce structured coaching reports. It surfaces anti-patterns, bobcoin efficiency metrics, and plan-discipline scores to help developers optimize their Bob usage.

### Goals
- Parse Bob's exported session markdown files into structured data
- Detect common anti-patterns (missing plans, dumb-zone drift, tool errors)
- Generate actionable coaching reports with scored metrics
- Demonstrate recursive self-analysis (Bob Coach analyzing its own sessions)
- Complete within 48 hours and 40 bobcoins budget

### Target Audience
IBM Bob Dev Day Hackathon judges and Bob power users seeking workflow optimization.

### Fixture Files
The [`fixtures/`](fixtures/) directory will contain at least 2 session exports:
- **sample-session-01.md** - Simple 2-turn orientation task (trivial case)
- **sample-session-02.md** - This planning session export (rich with multiple anti-patterns for validation)

---

## Export Format Analysis

Based on [`fixtures/sample-session-01.md`](fixtures/sample-session-01.md), Bob exports contain:

**Structure:**
- `**User:**` / `**Assistant:**` delimiters for conversation turns
- `<task>` XML blocks for user requests
- `<environment_details>` blocks with metadata (time, cost, mode, file context)
- Tool use XML (e.g., `<attempt_completion>`, `<ask_followup_question>`)
- Mode tags: `<slug>plan</slug>`, `<name>📝 Plan</name>`
- Cost tracking: `# Current Cost` field showing cumulative spend
- Error messages: `[ERROR]` prefixed system feedback
- Horizontal rules (`---`) separating turns

**Key Parseable Elements:**
- Turn boundaries and speaker roles
- Mode transitions (plan → code → ask, etc.)
- Cost accumulation per turn (NOTE: token counts are NOT in exports, only visible in IDE)
- Tool invocations and parameters
- Error occurrences and types (including mode restriction violations)
- Environment context (files, time, workspace)

---

## 5-Phase Implementation Plan

### Phase 0: Project Skeleton (Pre-Phase 1)
**Bobcoin Budget:** 5 coins
**Deliverables:** Scaffolded project structure (10 files including pyproject.toml)

**Files to Create:**
- [`pyproject.toml`](pyproject.toml) - Python 3.10+ project config, dependencies (click, rich), build system
- [`.gitignore`](..gitignore) - Python artifacts, `__pycache__`, `.venv`, `*.pyc`, IDE files
- [`README.md`](README.md) - Project description, installation, usage examples, demo instructions
- [`src/bob_coach/__init__.py`](src/bob_coach/__init__.py) - Package marker, version string
- [`src/bob_coach/cli.py`](src/bob_coach/cli.py) - Click-based CLI entry point, argument parsing
- [`tests/__init__.py`](tests/__init__.py) - Test package marker
- [`tests/test_parser.py`](tests/test_parser.py) - Parser unit tests (stub)
- [`AGENTS.md`](AGENTS.md) - Bob context file (already drafted)
- [`.bob/rules.md`](.bob/rules.md) - Bob-specific project rules and conventions
- [`.bob/commands/`](.bob/commands/) - Custom slash commands directory (empty initially)

**Success Criteria:**
- `pip install -e .` works
- `bob-coach --help` displays usage
- Tests run with `pytest` (even if empty)

---

### Phase 1: Parser
**Bobcoin Budget:** 8 coins
**Inputs:** Session markdown files (e.g., [`fixtures/sample-session-01.md`](fixtures/sample-session-01.md), [`fixtures/sample-session-02.md`](fixtures/sample-session-02.md))
**Deliverables:**
- [`src/bob_coach/parser.py`](src/bob_coach/parser.py) - Core parsing logic
- [`src/bob_coach/models.py`](src/bob_coach/models.py) - Data classes: `Session`, `Turn`, `ToolUse`, `ModeTransition`
- [`tests/test_parser.py`](tests/test_parser.py) - Comprehensive parser tests

**Parsing Targets:**
1. **Turn extraction:** Split on `---`, identify User/Assistant roles
2. **Mode tracking:** Extract `<slug>` and `<name>` from environment_details
3. **Cost accumulation:** Parse `# Current Cost` field, track per-turn deltas
4. **Tool use detection:** Regex match `<tool_name>` XML blocks, extract parameters
5. **Error detection:** Identify `[ERROR]` messages and context
6. **Environment metadata:** Extract timestamps, workspace paths, file lists

**Data Model:**
```python
@dataclass
class Turn:
    speaker: Literal["user", "assistant"]
    content: str
    mode: str | None
    cost_delta: float
    cumulative_cost: float
    timestamp: datetime | None
    tool_uses: list[ToolUse]
    errors: list[str]

@dataclass
class Session:
    turns: list[Turn]
    total_cost: float
    mode_transitions: list[ModeTransition]
    workspace: str | None
```

**Success Criteria:**
- Parse both sample fixtures into structured `Session` objects
- Extract all turns, modes, tool uses, and errors from both fixtures
- Cost tracking accurate across all turns
- Tests cover edge cases (missing fields, malformed XML)
- Parser designed to support future batch processing (single-file MVP)

---

### Phase 2: Anti-Pattern Detectors
**Bobcoin Budget:** 8 coins
**Inputs:** Parsed `Session` objects
**Deliverables:**
- [`src/bob_coach/detectors.py`](src/bob_coach/detectors.py) - Rule-based detector functions
- [`src/bob_coach/rules.py`](src/bob_coach/rules.py) - Anti-pattern rule definitions
- [`tests/test_detectors.py`](tests/test_detectors.py) - Detector unit tests

**Anti-Patterns to Detect:**

1. **Missing Plan File** (Severity: High)
   - Rule: Code mode session with no `PLAN.md`, `TODO.md`, or `AGENTS.md` referenced in environment_details
   - Signal: "Coding without a plan increases rework risk"

2. **Cost-Based Drift** (Severity: Critical)
   - Rule: Single turn cost delta >$0.30 OR cumulative session cost >$1.50 without phase break
   - Signal: "High cost suggests unfocused task or missing decomposition"
   - Note: Token counts are NOT in exports, use cost signals only

3. **Missing /review Command** (Severity: Medium)
   - Rule: Code mode session with >5 file edits but no `/review` in user messages
   - Signal: "Code changes without review increase bug risk"

4. **Tool Use Errors** (Severity: High)
   - Rule: `[ERROR]` message following assistant tool use
   - Signal: "Tool misuse indicates unclear requirements or Bob confusion"

5. **Conversation Loops** (Severity: Medium)
   - Rule: >3 consecutive ask_followup_question uses without progress
   - Signal: "Excessive back-and-forth suggests unclear task specification"

6. **Mode Thrashing** (Severity: Low)
   - Rule: >4 mode switches in <10 turns
   - Signal: "Frequent mode changes suggest task scope uncertainty"

7. **Plan-Mode Write Violation** (Severity: Medium)
   - Rule: `write_to_file` or `apply_diff` attempted in Plan mode for non-markdown files
   - Signal: Surfaces as `[ERROR]` with "protected configuration file" or mode restriction message
   - Recommendation: "Switch to Code mode before editing non-markdown files"

**Output Format:**
```python
@dataclass
class AntiPattern:
    name: str
    severity: Literal["low", "medium", "high", "critical"]
    description: str
    evidence: list[str]  # Turn indices or excerpts
    recommendation: str
```

**Success Criteria:**
- Detect all 7 anti-pattern types
- Zero false positives on both sample fixtures
- Each detector has clear, actionable recommendation
- All detectors are rule-based (no LLM inference)

---

### Phase 3: Coaching Report Renderer
**Bobcoin Budget:** 11 coins
**Inputs:** `Session` + detected `AntiPattern` list  
**Deliverables:**
- [`src/bob_coach/report.py`](src/bob_coach/report.py) - Report generation logic
- [`src/bob_coach/metrics.py`](src/bob_coach/metrics.py) - Metric calculation functions
- [`tests/test_report.py`](tests/test_report.py) - Report output tests

**Metrics to Calculate:**

1. **Plan-to-Code Ratio**
   - Formula: `(plan_mode_turns / code_mode_turns) * 100`
   - Target: >20% (healthy planning discipline)

2. **Bobcoin Efficiency**
   - Formula: `deliverables_count / total_cost`
   - Deliverables = file writes, successful tool uses
   - Target: >5 deliverables per $0.10

3. **Conversation Count**
   - Formula: `user_turns_count`
   - Target: <15 for focused sessions

4. **Slash Command Usage**
   - Formula: `slash_commands_used / user_turns`
   - Commands: `/review`, `/plan`, `/test`, etc.
   - Target: >30% (power user behavior)

5. **Error Rate**
   - Formula: `error_turns / total_turns * 100`
   - Target: <10%

**Output Formats:**

**Terminal (Rich library):**
```
╭─────────────────────────────────────────╮
│  Bob Coach Report                       │
│  Session: bob_task_may-2-2026...        │
│  Cost: $0.03 | Turns: 2 | Mode: plan   │
╰─────────────────────────────────────────╯

📊 Metrics
  Plan-to-Code Ratio:     100% ✓
  Bobcoin Efficiency:     33.3 deliverables/$
  Conversation Count:     2 ✓
  Slash Command Usage:    0% ⚠
  Error Rate:             50% ⚠

⚠️  Anti-Patterns Detected (1)
  [HIGH] Tool Use Errors
    Turn 2: Assistant failed to use tool initially
    → Recommendation: Review tool use requirements before responding
```

**JSON (machine-readable):**
```json
{
  "session_file": "bob_task_may-2-2026_12-07-31-am.md",
  "summary": {
    "total_cost": 0.03,
    "turn_count": 2,
    "mode_distribution": {"plan": 2}
  },
  "metrics": {
    "plan_to_code_ratio": 100.0,
    "bobcoin_efficiency": 33.3,
    "conversation_count": 2,
    "slash_command_usage": 0.0,
    "error_rate": 50.0
  },
  "anti_patterns": [
    {
      "name": "Tool Use Errors",
      "severity": "high",
      "evidence": ["Turn 2"],
      "recommendation": "Review tool use requirements before responding"
    }
  ]
}
```

**Success Criteria:**
- Terminal output uses color/formatting (rich library)
- JSON output validates against schema
- Both formats contain identical data
- Metrics match manual calculation on sample fixture

---

### Phase 4: Recursive Demo
**Bobcoin Budget:** 3 coins  
**Inputs:** Bob Coach's own session exports in [`bob_sessions/`](bob_sessions/)  
**Deliverables:**
- [`demo.sh`](demo.sh) - Demo script for video recording
- [`bob_sessions/`](bob_sessions/) - Exported sessions from Phases 0-3
- [`DEMO.md`](DEMO.md) - Demo narration script

**Demo Arc (3 minutes):**
1. **Setup (30s):** Show repo structure, explain Bob Coach purpose
2. **Run on Sample (60s):** `bob-coach fixtures/sample-session-01.md --format terminal`
   - Highlight detected anti-patterns
   - Show metrics dashboard
3. **Recursive Analysis (60s):** `bob-coach bob_sessions/*.md --format json > self-report.json`
   - Show Bob Coach analyzing its own development
   - Display aggregated metrics across all phases
4. **Insights (30s):** Narrate key findings (e.g., "Phase 2 had highest error rate, Phase 1 best bobcoin efficiency")

**Success Criteria:**
- Demo runs offline (no network calls)
- Video fits 3-minute limit
- Recursive analysis produces valid report
- Demo showcases all key features

---

### Phase 5: Polish
**Bobcoin Budget:** 2 coins  
**Deliverables:**
- Updated [`README.md`](README.md) with installation, usage, examples
- [`CONTRIBUTING.md`](CONTRIBUTING.md) - Guidelines for extending detectors
- [`LICENSE`](LICENSE) - MIT license
- Final [`DEMO.md`](DEMO.md) refinement

**README Sections:**
- Installation: `pip install bob-coach`
- Quick Start: `bob-coach path/to/session.md`
- CLI Options: `--format [terminal|json]`, `--output FILE`
- Anti-Pattern Reference: Table of all detectors
- Metrics Glossary: Definitions and targets
- Demo Video: Link to submission

**Success Criteria:**
- README clear for first-time users
- All CLI options documented
- License included
- Repo ready for public release

---

## Bobcoin Budget Summary

| Phase | Description | Estimated Coins | Cumulative |
|-------|-------------|-----------------|------------|
| 0 | Project Skeleton | 5 | 5 |
| 1 | Parser | 8 | 13 |
| 2 | Anti-Pattern Detectors | 8 | 21 |
| 3 | Coaching Report Renderer | 11 | 32 |
| 4 | Recursive Demo | 3 | 35 |
| 5 | Polish | 0 | 35 |
| **Total** | | **35** | **35/40** |

**Safety Buffer:** 5 coins for unexpected issues, refactoring, or demo retakes.

---

## Bob Workflow Discipline

To maximize bobcoin efficiency and maintain quality throughout development:

### Session Management
- **Export after each phase:** Save session history to [`bob_sessions/<phase-name>.md`](bob_sessions/) immediately after completion
- **Screenshot consumption:** Capture token/cost summary from IDE Task panel after each phase
- **Use `/review` proactively:** Run before completing any phase with >5 file changes

### Git Workflow
- **Auto-generated commit messages:** Use Bob's suggested commit messages (they're usually good)
- **Commit after each phase:** Keep git history aligned with phase boundaries
- **Branch strategy:** Work on `main` for hackathon speed (no feature branches needed)

### Custom Tooling
- **Create `/coach` command:** Add custom slash command in [`.bob/commands/`](.bob/commands/) to run `bob-coach` on current session during development
- **Populate `.bob/rules.md`:** Write rule-based detection conventions BEFORE starting Code mode (Phase 0)

### Quality Gates
- All code must have Python 3.10+ type hints
- Tests must pass before phase completion
- Parser must handle malformed input gracefully
- No LLM calls inside the tool (rule-based only)

---

## Risks and Mitigations

### Risk 1: Parser Fragility
**Description:** Bob's export format may vary across versions or contain edge cases not in sample fixture.

**Likelihood:** Medium  
**Impact:** High (blocks all downstream phases)

**Mitigation:**
- Write parser defensively with try/except blocks
- Add logging for unparseable sections
- Create multiple fixture files covering edge cases
- Implement "best-effort" parsing (skip malformed turns, continue)

### Risk 2: Bobcoin Budget Overrun
**Description:** Complex debugging or refactoring consumes >35 coins, leaving no buffer.

**Likelihood:** Medium  
**Impact:** Medium (may need to cut features)

**Mitigation:**
- Prioritize Phase 1-3 (core functionality)
- Make Phase 4-5 optional if budget tight
- Use `/review` command proactively to catch issues early
- Keep sessions focused (avoid conversation loops)

### Risk 3: Demo Video Timing
**Description:** Demo exceeds 3-minute limit or fails to showcase key features.

**Likelihood:** Low  
**Impact:** Medium (poor submission impression)

**Mitigation:**
- Write [`DEMO.md`](DEMO.md) script with timestamps
- Rehearse demo before recording
- Pre-generate all demo outputs (no live computation)
- Use video editing to trim pauses/errors

---

## Phase 0 File Scaffold

The following files should be created in Phase 0 to establish the project skeleton:

| File | Purpose |
|------|---------|
| [`pyproject.toml`](pyproject.toml) | Python 3.10+ project config, dependencies (click, rich, pytest), entry point |
| [`.gitignore`](.gitignore) | Ignore `__pycache__/`, `.venv/`, `*.pyc`, `.pytest_cache/`, IDE files |
| [`README.md`](README.md) | Project overview, installation, quick start, placeholder for full docs |
| [`src/bob_coach/__init__.py`](src/bob_coach/__init__.py) | Package marker, `__version__ = "0.1.0"` |
| [`src/bob_coach/cli.py`](src/bob_coach/cli.py) | Click CLI entry point, `--format` and `--output` options |
| [`tests/__init__.py`](tests/__init__.py) | Test package marker |
| [`tests/test_parser.py`](tests/test_parser.py) | Parser test stubs (to be filled in Phase 1) |
| [`AGENTS.md`](AGENTS.md) | Bob context: language, constraints, demo requirements |
| [`.bob/rules.md`](.bob/rules.md) | Bob-specific rules: no LLM calls, rule-based only, offline demo |
| [`.bob/commands/`](.bob/commands/) | Directory for custom slash commands (empty initially) |

---

## Next Steps

After approval of this plan:
1. Switch to **Code mode** for Phase 0 (skeleton scaffolding)
2. Validate skeleton with `pip install -e .` and `bob-coach --help`
3. Proceed sequentially through Phases 1-5
4. Export each phase's Bob session to [`bob_sessions/`](bob_sessions/) for recursive demo
5. Record demo video and submit to hackathon

---

*Plan created: 2026-05-01 | Hackathon deadline: 2026-05-03 | Budget: 35/40 bobcoins*
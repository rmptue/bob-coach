# Phase 2 Implementation Plan: Anti-Pattern Detectors

## Overview

Phase 2 builds rule-based detectors that identify 7 anti-patterns in Bob sessions. Each detector analyzes the parsed `Session` object and returns a list of `AntiPattern` findings with evidence and actionable recommendations.

**Budget:** 8 bobcoins
**Inputs:** Parsed `Session` objects from Phase 1
**Deliverables:** [`rules.py`](src/bob_coach/rules.py), [`detectors.py`](src/bob_coach/detectors.py), [`test_detectors.py`](tests/test_detectors.py)
**Tests:** 14-18 minimum (2 per detector + cross-cutting validation)

---

## 1. AntiPattern Data Model

### Dataclass Specification

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class AntiPattern:
    """Represents a detected anti-pattern with evidence and recommendation.
    
    All fields are required to ensure actionable, explainable findings.
    """
    name: str                                      # Anti-pattern identifier (e.g., "Missing Plan File")
    severity: Literal["low", "medium", "high", "critical"]  # Impact level
    description: str                               # What the anti-pattern is
    evidence: list[str]                            # Turn indices, excerpts, counts (machine-verifiable)
    recommendation: str                            # Specific action to fix (not vague advice)
```

### Example Detector Signature

```python
def detect_missing_plan_file(session: Session) -> list[AntiPattern]:
    """Detect Code mode sessions without plan file references.
    
    Rule: Any turn in Code mode where environment_details.workspace_dir exists
          but no PLAN.md/TODO.md/AGENTS.md in visible_files or open_tabs.
    
    Evidence: Turn indices where Code mode is active without plan files.
    
    Recommendation: "Create PLAN.md or TODO.md before starting Code mode to 
                     reduce rework risk. Use /plan command to switch modes."
    
    Args:
        session: Parsed session object from Phase 1
        
    Returns:
        List of AntiPattern findings (empty if no issues detected)
    """
    findings = []
    # Detector logic here
    return findings
```

---

## 2. Detector Logic Per Anti-Pattern

### 1. Missing Plan File (Severity: High)

**Rule (Python condition):**
```python
# For each turn where mode == "code":
#   If environment.workspace_dir is not None:
#     plan_files = ["PLAN.md", "TODO.md", "AGENTS.md", "plan.md", "todo.md"]
#     has_plan = any(
#         pf in environment.visible_files or pf in environment.open_tabs 
#         for pf in plan_files
#     )
#     if not has_plan:
#       # Flag this turn
```

**Evidence:**
- List of turn indices where Code mode is active without plan files
- Example: `["Turn 5", "Turn 7", "Turn 9"]`

**Recommendation:**
```
"Create PLAN.md or TODO.md before starting Code mode. Use 'update_todo_list' tool 
or switch to Plan mode with '/plan' to document your approach before coding."
```

**Edge Cases:**
- First turn in Code mode may not have environment_details yet → skip if environment is None
- Case-insensitive file matching (PLAN.md vs plan.md)
- Don't flag if session never enters Code mode (planning-only sessions are fine)

**False Positive Risks:**
- User may have plan in external tool (Notion, etc.) → Accept this limitation, detector is for Bob-visible plans only
- Very short Code sessions (<3 turns) may not need plan → Still flag, but note in description this is a guideline

---

### 2. Cost-Based Drift (Severity: Critical)

**Rule (Python condition):**
```python
# Single turn drift:
for turn in session.turns:
    if turn.cost_delta > 0.30:  # >$0.30 per turn
        # Flag this turn
        
# Session drift:
if session.total_cost > 1.50:  # >$1.50 total without phase break
    # Flag entire session
```

**CRITICAL DEFENSIVE HANDLING:**
Phase 1 parser produces negative cost_deltas when turns lack environment blocks (cost=0, delta = 0 - prev_cost = negative). **Must use `max(0, turn.cost_delta)` to avoid flagging negative deltas as drift.**

```python
# Correct implementation:
effective_delta = max(0.0, turn.cost_delta)
if effective_delta > 0.30:
    # Flag
```

**Evidence:**
- For single-turn drift: `["Turn 12: $0.45 cost increase"]`
- For session drift: `["Total session cost: $1.87 across 15 turns"]`

**Recommendation:**
```
"High cost suggests unfocused task or missing decomposition. Break work into 
smaller phases. Use '/review' to checkpoint progress. Consider switching to 
Plan mode to refine approach."
```

**Edge Cases:**
- Negative cost_deltas (parser artifact) → Use max(0, delta)
- First turn always has delta=0 → Skip first turn in single-turn check
- Session may have legitimate high cost (complex refactoring) → Still flag, user can judge context

**False Positive Risks:**
- Large file reads legitimately expensive → Accept this, cost is still a signal
- Demo/testing sessions may be exploratory → User can ignore finding if intentional

---

### 3. Missing /review Command (Severity: Medium)

**Rule (Python condition):**
```python
# Count file edit tools in assistant turns:
edit_tools = ["write_to_file", "apply_diff", "insert_content"]
edit_count = sum(
    1 for turn in session.turns 
    if turn.speaker == "assistant"
    for tool in turn.tool_uses
    if tool.name in edit_tools
)

# Check for /review in user turns:
has_review = "review" in session.slash_commands

if edit_count > 5 and not has_review:
    # Flag session
```

**Evidence:**
- `["6 file edits detected (write_to_file: 3, apply_diff: 2, insert_content: 1)", "No /review command found in user messages"]`

**Recommendation:**
```
"Run '/review' after making >5 file changes to catch bugs early. Code review 
reduces rework and improves quality."
```

**Edge Cases:**
- Session may have edits but no user turns yet (assistant-only) → Still flag if >5 edits
- User may have reviewed manually without /review command → Accept limitation, detector is for explicit command usage

**False Positive Risks:**
- Trivial edits (typo fixes) may not need review → Still flag, threshold is reasonable guideline
- User may review in separate session → Detector is per-session, this is expected

---

### 4. Tool Use Errors (Severity: High)

**Rule (Python condition):**
```python
# For each turn:
#   If turn.has_error == True:
#     Check if previous turn (turn.index - 1) was assistant with tool_uses
#     If yes, flag as tool use error
```

**Evidence:**
- `["Turn 2: [ERROR] after attempt_completion in Turn 1", "Turn 8: [ERROR] following write_to_file"]`

**Recommendation:**
```
"Tool errors indicate unclear requirements or incorrect parameters. Review tool 
documentation and task context before retrying. Use 'ask_followup_question' if 
requirements are ambiguous."
```

**Edge Cases:**
- Error in first turn (no previous turn) → Flag as general error, not tool-specific
- Multiple consecutive errors → Flag each separately with turn indices
- Error may be user-side (invalid input) → Still flag, detector doesn't distinguish error source

**False Positive Risks:**
- System errors unrelated to tool use → May flag incorrectly, but errors are always worth investigating
- Error message may be informational, not failure → Parser sets has_error=True for any [ERROR], accept this

---

### 5. Conversation Loops (Severity: Medium)

**Rule (Python condition):**
```python
# Track consecutive ask_followup_question uses:
consecutive_asks = 0
max_consecutive = 0
loop_turns = []

for turn in session.turns:
    if turn.speaker == "assistant":
        has_ask = any(tool.name == "ask_followup_question" for tool in turn.tool_uses)
        if has_ask:
            consecutive_asks += 1
            if consecutive_asks > max_consecutive:
                max_consecutive = consecutive_asks
                loop_turns.append(turn.index)
        else:
            consecutive_asks = 0

if max_consecutive > 3:
    # Flag session
```

**Evidence:**
- `["4 consecutive ask_followup_question uses in turns 5-8"]`

**Recommendation:**
```
"Excessive back-and-forth suggests unclear task specification. Provide more 
context upfront or use 'read_file' to gather information independently before 
asking questions."
```

**Edge Cases:**
- Legitimate clarification sequences (complex requirements) → Still flag, threshold is reasonable
- User may not respond to questions → Detector counts asks, not responses

**False Positive Risks:**
- Interactive design sessions may need many questions → User can judge if appropriate for context
- Questions may be about different topics → Detector doesn't analyze question content, only counts

---

### 6. Mode Thrashing (Severity: Low)

**Rule (Python condition):**
```python
# Count mode transitions in sliding 10-turn window:
for i in range(len(session.turns) - 9):  # -9 to get 10-turn windows
    window_turns = session.turns[i:i+10]
    transitions_in_window = [
        t for t in session.mode_transitions 
        if i <= t.turn_index < i+10
    ]
    if len(transitions_in_window) > 4:
        # Flag this window
```

**Evidence:**
- `["5 mode switches in turns 3-12: plan→code→plan→ask→code→plan"]`

**Recommendation:**
```
"Frequent mode changes suggest task scope uncertainty. Spend more time in Plan 
mode to clarify approach before switching to Code or Ask modes."
```

**Edge Cases:**
- Short sessions (<10 turns) → Check entire session, not windowed
- Legitimate workflow may involve many switches (e.g., iterative debugging) → Still flag, user can judge

**False Positive Risks:**
- Exploratory sessions may need mode flexibility → Low severity reflects this is a soft guideline
- Mode switches may be intentional workflow → User can ignore if appropriate

---

### 7. Plan-Mode Write Violation (Severity: Medium)

**Rule (Python condition):**
```python
# For each turn where mode == "plan":
#   For each tool_use in turn.tool_uses:
#     if tool_use.name in ["write_to_file", "apply_diff"]:
#       Check tool_use.parameters["path"] (if present)
#       if not path.endswith((".md", ".markdown", ".txt")):
#         # Flag this turn
#
# Alternative: Check if turn.has_error and mode == "plan"
#   Error message likely contains "protected configuration file" or mode restriction
```

**Evidence:**
- `["Turn 7: Attempted write_to_file for 'src/main.py' in Plan mode", "Turn 7: [ERROR] protected configuration file"]`

**Recommendation:**
```
"Switch to Code mode before editing non-markdown files. Use 'switch_mode' tool 
or '/code' command to transition modes."
```

**Edge Cases:**
- Plan mode CAN write markdown files → Only flag non-markdown writes
- Error may not explicitly mention mode restriction → Check both tool use AND has_error
- Tool may not have path parameter extracted → Skip if path is missing

**False Positive Risks:**
- Parser may not extract path parameter correctly → May miss some violations, acceptable
- User may intentionally test mode restrictions → Rare, still worth flagging

---

## 3. Rule Definitions Structure

### Decision: Python Constants in rules.py

**Rationale:**
- Thresholds need to be **readable** for `/coach` command in Phase 4
- Python constants are easier to import and reference than markdown
- Allows programmatic access (e.g., `COST_DRIFT_THRESHOLD_PER_TURN`)
- Can add docstrings explaining rationale for each threshold

**Structure:**

```python
# src/bob_coach/rules.py

"""Anti-pattern detection rules and thresholds.

All thresholds are configurable constants. Adjust based on your team's
Bob usage patterns and quality standards.
"""

# Cost-Based Drift
COST_DRIFT_THRESHOLD_PER_TURN = 0.30  # dollars
COST_DRIFT_THRESHOLD_SESSION = 1.50   # dollars

# Missing /review Command
FILE_EDIT_THRESHOLD = 5  # number of edits before review recommended

# Conversation Loops
CONSECUTIVE_ASK_THRESHOLD = 3  # number of consecutive ask_followup_question uses

# Mode Thrashing
MODE_SWITCH_THRESHOLD = 4      # switches per window
MODE_SWITCH_WINDOW_SIZE = 10   # turns

# Plan File Detection
PLAN_FILE_NAMES = [
    "PLAN.md", "TODO.md", "AGENTS.md",
    "plan.md", "todo.md", "agents.md",
    "PLAN.txt", "TODO.txt"
]

# File Edit Tools
FILE_EDIT_TOOLS = ["write_to_file", "apply_diff", "insert_content"]

# Plan-Mode Write Violation
MARKDOWN_EXTENSIONS = [".md", ".markdown", ".txt"]
```

**Why not markdown?**
- Markdown is for documentation, not configuration
- Python constants are type-safe and IDE-friendly
- Phase 4's `/coach` command can import and display these values programmatically

---

## 4. Defensive Considerations

### Negative Cost Deltas (Critical)

**Problem:** Phase 1 parser produces negative cost_deltas when:
- Turn N has environment with cost=$0.50
- Turn N+1 has NO environment block (cost defaults to 0.0)
- Delta = 0.0 - 0.50 = -0.50

**Solution:**
```python
# In detect_cost_drift():
effective_delta = max(0.0, turn.cost_delta)
if effective_delta > COST_DRIFT_THRESHOLD_PER_TURN:
    # Flag
```

**Why this works:**
- Negative deltas are parser artifacts, not real cost decreases
- `max(0, delta)` treats missing cost data as "no change" rather than "negative cost"
- Preserves detection of real high-cost turns

### Missing Environment Data

**Problem:** Not all turns have environment_details (especially user turns).

**Solution:**
- Check `if turn.environment is None` before accessing environment fields
- Use `turn.mode` (copied from environment during parsing) instead of `turn.environment.mode_slug`
- Gracefully skip turns with missing data rather than crashing

### Empty Tool Parameters

**Problem:** Parser may not extract all tool parameters (complex XML, nested content).

**Solution:**
- Check `if "path" in tool.parameters` before accessing
- Use `.get("path", "")` with default values
- Don't fail detection if parameter is missing, just skip that tool use

### Case Sensitivity

**Problem:** File names may vary in case (PLAN.md vs plan.md).

**Solution:**
- Convert to lowercase for comparison: `filename.lower() in [pf.lower() for pf in PLAN_FILE_NAMES]`
- Or use case-insensitive matching in rules.py constants

---

## 5. Test Plan

### Test Structure

```python
# tests/test_detectors.py

import pytest
from bob_coach.parser import parse_session
from bob_coach.detectors import (
    detect_missing_plan_file,
    detect_cost_drift,
    detect_missing_review,
    detect_tool_errors,
    detect_conversation_loops,
    detect_mode_thrashing,
    detect_plan_mode_violations,
)
from bob_coach.models import AntiPattern

@pytest.fixture
def sample_01_session():
    """Simple 2-turn session (fixture)."""
    return parse_session(Path("fixtures/sample-session-01.md"))

@pytest.fixture
def sample_02_session():
    """Complex planning session (fixture)."""
    return parse_session(Path("fixtures/sample-session-02.md"))
```

### Test Cases (10-14 tests)

#### 1. test_missing_plan_file_detected (sample-02)
```python
def test_missing_plan_file_detected(sample_02_session):
    findings = detect_missing_plan_file(sample_02_session)
    # sample-02 is Plan mode only, should NOT flag
    assert len(findings) == 0
```

#### 2. test_missing_plan_file_in_code_mode
```python
def test_missing_plan_file_in_code_mode():
    # Create mock session with Code mode, no plan files
    session = Session(turns=[
        Turn(index=0, speaker="assistant", mode="code", 
             environment=EnvironmentDetails(
                 mode_slug="code",
                 visible_files=["src/main.py"],
                 open_tabs=["src/main.py"]
             ), ...)
    ])
    findings = detect_missing_plan_file(session)
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert "PLAN.md" in findings[0].recommendation
```

#### 3. test_cost_drift_single_turn (sample-02)
```python
def test_cost_drift_single_turn(sample_02_session):
    findings = detect_cost_drift(sample_02_session)
    # sample-02 has turn with $0.31 cost (line 1115)
    assert len(findings) >= 1
    assert any("Turn" in ev for f in findings for ev in f.evidence)
```

#### 4. test_cost_drift_negative_delta_ignored
```python
def test_cost_drift_negative_delta_ignored():
    session = Session(turns=[
        Turn(index=0, cost_delta=0.0, cumulative_cost=0.50, ...),
        Turn(index=1, cost_delta=-0.50, cumulative_cost=0.0, ...),  # Negative
    ])
    findings = detect_cost_drift(session)
    # Should NOT flag negative delta
    assert len(findings) == 0
```

#### 5. test_missing_review_detected
```python
def test_missing_review_detected():
    session = Session(
        turns=[
            Turn(index=i, speaker="assistant", 
                 tool_uses=[ToolUse(name="write_to_file", ...)], ...)
            for i in range(6)  # 6 file edits
        ],
        slash_commands=[],  # No /review
        file_edits=6
    )
    findings = detect_missing_review(session)
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert "6 file edits" in findings[0].evidence[0]
```

#### 6. test_tool_errors_detected (sample-01)
```python
def test_tool_errors_detected(sample_01_session):
    findings = detect_tool_errors(sample_01_session)
    # sample-01 has [ERROR] in turn 1 after tool use in turn 0
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert "Turn 1" in findings[0].evidence[0]
```

#### 7. test_conversation_loops_detected
```python
def test_conversation_loops_detected():
    session = Session(turns=[
        Turn(index=i, speaker="assistant",
             tool_uses=[ToolUse(name="ask_followup_question", ...)], ...)
        for i in range(5)  # 5 consecutive asks
    ])
    findings = detect_conversation_loops(session)
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert "consecutive" in findings[0].description.lower()
```

#### 8. test_mode_thrashing_detected (sample-02)
```python
def test_mode_thrashing_detected(sample_02_session):
    findings = detect_mode_thrashing(sample_02_session)
    # sample-02 is Plan mode only, no thrashing
    assert len(findings) == 0
```

#### 9. test_plan_mode_violation_high_confidence
```python
def test_plan_mode_violation_high_confidence():
    # Both signals present: tool_use + error
    session = Session(turns=[
        Turn(index=0, speaker="assistant", mode="plan",
             tool_uses=[ToolUse(name="write_to_file",
                               parameters={"path": "src/main.py"}, ...)],
             has_error=True, ...)
    ])
    findings = detect_plan_mode_violations(session)
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert "write_to_file('src/main.py')" in findings[0].evidence[0]
    assert "[ERROR]" in findings[0].evidence[0]
```

#### 10. test_plan_mode_violation_tool_only
```python
def test_plan_mode_violation_tool_only():
    # Only tool signal, no error
    session = Session(turns=[
        Turn(index=0, speaker="assistant", mode="plan",
             tool_uses=[ToolUse(name="write_to_file",
                               parameters={"path": "src/main.py"}, ...)],
             has_error=False, ...)
    ])
    findings = detect_plan_mode_violations(session)
    assert len(findings) == 1
    assert "Possible violation" in findings[0].evidence[0]
```

#### 11. test_plan_mode_violation_error_only
```python
def test_plan_mode_violation_error_only():
    # Only error signal, path not extracted
    session = Session(turns=[
        Turn(index=0, speaker="assistant", mode="plan",
             tool_uses=[ToolUse(name="write_to_file",
                               parameters={}, ...)],  # No path
             has_error=True, ...)
    ])
    findings = detect_plan_mode_violations(session)
    assert len(findings) == 1
    assert "Possible violation" in findings[0].evidence[0]
    assert "path not extracted" in findings[0].evidence[0]
```

#### 12. test_all_detectors_return_list
```python
def test_all_detectors_return_list(sample_01_session):
    # Ensure all detectors return list[AntiPattern], not None
    detectors = [
        detect_missing_plan_file,
        detect_cost_drift,
        detect_missing_review,
        detect_tool_errors,
        detect_conversation_loops,
        detect_mode_thrashing,
        detect_plan_mode_violations,
    ]
    for detector in detectors:
        result = detector(sample_01_session)
        assert isinstance(result, list)
        assert all(isinstance(ap, AntiPattern) for ap in result)
```

#### 13. test_evidence_non_empty
```python
def test_evidence_non_empty(sample_01_session):
    # All findings must have non-empty evidence
    all_findings = []
    for detector in [detect_tool_errors, ...]:  # All detectors
        all_findings.extend(detector(sample_01_session))
    
    for finding in all_findings:
        assert len(finding.evidence) > 0
        assert all(isinstance(ev, str) and len(ev) > 0 for ev in finding.evidence)
```

#### 12. test_recommendation_actionable
```python
def test_recommendation_actionable(sample_01_session):
    # All recommendations must be non-empty strings
    all_findings = []
    for detector in [detect_tool_errors, ...]:
        all_findings.extend(detector(sample_01_session))
    
    for finding in all_findings:
        assert isinstance(finding.recommendation, str)
        assert len(finding.recommendation) > 20  # Substantive recommendation
```

#### 13. test_severity_valid
```python
def test_severity_valid(sample_01_session):
    valid_severities = {"low", "medium", "high", "critical"}
    all_findings = []
    for detector in [detect_tool_errors, ...]:
        all_findings.extend(detector(sample_01_session))
    
    for finding in all_findings:
        assert finding.severity in valid_severities
```

#### 14. test_no_false_positives_on_clean_session
```python
def test_no_false_positives_on_clean_session():
    # Create ideal session: Plan mode, low cost, no errors, has /review
    session = Session(
        turns=[
            Turn(index=0, speaker="user", mode="plan", cost_delta=0.01, ...),
            Turn(index=1, speaker="assistant", mode="plan", cost_delta=0.02, ...),
        ],
        total_cost=0.03,
        mode_transitions=[],
        slash_commands=["review"],
        file_edits=2
    )
    
    # No detector should flag this session
    all_findings = []
    for detector in [detect_missing_plan_file, ...]:
        all_findings.extend(detector(session))
    
    assert len(all_findings) == 0
```

### Test Coverage Goals

- **Happy path:** Both fixtures analyzed without crashes
- **Edge cases:** Negative deltas, missing environment, empty parameters
- **Validation:** All findings have valid severity, non-empty evidence, actionable recommendations
- **False negatives:** Clean session produces zero findings

---

## 6. Bobcoin Estimate Breakdown

**Total Phase 2 Budget:** 8 coins

| Task | Estimated Coins | Rationale |
|------|-----------------|-----------|
| **AntiPattern dataclass + rules.py** | 1.0 | Simple dataclass, threshold constants, docstrings |
| **detectors.py (7 detectors)** | 4.0 | Core logic, ~50 lines per detector, defensive coding |
| **test_detectors.py** | 2.0 | 10-14 tests, mock sessions, assertions |
| **Debugging + edge cases** | 1.0 | Fix negative delta handling, test failures, refinement |
| **Total** | **8.0** | Matches Phase 2 budget exactly |

### Coin-Saving Strategies

- Write all detectors in single Code session (shared context)
- Use `/review` before finalizing to catch logic errors early
- Test incrementally: run pytest after each 2-3 detectors
- Reuse helper functions (e.g., `_is_plan_file()`, `_count_edit_tools()`)

---

## 7. Three Concrete Risks

### Risk 1: False Positive Rate Too High to Be Useful

**Concrete Issue:** Detectors flag legitimate workflows as anti-patterns (e.g., flagging exploratory sessions as "mode thrashing", flagging complex refactoring as "cost drift").

**Impact:** Users ignore all findings, tool loses credibility. Demo shows too many false alarms.

**Mitigation:**
- Set conservative thresholds (>4 switches, >$0.30/turn, >5 edits)
- Use severity levels to distinguish critical vs. advisory findings
- Test against both fixtures AND Bob Coach's own Phase 0/1 sessions (real-world validation)
- Add "Context" field to AntiPattern (future enhancement) explaining when to ignore
- Document in README: "Findings are guidelines, not strict rules"

### Risk 2: Negative Cost Delta Handling Breaks Drift Detection

**Concrete Issue:** If `max(0, delta)` logic is wrong or missing, detector either:
- Flags every turn with missing environment as drift (false positives)
- Misses real high-cost turns because negative deltas corrupt cumulative tracking

**Impact:** Cost-based drift detector (critical severity) is unreliable, undermining core value prop.

**Mitigation:**
- Write dedicated test: `test_cost_drift_negative_delta_ignored()` (see test plan)
- Manually verify against sample-02 (has $0.31 turn at line 1115)
- Add logging/debug mode to show cost_delta values during detection
- Document assumption in rules.py: "Negative deltas are parser artifacts, treated as 0"

### Risk 3: Plan-Mode Violation Detector Misses Cases Due to Parameter Extraction

**Concrete Issue:** Phase 1 parser may not extract `path` parameter from `write_to_file` tool uses (complex XML, nested content). Detector checks `tool.parameters["path"]` and crashes or skips.

**Impact:** Plan-mode violations go undetected, reducing detector coverage.

**Mitigation:**
- Use defensive access: `tool.parameters.get("path", "")` with default
- Fall back to `turn.has_error` check (mode violations surface as [ERROR])
- Test specifically with mock session containing write_to_file without path parameter
- Accept limitation: If parser doesn't extract path, detector can't check extension
- Document in AGENTS.md: "Plan-mode detector requires path parameter extraction"

---

## Implementation Checklist

After this plan is approved, Code mode will execute:

- [ ] Add `AntiPattern` dataclass to [`src/bob_coach/models.py`](src/bob_coach/models.py)
- [ ] Create [`src/bob_coach/rules.py`](src/bob_coach/rules.py) with threshold constants
- [ ] Create [`src/bob_coach/detectors.py`](src/bob_coach/detectors.py) with 7 detector functions:
  - [ ] `detect_missing_plan_file(session: Session) -> list[AntiPattern]`
  - [ ] `detect_cost_drift(session: Session) -> list[AntiPattern]`
  - [ ] `detect_missing_review(session: Session) -> list[AntiPattern]`
  - [ ] `detect_tool_errors(session: Session) -> list[AntiPattern]`
  - [ ] `detect_conversation_loops(session: Session) -> list[AntiPattern]`
  - [ ] `detect_mode_thrashing(session: Session) -> list[AntiPattern]`
  - [ ] `detect_plan_mode_violations(session: Session) -> list[AntiPattern]`
- [ ] Create [`tests/test_detectors.py`](tests/test_detectors.py) with 10-14 test functions
- [ ] Run `pytest tests/test_detectors.py -v` — all tests pass
- [ ] Verify both fixtures produce expected findings (manual inspection)
- [ ] Export this Phase 2 session to [`bob_sessions/phase-2.md`](bob_sessions/phase-2.md)

---

## Success Criteria

Phase 2 is complete when:

- ✅ All 7 detectors implemented and return `list[AntiPattern]`
- ✅ All findings have non-empty evidence and actionable recommendations
- ✅ Negative cost deltas handled correctly (no false positives)
- ✅ All 10-14 tests pass
- ✅ Both fixtures analyzed without crashes
- ✅ Zero false positives on "clean" mock session
- ✅ Bobcoin spend ≤8 coins for Phase 2
- ✅ Code has type hints on all functions

---

*Phase 2 Plan | Budget: 8 coins | Detectors: 7 | Tests: 10-14 | Risk Level: Medium*
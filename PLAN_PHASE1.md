# Phase 1 Implementation Plan: Parser

## Overview

Phase 1 builds the core parsing engine that transforms Bob's exported session markdown into structured Python objects. This is the foundation for all downstream analysis (anti-pattern detection, metrics, reports).

**Budget:** 8 bobcoins  
**Inputs:** [`fixtures/sample-session-01.md`](fixtures/sample-session-01.md) (119 lines, simple), [`fixtures/sample-session-02.md`](fixtures/sample-session-02.md) (1,248 lines, complex)  
**Deliverables:** [`models.py`](src/bob_coach/models.py), [`parser.py`](src/bob_coach/parser.py), [`test_parser.py`](tests/test_parser.py)

---

## 1. Data Models

All dataclasses use Python 3.10+ type hints (`list[str]`, `dict[str, int]`, `X | None`).

### Core Models

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

@dataclass
class ToolUse:
    """Represents a single tool invocation by the assistant."""
    name: str                          # Tool name (e.g., "read_file", "attempt_completion")
    parameters: dict[str, str]         # Extracted parameter key-value pairs
    turn_index: int                    # Which turn this tool was used in
    
    # Why: Phase 2 needs tool names for detecting missing /review, Phase 3 counts deliverables

@dataclass
class ModeTransition:
    """Tracks when Bob switches between modes (plan → code, etc.)."""
    from_mode: str | None              # Previous mode slug (None if first turn)
    to_mode: str                       # New mode slug (e.g., "plan", "code", "ask")
    to_mode_name: str                  # Display name (e.g., "📝 Plan")
    turn_index: int                    # Turn where transition occurred
    
    # Why: Phase 2 detects mode thrashing (>4 switches in <10 turns)

@dataclass
class EnvironmentDetails:
    """Metadata from environment_details blocks."""
    timestamp: datetime | None         # Parsed from "# Current Time" ISO 8601
    cost: float                        # Parsed from "# Current Cost" (e.g., "$0.03" → 0.03)
    mode_slug: str | None              # From <slug>plan</slug>
    mode_name: str | None              # From <name>📝 Plan</name>
    workspace_dir: str | None          # From "# Current Workspace Directory (...)"
    visible_files: list[str]           # From "# VSCode Visible Files" section
    open_tabs: list[str]               # From "# VSCode Open Tabs" section
    
    # Why: Phase 2 needs workspace_dir to detect missing plan files, Phase 3 uses timestamps

@dataclass
class Turn:
    """A single conversation turn (user or assistant message)."""
    index: int                         # 0-based turn number in session
    speaker: Literal["user", "assistant"]
    content: str                       # Full message content (excluding environment_details)
    mode: str | None                   # Current mode slug at this turn
    cost_delta: float                  # Cost increase from previous turn (0.0 for first turn)
    cumulative_cost: float             # Total session cost at this turn
    timestamp: datetime | None         # When this turn occurred
    tool_uses: list[ToolUse]           # Tools invoked in this turn (empty for user turns)
    has_error: bool                    # True if turn contains "[ERROR]" message
    environment: EnvironmentDetails | None  # Parsed environment_details (None if missing)
    
    # Why: Phase 2 analyzes turns for anti-patterns, Phase 3 calculates metrics

@dataclass
class Session:
    """Complete parsed session with all turns and metadata."""
    turns: list[Turn]                  # All conversation turns in order
    total_cost: float                  # Final cumulative cost
    mode_transitions: list[ModeTransition]  # All mode switches
    workspace: str | None              # Workspace directory (from first turn's environment)
    file_edits: int                    # Count of write_to_file/apply_diff/insert_content uses
    slash_commands: list[str]          # Extracted slash commands from user turns (e.g., "/review")
    
    # Why: Phase 2 needs file_edits for missing /review detection, Phase 3 uses all fields
```

### Design Rationale

- **Minimal fields:** Only include data needed by Phase 2 (detectors) or Phase 3 (metrics). Don't parse data we won't use.
- **Flat structure:** Avoid deep nesting. `Turn` contains `EnvironmentDetails` directly, not nested sub-objects.
- **Computed fields:** `Session.file_edits` and `Session.slash_commands` are computed during parsing to avoid re-scanning in Phase 2.
- **Graceful degradation:** All optional fields use `| None` so parser can skip malformed sections without failing.

---

## 2. Parsing Strategy

### Approach: Line-by-Line State Machine

**Choice:** Hybrid state machine + regex extraction.

**Rationale:**
- Bob exports are **semi-structured** — clear delimiters (`---`, `**User:**`, `**Assistant:**`) but variable content within turns
- State machine handles turn boundaries and speaker tracking
- Regex extracts structured elements (XML tags, cost fields, timestamps)
- Standard library only (no markdown parsers, no XML parsers beyond regex)

### State Machine States

```python
class ParserState(Enum):
    SEEKING_TURN = 1        # Looking for **User:** or **Assistant:**
    IN_USER_TURN = 2        # Accumulating user message content
    IN_ASSISTANT_TURN = 3   # Accumulating assistant message content
    IN_ENVIRONMENT = 4      # Inside <environment_details> block
```

### Parsing Flow

```
1. Initialize: state = SEEKING_TURN, current_turn = None, turns = []

2. For each line in markdown:
   a. If line == "---": 
      - Finalize current_turn (if any), append to turns
      - state = SEEKING_TURN
   
   b. If line == "**User:**":
      - state = IN_USER_TURN
      - current_turn = Turn(speaker="user", ...)
   
   c. If line == "**Assistant:**":
      - state = IN_ASSISTANT_TURN
      - current_turn = Turn(speaker="assistant", ...)
   
   d. If state == IN_USER_TURN or IN_ASSISTANT_TURN:
      - If line starts with "<environment_details>":
        - state = IN_ENVIRONMENT
        - Start accumulating environment block
      - Else if line contains tool XML (e.g., "<read_file>"):
        - Extract tool name and parameters using regex
        - Add to current_turn.tool_uses
      - Else:
        - Append line to current_turn.content
   
   e. If state == IN_ENVIRONMENT:
      - If line == "</environment_details>":
        - Parse accumulated environment block
        - Extract timestamp, cost, mode, workspace, files
        - Attach to current_turn.environment
        - state = previous_state (IN_USER_TURN or IN_ASSISTANT_TURN)
      - Else:
        - Accumulate line for environment parsing

3. After all lines: finalize last turn (if any)

4. Post-process:
   - Calculate cost_delta for each turn
   - Extract mode_transitions from turn sequence
   - Count file_edits (write_to_file, apply_diff, insert_content)
   - Extract slash_commands from user turn content (regex: r'/\w+')
```

### Key Regex Patterns

```python
# Turn delimiters
TURN_DELIMITER = r'^---$'
USER_MARKER = r'^\*\*User:\*\*$'
ASSISTANT_MARKER = r'^\*\*Assistant:\*\*$'

# Environment fields
COST_PATTERN = r'# Current Cost\s*\n\$(\d+\.\d+)'
TIMESTAMP_PATTERN = r'Current time in ISO 8601 UTC format: (.+)'
MODE_SLUG_PATTERN = r'<slug>(\w+)</slug>'
MODE_NAME_PATTERN = r'<name>(.+?)</name>'
WORKSPACE_PATTERN = r'# Current Workspace Directory \((.+?)\)'

# Tool use (generic XML tag extraction)
TOOL_PATTERN = r'<(\w+)>\s*\n(.*?)\n</\1>'  # Captures tool name and content
PARAM_PATTERN = r'<(\w+)>(.*?)</\1>'        # Captures parameter name and value

# Slash commands
SLASH_CMD_PATTERN = r'/(\w+)'

# Error detection
ERROR_PATTERN = r'\[ERROR\]'
```

### Why This Approach?

- **Robust:** State machine handles missing delimiters gracefully (skip malformed turns)
- **Efficient:** Single pass through file, no backtracking
- **Testable:** Each state transition is a discrete unit test
- **Standard library:** No external dependencies (regex is stdlib)
- **Handles edge cases:** See section 3 below

---

## 3. Edge Cases

Walking through both fixtures, here are the edge cases the parser MUST handle:

### From sample-session-01.md (119 lines)

1. **[ERROR] reminder messages** (lines 51-78)
   - User turn contains system-generated error message
   - Must NOT treat `[ERROR]` as speaker delimiter
   - Solution: Only recognize `**User:**` and `**Assistant:**` as turn markers
   - Set `turn.has_error = True` when `[ERROR]` found in content

2. **Tool use in attempt_completion** (lines 107-118)
   - `<attempt_completion>` contains `<result>` parameter with multi-line content
   - Solution: Regex with `DOTALL` flag to capture multi-line parameters
   - Extract tool name = "attempt_completion", parameters = {"result": "..."}

3. **Cost delta calculation** (lines 18, 91)
   - Turn 1: $0.00 → cost_delta = 0.0
   - Turn 2: $0.03 → cost_delta = 0.03
   - Solution: Track previous_cost, compute delta = current - previous

4. **Empty environment sections**
   - "# VSCode Visible Files" followed by blank line (no files listed)
   - Solution: Return empty list `[]` for visible_files, not None

### From sample-session-02.md (1,248 lines)

5. **Embedded XML in user content** (lines 3-37)
   - User's `<task>` block contains instructions mentioning XML tags
   - Must NOT parse these as tool uses (they're in user content, not assistant)
   - Solution: Only extract tools from assistant turns

6. **Nested code blocks vs tool XML** (throughout)
   - Assistant content may contain markdown code blocks with XML examples
   - Tool XML is at root level of turn content, not inside ``` blocks
   - Solution: Track if we're inside a code block (``` delimiter), skip tool extraction there

7. **update_todo_list special handling** (lines 241-248)
   - Tool use with `<todos>` parameter containing markdown checklist
   - Checklist has `[ ]`, `[x]`, `[-]` markers that look like XML
   - Solution: Extract full `<todos>...</todos>` content as single string parameter

8. **Multiple tool uses in one turn** (not in fixtures, but possible)
   - Assistant could use multiple tools sequentially
   - Solution: `turn.tool_uses` is a list, append each detected tool

9. **Mode transitions without explicit tag** (lines 69-80)
   - First turn may not have mode tags in environment_details
   - Solution: `mode_slug` and `mode_name` are optional (`| None`)

10. **Cumulative cost tracking across turns** (lines 50, 268, 1208)
    - Cost increases: $0.00 → $0.03 → $0.07 → $0.37
    - Must track cumulative cost per turn for Phase 2 drift detection
    - Solution: Store both `cost_delta` and `cumulative_cost` in Turn

11. **Workspace directory variations** (lines 29, 61)
    - Format: `# Current Workspace Directory (path) Files`
    - Path may contain spaces, special chars (e.g., `C:/Users/Joshua/Desktop`)
    - Solution: Regex captures everything inside parentheses

12. **Malformed/truncated exports**
    - Export may end mid-turn (no final `---`)
    - Solution: Finalize last turn even if no delimiter found

13. **Empty turns** (not in fixtures, but defensive)
    - Turn with only `**User:**` and `---`, no content
    - Solution: Create Turn with empty content string, don't skip

14. **Nested attempt_completion blocks** (not in fixtures, but possible)
    - Assistant might quote previous attempt_completion in explanation
    - Solution: Only extract tool XML at root level (not inside quoted blocks)
    - Implementation: Track quote depth with `>` prefix detection

15. **Variable environment_details content** (lines 6-32, 38-65)
    - Some fields present in one turn, missing in another
    - "# VSCode Open Tabs" may list files or be empty
    - Solution: All EnvironmentDetails fields are optional, parse what's present

---

## 4. Test Plan

### Test Structure

```python
# tests/test_parser.py

import pytest
from pathlib import Path
from bob_coach.parser import parse_session
from bob_coach.models import Session, Turn

@pytest.fixture
def fixture_dir():
    return Path(__file__).parent.parent / "fixtures"

@pytest.fixture
def sample_01(fixture_dir):
    return fixture_dir / "sample-session-01.md"

@pytest.fixture
def sample_02(fixture_dir):
    return fixture_dir / "sample-session-02.md"
```

### Test Cases (12 focused tests)

1. **test_parse_simple_session** (sample-01)
   - Assert: 2 turns parsed (1 user, 1 assistant)
   - Assert: Turn 0 speaker == "user", Turn 1 speaker == "assistant"
   - Assert: Total cost == 0.03

2. **test_cost_tracking** (sample-01)
   - Assert: Turn 0 cost_delta == 0.0, cumulative_cost == 0.0
   - Assert: Turn 1 cost_delta == 0.03, cumulative_cost == 0.03

3. **test_error_detection** (sample-01)
   - Assert: Turn 1 (user turn with [ERROR]) has_error == True
   - Assert: Turn 0 has_error == False

4. **test_tool_extraction** (sample-01)
   - Assert: Turn 0 (assistant) has 1 tool_use
   - Assert: tool_use.name == "attempt_completion"
   - Assert: "result" in tool_use.parameters

5. **test_environment_parsing** (sample-01)
   - Assert: Turn 0 environment.timestamp is datetime object
   - Assert: Turn 0 environment.mode_slug == "plan"
   - Assert: Turn 0 environment.workspace_dir contains "Desktop"

6. **test_complex_session** (sample-02)
   - Assert: >10 turns parsed (exact count from fixture)
   - Assert: Multiple mode transitions detected
   - Assert: Final cost matches last environment_details cost

7. **test_mode_transitions** (sample-02)
   - Assert: mode_transitions list is not empty
   - Assert: First transition has from_mode == None
   - Assert: Transition turn_index matches actual mode change

8. **test_slash_command_extraction** (sample-02)
   - Assert: "/review" not in sample-02 (it's a planning session)
   - Create mock session with "/review" in user turn
   - Assert: session.slash_commands contains "review"

9. **test_file_edit_counting** (sample-02)
   - Assert: session.file_edits > 0 (sample-02 has write_to_file uses)
   - Count actual write_to_file/apply_diff in fixture manually
   - Assert: parsed count matches manual count

10. **test_malformed_input_graceful**
    - Create fixture with missing `---` delimiter
    - Assert: Parser returns partial Session, doesn't crash
    - Assert: Parsed turns up to malformed section

11. **test_empty_environment_fields** (sample-01)
    - Assert: Turn 0 environment.visible_files == []
    - Assert: Turn 0 environment.open_tabs == []

12. **test_multi_line_tool_parameters** (sample-01)
    - Assert: attempt_completion result parameter contains newlines
    - Assert: Full multi-line content captured, not truncated

### Test Coverage Goals

- **Happy path:** Both fixtures parse completely
- **Edge cases:** Error messages, empty fields, malformed input
- **Computed fields:** Cost deltas, mode transitions, file edits, slash commands
- **Graceful degradation:** Missing fields don't crash parser

---

## 5. Bobcoin Estimate Breakdown

**Total Phase 1 Budget:** 8 coins

| Task | Estimated Coins | Rationale |
|------|-----------------|-----------|
| **models.py** | 1.5 | Define 5 dataclasses with type hints, docstrings. Straightforward, no logic. |
| **parser.py (core logic)** | 3.5 | State machine, regex extraction, post-processing. Most complex part. |
| **parser.py (edge cases)** | 1.0 | Handle malformed input, nested XML, code blocks. Defensive coding. |
| **test_parser.py** | 1.5 | Write 12 tests, create pytest fixtures. Tests are simple assertions. |
| **Debugging buffer** | 0.5 | Fix regex bugs, handle unexpected fixture variations. |
| **Total** | **8.0** | Matches Phase 1 budget exactly. |

### Coin-Saving Strategies

- Write models.py and parser.py in same Code session (context accumulates)
- Use `/review` before finalizing to catch bugs early (avoid rework)
- Test incrementally: run pytest after each major function (fail fast)
- Reuse regex patterns across functions (DRY principle)

---

## 6. Three Risks

### Risk 1: Regex Brittleness on Real Exports

**Concrete Issue:** Bob's export format may vary across versions or contain edge cases not in sample-session-02.md (e.g., different environment_details fields, new tool names, Unicode in content).

**Impact:** Parser fails on real session exports during demo, breaking Phase 4.

**Mitigation:**
- Write parser defensively: try/except around regex matches, log warnings for unparseable sections
- Test against BOTH fixtures (simple + complex) before proceeding to Phase 2
- Add `parse_best_effort()` mode that skips malformed turns rather than crashing
- Export Bob Coach's own Phase 0 session NOW and add as third fixture (real-world validation)

### Risk 2: Cost Delta Calculation Off-by-One

**Concrete Issue:** If environment_details cost field is missing in some turns, cost_delta calculation breaks (e.g., Turn 5 has no cost, Turn 6 shows $0.50 — is delta $0.50 or unknown?).

**Impact:** Phase 2 "Cost-Based Drift" detector produces false positives/negatives.

**Mitigation:**
- Track `last_known_cost` separately from `turn.cumulative_cost`
- If cost missing, set `cost_delta = 0.0` and `cumulative_cost = last_known_cost` (carry forward)
- Add test case: fixture with missing cost in middle turn
- Document assumption: cost always increases monotonically (never decreases)

### Risk 3: Tool Parameter Extraction Fails on Complex XML

**Concrete Issue:** Tool parameters may contain nested XML-like content (e.g., `<diff>` block inside `<apply_diff>` with `<<<<<<<` merge markers that look like XML tags).

**Impact:** Regex captures wrong content, tool_uses list is incomplete or corrupted.

**Mitigation:**
- Use non-greedy regex (`.*?`) to avoid over-capturing
- Test specifically on `update_todo_list` (has markdown inside `<todos>`)
- If regex fails, fall back to simple string extraction: find opening tag, find matching closing tag, extract everything between
- Phase 2 doesn't need perfect parameter parsing — just tool names and basic params

---

## Implementation Checklist

After this plan is approved, Code mode will execute:

- [ ] Create [`src/bob_coach/models.py`](src/bob_coach/models.py) with 5 dataclasses
- [ ] Create [`src/bob_coach/parser.py`](src/bob_coach/parser.py) with:
  - [ ] `parse_session(filepath: Path) -> Session` main entry point
  - [ ] `_parse_turn(lines: list[str]) -> Turn` turn parser
  - [ ] `_parse_environment(block: str) -> EnvironmentDetails` environment parser
  - [ ] `_extract_tools(content: str) -> list[ToolUse]` tool extractor
  - [ ] `_calculate_cost_deltas(turns: list[Turn]) -> None` post-processor
  - [ ] `_extract_mode_transitions(turns: list[Turn]) -> list[ModeTransition]` post-processor
- [ ] Update [`tests/test_parser.py`](tests/test_parser.py) with 12 test functions
- [ ] Run `pytest tests/test_parser.py -v` — all tests pass
- [ ] Export this Phase 1 session to [`bob_sessions/phase-1.md`](bob_sessions/phase-1.md)

---

## Success Criteria

Phase 1 is complete when:

- ✅ Both fixtures parse without errors
- ✅ `Session` object contains all expected fields (turns, cost, mode_transitions, file_edits, slash_commands)
- ✅ All 12 tests pass
- ✅ Parser handles malformed input gracefully (no unhandled exceptions)
- ✅ Bobcoin spend ≤8 coins for Phase 1
- ✅ Code has type hints on all functions and dataclass fields

---

*Phase 1 Plan | Budget: 8 coins | Fixtures: 2 | Tests: 12 | Risk Level: Medium*
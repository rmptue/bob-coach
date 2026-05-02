"""Data models for Bob Coach session parsing."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class ToolUse:
    """Represents a single tool invocation by the assistant.
    
    Used by Phase 2 detectors to identify missing /review commands
    and by Phase 3 to count deliverables for bobcoin efficiency.
    """
    name: str                          # Tool name (e.g., "read_file", "attempt_completion")
    parameters: dict[str, str]         # Extracted parameter key-value pairs
    turn_index: int                    # Which turn this tool was used in


@dataclass
class ModeTransition:
    """Tracks when Bob switches between modes (plan → code, etc.).
    
    Used by Phase 2 to detect mode thrashing (>4 switches in <10 turns).
    """
    from_mode: str | None              # Previous mode slug (None if first turn)
    to_mode: str                       # New mode slug (e.g., "plan", "code", "ask")
    to_mode_name: str                  # Display name (e.g., "📝 Plan")
    turn_index: int                    # Turn where transition occurred


@dataclass
class EnvironmentDetails:
    """Metadata from environment_details blocks.
    
    Parsed from the <environment_details> XML sections in each turn.
    All fields are optional to handle missing/malformed data gracefully.
    """
    timestamp: datetime | None = None         # Parsed from "# Current Time" ISO 8601
    cost: float = 0.0                         # Parsed from "# Current Cost" (e.g., "$0.03" → 0.03)
    mode_slug: str | None = None              # From <slug>plan</slug>
    mode_name: str | None = None              # From <name>📝 Plan</name>
    workspace_dir: str | None = None          # From "# Current Workspace Directory (...)"
    visible_files: list[str] = field(default_factory=list)   # From "# VSCode Visible Files"
    open_tabs: list[str] = field(default_factory=list)       # From "# VSCode Open Tabs"


@dataclass
class Turn:
    """A single conversation turn (user or assistant message).
    
    Core unit of session analysis. Contains all data needed for
    anti-pattern detection and metric calculation.
    """
    index: int                                # 0-based turn number in session
    speaker: Literal["user", "assistant"]     # Who sent this message
    content: str                              # Full message content (excluding environment_details)
    mode: str | None                          # Current mode slug at this turn
    cost_delta: float                         # Cost increase from previous turn (0.0 for first turn)
    cumulative_cost: float                    # Total session cost at this turn
    timestamp: datetime | None                # When this turn occurred
    tool_uses: list[ToolUse] = field(default_factory=list)           # Tools invoked in this turn
    has_error: bool = False                   # True if turn contains "[ERROR]" message
    environment: EnvironmentDetails | None = None  # Parsed environment_details (None if missing)


@dataclass
class Session:
    """Complete parsed session with all turns and metadata.
    
    Top-level object returned by parser. Contains computed fields
    for efficient Phase 2/3 processing.
    """
    turns: list[Turn] = field(default_factory=list)                  # All conversation turns in order
    total_cost: float = 0.0                                          # Final cumulative cost
    mode_transitions: list[ModeTransition] = field(default_factory=list)  # All mode switches
    workspace: str | None = None                                     # Workspace directory (from first turn)
    file_edits: int = 0                                              # Count of write_to_file/apply_diff/insert_content
    slash_commands: list[str] = field(default_factory=list)          # Extracted slash commands (e.g., ["review", "plan"])

# Made with Bob

"""Anti-pattern detection rules and thresholds.

All thresholds are configurable constants. Adjust based on your team's
Bob usage patterns and quality standards.
"""

# Cost-Based Drift
COST_DRIFT_THRESHOLD_PER_TURN = 0.30  # dollars - single turn cost increase
COST_DRIFT_THRESHOLD_SESSION = 1.50   # dollars - total session cost

# Missing Plan File
PLAN_FILE_NAMES = [
    "PLAN.md", "TODO.md", "AGENTS.md",
    "plan.md", "todo.md", "agents.md",
    "PLAN.txt", "TODO.txt"
]
CODE_MODE_TURN_THRESHOLD = 3  # Only flag if >3 Code mode turns without plan

# Missing /review Command
FILE_EDIT_THRESHOLD = 5  # number of edits before review recommended

# Conversation Loops
CONSECUTIVE_ASK_THRESHOLD = 3  # number of consecutive ask_followup_question uses

# Mode Thrashing
MODE_SWITCH_THRESHOLD = 4      # switches per window
MODE_SWITCH_WINDOW_SIZE = 10   # turns

# File Edit Tools
FILE_EDIT_TOOLS = ["write_to_file", "apply_diff", "insert_content"]

# Plan-Mode Write Violation
MARKDOWN_EXTENSIONS = [".md", ".markdown", ".txt"]

# Made with Bob
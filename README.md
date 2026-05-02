# Bob Coach

> Grades IBM Bob session exports on five metrics and seven anti-patterns. Including the sessions used to build it.

[![tests](https://img.shields.io/badge/tests-56%2F56-brightgreen)](#tests) [![hackathon](https://img.shields.io/badge/IBM%20Bob%20Dev%20Day-2026-blue)](#)

## Why this exists

IBM Bob is an AI coding agent that costs real money. Every session burns tokens that show up on a bill. But developers using Bob — and similar agents — have no honest mirror on their usage. Chat-displayed costs are inconsistent with actual API charges. There's no objective signal on whether a session was efficient, disciplined, or wasteful.

Bob Coach reads Bob's exported session reports (the markdown files Bob produces when you save a conversation) and produces a structured coaching report. Score 0-100. Five metrics. Seven anti-patterns. Evidence. Actionable recommendations.

**The recursive demo:** I ran Bob Coach on the sessions I used to build Bob Coach. Phase 1 (the parser): 0/100. Phase 4a (the renderer): 7/100. Phase 4b (where I explicitly applied lessons from Phase 1): also 7/100. The lessons were clear. The behaviors were hard. The tool refuses to grade on effort.

A coaching tool that flatters the developer is useless.

## Quick demo

```
$ bob-coach bob_sessions/phase-1.md --compact

╭──────────────────────────────────────────────────────────────────────────────╮
│ 🎯 Bob Coach Report                                                          │
│ Session: phase-1.md                                                          │
│ Cost: $5.80 | Turns: 80 | Duration: 17m                                      │
╰──────────────────────────────────────────────────────────────────────────────╯

                       📊 Metrics Summary
┃ Metric                    ┃    Target ┃    Actual ┃  Status  ┃
┃ Plan-to-Code Ratio        ┃      >20% ┃     37.9% ┃  ✓ Pass  ┃
┃ Bobcoin Efficiency        ┃   >5/$0.1 ┃  0.8/$0.1 ┃  ✗ Fail  ┃
┃ Conversation Count        ┃       <15 ┃        40 ┃  ✗ Fail  ┃
┃ Slash Command Usage       ┃      >30% ┃      0.0% ┃  ✗ Fail  ┃
┃ Error Rate                ┃      <10% ┃     22.5% ┃  ✗ Fail  ┃

⚠️  Anti-Patterns Detected (5)

▲ [CRITICAL] Cost-Based Drift (Single Turn)
▲ [CRITICAL] Cost-Based Drift (Session)
[HIGH] Missing Plan File
[HIGH] Tool Use Errors
[MEDIUM] Missing /review Command

✅ Session Score: 0/100
   1/5 metrics passing | 5 anti-patterns detected
```

## Install

```bash
git clone https://github.com/rmptue/bob-coach.git
cd bob-coach
pip install -e .
```

Requires Python 3.11+.

## Usage

```bash
# Analyze a session, full output
bob-coach bob_sessions/phase-1.md

# Compact mode (~40 lines, ideal for demo videos)
bob-coach bob_sessions/phase-1.md --compact

# JSON output for tooling
bob-coach bob_sessions/phase-1.md --format json

# Write to file
bob-coach bob_sessions/phase-1.md --output report.txt
```

### Getting a session export from Bob

In Bob's IDE: **Views → More Actions → History → Export task history**. The exported `.md` file is what you feed to Bob Coach.

## What it measures

### Five metrics

| Metric | Target | What it catches |
|---|---|---|
| Plan-to-Code Ratio | >20% planning turns | Skipping planning, jumping to code |
| Bobcoin Efficiency | >5 deliverables per $0.10 | Sessions burning money for low output |
| Conversation Count | <15 turns | Sessions that should have been split |
| Slash Command Usage | >30% | Not leveraging Bob's `/plan`, `/review` commands |
| Error Rate | <10% tool errors | Sloppy invocations, unclear requirements |

### Seven (now eight) anti-patterns

| Anti-pattern | Severity | Trigger |
|---|---|---|
| Cost-Based Drift (Single Turn) | CRITICAL | Any turn with >$0.30 cost increase |
| Cost-Based Drift (Session) | CRITICAL | Total session cost >$1.50 |
| Missing Plan File | HIGH | Code mode session without PLAN.md/TODO.md/AGENTS.md |
| Tool Use Errors | HIGH | `[ERROR]` messages following tool invocations |
| Conversation Loops | HIGH | Repeated user follow-ups without progress |
| Mode Thrashing | MEDIUM | Frequent Plan↔Code switching mid-task |
| Missing /review | MEDIUM | >5 file edits with no `/review` checkpoint |
| Repeated File Reads | MEDIUM | Same file read 3+ times in one session |

Each anti-pattern produces evidence (specific turn numbers, costs, file paths) and an actionable recommendation.

## How Bob Coach was built

Each phase is its own commit. The full development arc is visible in `git log`:

```
chore: remove redundant demo outputs
fix(demo): regenerate JSON outputs and add recording script
feat(renderer): add --compact flag and CRITICAL visual markers (Session A)
demo: add phase-4a/4b session exports and reports for video
feat(detectors): add RepeatedFileReadsDetector (lesson from phase-1 self-coaching)
feat(demo): reproducible UTF-8 output generation
Phase 3: report renderer + metrics + CLI integration (50/50 tests passing)
Phase 2: 7 anti-pattern detectors + rules.py (18/18 tests passing)
Phase 1: parser + models + tests (12/12 passing)
Phase 0: project skeleton scaffolded by Bob
Phase planning: PLAN.md + AGENTS.md + fixtures
```

All Bob session exports are in [`bob_sessions/`](bob_sessions/). Generated reports for each session are in [`demo/outputs/`](demo/outputs/). To regenerate them yourself:

```bash
python gen_demo_outputs.py
```

## Architecture

```
bob-coach/
├── src/bob_coach/
│   ├── parser.py        # Bob markdown → Session/Turn/ToolUse dataclasses
│   ├── detectors.py     # 8 anti-pattern detectors (pure functions)
│   ├── metrics.py       # 5 metrics with pass/fail thresholds
│   ├── report.py        # Terminal + JSON renderers
│   └── cli.py           # Click-based CLI entry point
├── tests/               # 56 tests covering parser, detectors, metrics, renderer
├── bob_sessions/        # Real Bob sessions used to build this tool
├── demo/outputs/        # Generated reports for each session
├── fixtures/            # Test fixtures (sample-session-01.md, sample-session-02.md)
├── DEMO.md              # Demo video narration script
├── demo.ps1             # Recording script (PowerShell)
└── gen_demo_outputs.py  # Reproducible report regeneration
```

Pure Python, no external services, no API keys. Detectors are independent functions that compose through a shared `AntiPattern` dataclass.

## Tests

```bash
pytest -q
# 56 passed
```

## Known limitations (v0.1)

- ANSI bold codes leak into non-TTY output. CRITICAL anti-pattern lines show `[1m...[0m` literals when redirected to files. Renders correctly in interactive terminals. Fix planned for v0.2.
- Cost-Based Drift evidence list shows cumulative cost rather than per-turn delta. Bob Coach detected this on its own session — kept as v0.1 quirk for the recursive narrative.
- Path normalization in Repeated File Reads detector uses simple string equality. Same logical file at different relative/absolute paths counts separately.

## Submission

Built solo for IBM Bob Dev Day Hackathon, May 1–3, 2026.

Bob built Bob Coach. I scaffolded the project with Bob's Plan mode in Phase 0, built the parser in Phase 1, detectors in Phase 2, renderer and metrics in Phase 3, all in separate Bob conversations to maintain clean context boundaries. Phase 4a added the `--compact` flag. Phase 4b added the eighth detector — `RepeatedFileReadsDetector` — in a session where I explicitly applied lessons from Bob Coach's analysis of Phase 1.

The recursive demo is the codebase.

## License

MIT

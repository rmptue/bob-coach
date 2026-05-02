# Bob Coach — Demo Recording Script
# Run inside the project root: .\demo.ps1
# Press Enter between beats. Each beat aligns with a section in DEMO.md.
#
# Pre-flight (do BEFORE starting recording):
#   1. chcp 65001
#   2. $OutputEncoding = [System.Text.Encoding]::UTF8
#   3. [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
#   4. Increase terminal font size to ~18-20pt for screen recording
#   5. Maximize terminal window
#   6. Clear terminal: clear

# ---------- Beat 1: Hook ----------
Clear-Host
Write-Host ""
Write-Host "  Bob Coach" -ForegroundColor Cyan
Write-Host "  IBM Bob Dev Day Hackathon 2026" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  [Press Enter to begin demo]" -ForegroundColor DarkGray
Read-Host

# ---------- Beat 2: Clean session ----------
Clear-Host
Write-Host "PS> bob-coach fixtures\sample-session-01.md" -ForegroundColor Yellow
Write-Host ""
bob-coach fixtures\sample-session-01.md
Write-Host ""
Write-Host "  [Narration: 'forty out of one hundred... what good looks like']" -ForegroundColor DarkGray
Read-Host

# ---------- Beat 3: phase-1 ----------
Clear-Host
Write-Host "PS> bob-coach bob_sessions\phase-1.md --compact" -ForegroundColor Yellow
Write-Host ""
bob-coach bob_sessions\phase-1.md --compact
Write-Host ""
Write-Host "  [Narration: 'eighty turns... five dollars and eighty cents... zero out of one hundred']" -ForegroundColor DarkGray
Read-Host

# ---------- Beat 4: phase-4a ----------
Clear-Host
Write-Host "PS> bob-coach bob_sessions\phase-4a-renderer-polish.md --compact" -ForegroundColor Yellow
Write-Host ""
bob-coach bob_sessions\phase-4a-renderer-polish.md --compact
Write-Host ""
Write-Host "  [Narration: 'building the renderer... score: seven']" -ForegroundColor DarkGray
Read-Host

# ---------- Beat 5: phase-4b ----------
Clear-Host
Write-Host "PS> bob-coach bob_sessions\phase-4b-self-coached.md --compact" -ForegroundColor Yellow
Write-Host ""
bob-coach bob_sessions\phase-4b-self-coached.md --compact
Write-Host ""
Write-Host "  [Narration: 'same score. seven. the tool refuses to lie...']" -ForegroundColor DarkGray
Read-Host

# ---------- Beat 6: JSON output ----------
Clear-Host
Write-Host "PS> bob-coach bob_sessions\phase-1.md --format json | Select-Object -First 25" -ForegroundColor Yellow
Write-Host ""
bob-coach bob_sessions\phase-1.md --format json | Select-Object -First 25
Write-Host ""
Write-Host "  [Narration: 'seven detectors... five metrics... fifty-six tests']" -ForegroundColor DarkGray
Read-Host

# ---------- Beat 7: Close ----------
Clear-Host
Write-Host ""
Write-Host "  Bob Coach" -ForegroundColor Cyan
Write-Host "  Built with Bob. Grading Bob honestly." -ForegroundColor White
Write-Host ""
Write-Host "  github.com/rmptue/bob-coach" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  [End of demo]" -ForegroundColor DarkGray
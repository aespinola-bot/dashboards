# scripts/

Maintenance scripts for this dashboards repo.

## `update-wc-results.py`

Auto-fetches **World Cup 2026** group-stage results from Wikipedia (the 12
`2026_FIFA_World_Cup_Group_X` pages) and patches:

1. `worldcup2026.html` — adds/updates an `actual:[h,a]` field on each
   matching `MATCHES` entry. Once present, the dashboard renders a locked
   FINAL score box (no inputs) and computes 🤖 AI vs 👤 You accuracy.
2. `~\OneDrive - Microsoft\Desktop\agency-output\WorldCup2026_Calendar.md`
   — rewrites the bold match cell to `🔒 Home H–A Away` and replaces the
   Pred column with `AI: X–Y ✓✓ / ✓ / ✗`.

### Usage

```powershell
# Preview what would change
python scripts\update-wc-results.py --dry-run

# Apply changes
python scripts\update-wc-results.py

# Apply, commit and push (one-shot post-matchday)
python scripts\update-wc-results.py --commit --push

# Skip MD regen (HTML only)
python scripts\update-wc-results.py --skip-md
```

Run after each matchday. Idempotent — only adds/updates `actual` fields that
have changed. Wikipedia API has a soft rate limit; the script sleeps 0.5s
between group fetches. If you get 429s, just re-run.

### Suggested scheduled task

Run once a day at 23:30 PT during the group stage (Jun 11–27 2026):

```powershell
$action = New-ScheduledTaskAction `
  -Execute "python" `
  -Argument "scripts\update-wc-results.py --commit --push" `
  -WorkingDirectory "C:\Users\toespino\dashboards"
$trigger = New-ScheduledTaskTrigger -Daily -At 11:30PM
Register-ScheduledTask -TaskName "WC2026-results-sync" -Action $action -Trigger $trigger
```

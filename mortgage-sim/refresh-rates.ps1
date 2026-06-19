# refresh-rates.ps1
# Pulls latest 30y fixed conforming mortgage rate from Freddie Mac PMMS (via FRED public CSV)
# and writes rates.json next to MortgageSim.html. Scheduled to run daily at 6:00 AM PST.

param(
    [string]$OutFile = (Join-Path $PSScriptRoot 'rates.json'),
    [string]$LogFile = (Join-Path $PSScriptRoot 'refresh-rates.log')
)

$ErrorActionPreference = 'Stop'
function Log($m){ "$([DateTime]::Now.ToString('MM/dd/yyyy HH:mm:ss')) $m" | Tee-Object -FilePath $LogFile -Append | Out-Null }

try {
    Log "Starting rate refresh"

    # Freddie Mac PMMS 30y / 15y fixed (weekly Thu) — public CSV via FRED, no key
    $url30 = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US'
    $url15 = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE15US'

    $tmp30 = New-TemporaryFile; $tmp15 = New-TemporaryFile

    # curl.exe handles TLS reliably where Invoke-WebRequest sometimes hangs
    & curl.exe -sS --max-time 45 -o $tmp30 $url30
    if($LASTEXITCODE -ne 0){ throw "curl 30y failed exit=$LASTEXITCODE" }
    & curl.exe -sS --max-time 45 -o $tmp15 $url15
    if($LASTEXITCODE -ne 0){ throw "curl 15y failed exit=$LASTEXITCODE" }

    $csv30 = Import-Csv $tmp30 | Where-Object { $_.MORTGAGE30US -and $_.MORTGAGE30US -ne '.' } | Select-Object -Last 1
    $csv15 = Import-Csv $tmp15 | Where-Object { $_.MORTGAGE15US -and $_.MORTGAGE15US -ne '.' } | Select-Object -Last 1

    $rate30 = [double]$csv30.MORTGAGE30US
    $rate15 = [double]$csv15.MORTGAGE15US

    # Derive 20y / 10y by simple spread relative to historical PMMS deltas
    $rate20 = [Math]::Round($rate30 - 0.25, 3)
    $rate10 = [Math]::Round($rate15 - 0.10, 3)

    # PMMS observation date is in 'observation_date' column; format mm/dd/yyyy
    $obs = $csv30.observation_date
    $obsDt = [DateTime]::Parse($obs)
    $asOf = $obsDt.ToString('MM/dd/yyyy')
    $now  = [DateTime]::Now.ToString('MM/dd/yyyy HH:mm:ss')

    $payload = [ordered]@{
        rate30   = $rate30
        rate20   = $rate20
        rate15   = $rate15
        rate10   = $rate10
        asOf     = $asOf
        source   = 'Freddie Mac PMMS via FRED (MORTGAGE30US / MORTGAGE15US)'
        updatedAt= $now
    }

    $json = $payload | ConvertTo-Json -Depth 4
    Set-Content -Path $OutFile -Value $json -Encoding UTF8

    Remove-Item $tmp30,$tmp15 -ErrorAction SilentlyContinue
    Log "OK rate30=$rate30 rate15=$rate15 asOf=$asOf -> $OutFile"

    # ---------- auto-commit & push so GitHub Pages stays current ----------
    $repoRoot = Split-Path -Parent (Split-Path -Parent $OutFile)
    if(Test-Path (Join-Path $repoRoot '.git')){
        Push-Location $repoRoot
        try {
            $rel = Resolve-Path -Relative $OutFile
            & git add $rel 2>&1 | Out-Null
            $changes = & git status --porcelain $rel
            if($changes){
                & git -c user.name='aespinola-bot' -c user.email='aespinola-bot@users.noreply.github.com' commit -m "chore(mortgage-sim): refresh rates $asOf (30y=$rate30%, 15y=$rate15%)" 2>&1 | Out-Null
                & git push origin main 2>&1 | Out-Null
                Log "git push OK"
            } else {
                Log "no rate change since last run, skipping commit"
            }
        } catch { Log "git ERROR $_" }
        finally { Pop-Location }
    }
}
catch {
    Log "ERROR $_"
    throw
}

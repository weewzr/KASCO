# Captures genuine screenshots of the running KASCO site with headless Edge.
param([string]$Base = "http://localhost:8765/index.html", [string]$Out)
$edge = "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
$tmp = Join-Path $env:TEMP "kasco-edge-profile"
foreach ($tab in @("map", "overview")) {
    $file = Join-Path $Out "site_$tab.png"
    & $edge --headless=new --disable-gpu --hide-scrollbars --no-first-run --user-data-dir="$tmp" --window-size=1600,1000 --virtual-time-budget=15000 --screenshot="$file" "$Base#$tab" | Out-Null
    Start-Sleep -Seconds 3
    "$file $((Get-Item $file).Length)"
}

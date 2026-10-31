# Exports the pitch deck to PDF through PowerPoint.
param([string]$Deck, [string]$Pdf)
$app = New-Object -ComObject PowerPoint.Application
$p = $app.Presentations.Open($Deck, $true, $false, $false)
$p.SaveAs($Pdf, 32)
$p.Close()
$app.Quit()
Write-Output "exported $Pdf"

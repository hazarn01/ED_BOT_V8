# Validate ED Bot v8 API locally on Windows

Write-Host "Checking API health..." -ForegroundColor Cyan
$health = Invoke-RestMethod -Uri http://localhost:8001/health -UseBasicParsing
$health | ConvertTo-Json -Compress

Write-Host "`nContact query..." -ForegroundColor Cyan
$body1 = @{ query = "who is on call for cardiology" } | ConvertTo-Json
$r1 = Invoke-RestMethod -Uri http://localhost:8001/api/v1/query -Method Post -ContentType 'application/json' -Body $body1 -UseBasicParsing
$r1 | ConvertTo-Json -Compress

Write-Host "`nForm query..." -ForegroundColor Cyan
$body2 = @{ query = "show me the blood transfusion form" } | ConvertTo-Json
$r2 = Invoke-RestMethod -Uri http://localhost:8001/api/v1/query -Method Post -ContentType 'application/json' -Body $body2 -UseBasicParsing
$r2 | ConvertTo-Json -Compress

Write-Host "`nProtocol query..." -ForegroundColor Cyan
$body3 = @{ query = "what is the STEMI protocol" } | ConvertTo-Json
$r3 = Invoke-RestMethod -Uri http://localhost:8001/api/v1/query -Method Post -ContentType 'application/json' -Body $body3 -UseBasicParsing
$r3 | ConvertTo-Json -Compress

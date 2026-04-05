while ($true) {
    Clear-Host
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "=== Latest Jobs ($timestamp) ===" -ForegroundColor Cyan
    Write-Host ""
    
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8000/api/upwork/most_recent_jobs"
        
        $jobsToShow = $response.jobs | Select-Object -First 3
        
        foreach ($job in $jobsToShow) {
            Write-Host "Job: " -NoNewline -ForegroundColor Yellow
            Write-Host $job.title -ForegroundColor White
            
            Write-Host "Budget: " -NoNewline -ForegroundColor Yellow
            Write-Host $job.budget -ForegroundColor Green
            
            Write-Host "Country: " -NoNewline -ForegroundColor Yellow
            Write-Host $job.country -ForegroundColor White
            
            Write-Host "Skills: " -NoNewline -ForegroundColor Yellow
            Write-Host ($job.skills -join ", ") -ForegroundColor Cyan
            
            Write-Host "---" -ForegroundColor DarkGray
            Write-Host ""
        }
    }
    catch {
        Write-Host "Error fetching jobs: $_" -ForegroundColor Red
    }
    
    Write-Host "Refreshing in 10 seconds... (Press Ctrl+C to stop)" -ForegroundColor DarkYellow
    Start-Sleep -Seconds 10
}

# PowerShell script to run tests by category with timeouts
# Each category runs separately to isolate issues

$ErrorActionPreference = "Continue"
$outputDir = "test_results_by_category"
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

# Test categories based on pytest markers (excluding performance, chaos, compatibility as per CI)
$categories = @(
    @{Name="unit"; Marker="unit"},
    @{Name="integration"; Marker="integration"},
    @{Name="core"; Marker="core"},
    @{Name="peer"; Marker="peer"},
    @{Name="piece"; Marker="piece"},
    @{Name="tracker"; Marker="tracker"},
    @{Name="network"; Marker="network"},
    @{Name="metadata"; Marker="metadata"},
    @{Name="disk"; Marker="disk"},
    @{Name="file"; Marker="file"},
    @{Name="storage"; Marker="storage"},
    @{Name="session"; Marker="session"},
    @{Name="resilience"; Marker="resilience"},
    @{Name="connection"; Marker="connection"},
    @{Name="checkpoint"; Marker="checkpoint"},
    @{Name="cli"; Marker="cli"},
    @{Name="extensions"; Marker="extensions"},
    @{Name="ml"; Marker="ml"},
    @{Name="monitoring"; Marker="monitoring"},
    @{Name="observability"; Marker="observability"},
    @{Name="protocols"; Marker="protocols"},
    @{Name="security"; Marker="security"},
    @{Name="transport"; Marker="transport"},
    @{Name="config"; Marker="config"},
    @{Name="discovery"; Marker="discovery"},
    @{Name="plugins"; Marker="plugins"},
    @{Name="daemon"; Path="tests/daemon"},
    @{Name="services"; Marker="services"}
)

$allFailures = @()

foreach ($category in $categories) {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "Running category: $($category.Name)" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
    
    $outputFile = "$outputDir\$($category.Name)_output.txt"
    $failuresFile = "$outputDir\$($category.Name)_failures.txt"
    
    # Build pytest command
    $pytestArgs = @(
        "-c", "dev/pytest.ini",
        "tests/",
        "-v",
        "--tb=short",
        "--maxfail=999",
        "--timeout=600",
        "--timeout-method=thread",
        "-m", "not performance and not chaos and not compatibility"
    )
    
    # Add marker or path filter
    if ($category.Marker) {
        $pytestArgs += "-m", $category.Marker
    } elseif ($category.Path) {
        $pytestArgs = $pytestArgs[0..($pytestArgs.Length-2)]  # Remove tests/ from args
        $pytestArgs += $category.Path
    }
    
    # Run pytest and capture output
    $startTime = Get-Date
    try {
        $result = & uv run pytest @pytestArgs 2>&1 | Tee-Object -FilePath $outputFile
        
        $endTime = Get-Date
        $duration = $endTime - $startTime
        
        # Extract failures from output
        $failureLines = $result | Select-String -Pattern "(FAILED|ERROR|TIMEOUT|timeout)" -Context 5,10
        
        if ($failureLines) {
            $failureLines | Out-File -FilePath $failuresFile -Encoding utf8
            $allFailures += [PSCustomObject]@{
                Category = $category.Name
                Failures = ($failureLines | Measure-Object).Count
                Duration = $duration
                OutputFile = $outputFile
                FailuresFile = $failuresFile
            }
            Write-Host "FAILURES DETECTED: $($failureLines.Count) failures" -ForegroundColor Red
        } else {
            Write-Host "All tests passed!" -ForegroundColor Green
        }
        
        Write-Host "Duration: $($duration.TotalSeconds) seconds" -ForegroundColor Yellow
        
    } catch {
        Write-Host "ERROR running tests: $_" -ForegroundColor Red
        $allFailures += [PSCustomObject]@{
            Category = $category.Name
            Failures = "ERROR"
            Duration = (Get-Date) - $startTime
            OutputFile = $outputFile
            FailuresFile = $failuresFile
            Error = $_.Exception.Message
        }
    }
    
    # Small delay between categories
    Start-Sleep -Seconds 2
}

# Create summary
$summaryFile = "$outputDir\summary.txt"
$allFailures | Format-Table -AutoSize | Out-File -FilePath $summaryFile -Encoding utf8

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
$allFailures | Format-Table -AutoSize
Write-Host "`nFull results saved to: $outputDir" -ForegroundColor Green



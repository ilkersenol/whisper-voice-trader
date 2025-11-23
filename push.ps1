param(
    [string]$Message = "update"
)

Write-Host "Git push başlatılıyor..." -ForegroundColor Cyan

git status

Write-Host "`nDevam etmek istiyor musun? (E/h)" -NoNewline
$answer = Read-Host

if ($answer -ne "E" -and $answer -ne "e") {
    Write-Host "İptal edildi."
    exit 0
}

git add .
git commit -m "$Message"
git push

Write-Host "`nİşlem tamamlandı." -ForegroundColor Green

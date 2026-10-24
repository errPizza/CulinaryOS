$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$python = Join-Path $projectRoot 'tools\python\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = (Get-Command python -ErrorAction Stop).Source }
$bash = 'C:\Program Files\Git\bin\bash.exe'
if (-not (Test-Path -LiteralPath $bash)) { $bash = (Get-Command bash -ErrorAction Stop).Source }
if (-not $env:CULINARYOS_OPENSSL) {
    $openssl = 'C:\Program Files\Git\usr\bin\openssl.exe'
    if (Test-Path -LiteralPath $openssl) { $env:CULINARYOS_OPENSSL = $openssl }
}
$results = @()
foreach ($name in @('test_project.py','test_diagnostics.py','test_backup.py','test_network.py','test_pki.py','test_data.py','test_runtime.py','test_firstboot.py','test_sync_tls.py')) {
    $ErrorActionPreference = 'Continue'
    $output = & $python (Join-Path $projectRoot "tests\$name") 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    $results += [pscustomobject]@{ name = $name; exit_code = $code; output = @($output) }
    $output | Write-Output
}
$scripts = @(Get-ChildItem scripts -Filter '*.sh') + @(Get-Item 'os\hooks\0100-culinaryos.hook.chroot') + @(Get-ChildItem 'os\overlay\usr\local\sbin' -File)
foreach ($script in $scripts) {
    $output = & $bash -n $script.FullName 2>&1 | ForEach-Object { "$_" }
    $results += [pscustomobject]@{ name = "bash -n $($script.Name)"; exit_code = $LASTEXITCODE; output = @($output) }
}
$shellcheck = Join-Path $projectRoot 'tools\shellcheck\shellcheck.exe'
if (Test-Path -LiteralPath $shellcheck) {
    $paths = @($scripts | ForEach-Object { $_.FullName })
    $output = & $shellcheck --format=json1 @paths
    $results += [pscustomobject]@{ name = 'ShellCheck'; exit_code = $LASTEXITCODE; output = @($output) }
}
New-Item -ItemType Directory -Path results -Force | Out-Null
$report = [ordered]@{
    timestamp_utc = [DateTime]::UtcNow.ToString('o')
    environment = 'Windows; Python portable; Git Bash (sin kernel Linux)'
    tests = $results
    not_executed = @('ISO','arranque BIOS/UEFI/Secure Boot','systemd','nftables','PAM','AppArmor','GUI','VM','persistencia instalada','transporte AF_UNIX y permisos POSIX','UPS USB y apagado físico','Avahi/mDNS en LAN real','systemd LoadCredential','app nativa futura','central real no aprovisionado')
}
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath 'results\local-verification.json' -Encoding UTF8
if (@($results | Where-Object { $_.exit_code -ne 0 }).Count -gt 0) { exit 1 }
Write-Output 'Verificaciones locales aprobadas. Las pruebas Linux siguen pendientes.'

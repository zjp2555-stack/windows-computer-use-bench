param([ValidateSet('typesafe','vercel')][string]$Provider = 'typesafe')
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1') -Force
$keyName = if ($Provider -eq 'vercel') { 'vercel-key.dpapi' } else { 'jev-key.dpapi' }
$keyPath = Join-Path $PSScriptRoot ('..\config\' + $keyName)
$secret = (Get-Content -LiteralPath $keyPath -Raw).Trim() | ConvertTo-SecureString
$keyPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try { [Console]::Write([Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPtr)) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPtr); $secret.Dispose() }

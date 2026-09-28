$ErrorActionPreference = 'Stop'
$portRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $portRoot
$env:PYTHONUTF8 = '1'
while ($true) {
    Clear-Host
    Write-Host 'TYPESAFE COMPUTER USE - WINDOWS PORT' -ForegroundColor Cyan
    Write-Host '1 - Check installation status'
    Write-Host '2 - Open usage and agent guide'
    Write-Host '3 - Change API key (hidden input)'
    Write-Host '4 - Generate and open MCP configuration'
    Write-Host '5 - Stop active runs'
    Write-Host '0 - Exit'
    switch (Read-Host 'Choice') {
        '1' { & '.venv/Scripts/python.exe' -c 'from typesafe_computer_use.credentials import prepare_provider; prepare_provider(); import os; from typesafe_computer_use.windows_ocr import engine; print("Jev key available:", bool(os.environ.get("TYPESAFE_API_KEY"))); print("Local OCR:", engine().recognizer_language.language_tag); print("Writer: current MCP host agent")' }
        '2' { Start-Process notepad.exe -ArgumentList ('"'+(Join-Path $portRoot 'WINDOWS.md')+'"') }
        '3' { & (Join-Path $PSScriptRoot 'Set-Key.ps1') }
        '4' { & (Join-Path $PSScriptRoot 'Generate-McpConfig.ps1'); Start-Process notepad.exe -ArgumentList ('"'+(Join-Path $portRoot 'mcp-config.json')+'"') }
        '5' { & (Join-Path $PSScriptRoot 'Stop.ps1') }
        '0' { exit }
    }
    [void](Read-Host 'Press Enter to return to the menu')
}

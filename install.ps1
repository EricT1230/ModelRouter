[CmdletBinding()]
param(
    [ValidateSet('user', 'project')]
    [string]$Scope = 'user',
    [string]$Project,
    [string]$CodexHome,
    [switch]$Apply,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
if ($Apply -and $DryRun) {
    throw 'Choose -Apply or -DryRun, not both.'
}
if (-not $Apply -and -not $DryRun) {
    $DryRun = $true
}
if ($Scope -eq 'project' -and [string]::IsNullOrWhiteSpace($Project)) {
    throw '-Project is required when -Scope project is selected.'
}

$pythonCommand = Get-Command py -ErrorAction SilentlyContinue
$pythonArguments = @()
if ($null -eq $pythonCommand) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
}
if ($null -eq $pythonCommand) {
    throw 'Python 3.10 or newer is required. Install Python, then run this script again.'
}
if ($pythonCommand.Name -in @('py', 'py.exe')) {
    $pythonArguments += '-3'
}

$script = Join-Path $PSScriptRoot 'scripts/install.py'
$arguments = @($pythonArguments + @('-X', 'utf8', $script, '--scope', $Scope))
if (-not [string]::IsNullOrWhiteSpace($Project)) {
    $arguments += @('--project', $Project)
}
if (-not [string]::IsNullOrWhiteSpace($CodexHome)) {
    $arguments += @('--codex-home', $CodexHome)
}
$arguments += if ($Apply) { '--apply' } else { '--dry-run' }

& $pythonCommand.Source @arguments
exit $LASTEXITCODE

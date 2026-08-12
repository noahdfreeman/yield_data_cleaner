# Create a live QGIS development link without overwriting an installed plugin.
[CmdletBinding()]
param(
    [string]$ProfileName = "default"
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $repositoryRoot "yield_data_cleaner"
$pluginsRoot = Join-Path $env:APPDATA "QGIS\QGIS3\profiles\$ProfileName\python\plugins"
$destination = Join-Path $pluginsRoot "yield_data_cleaner"

if (-not (Test-Path -LiteralPath (Join-Path $source "metadata.txt") -PathType Leaf)) {
    throw "Plugin source is missing metadata.txt: $source"
}

New-Item -ItemType Directory -Path $pluginsRoot -Force | Out-Null
if (Test-Path -LiteralPath $destination) {
    $existing = Get-Item -LiteralPath $destination -Force
    $existingTarget = @($existing.Target) -join ""
    if ($existing.LinkType -eq "Junction" -and $existingTarget -eq $source) {
        Write-Output "Development link already configured: $destination"
        exit 0
    }
    throw "Refusing to replace existing plugin path: $destination"
}

New-Item -ItemType Junction -Path $destination -Target $source | Out-Null
Write-Output "QGIS development link created: $destination -> $source"

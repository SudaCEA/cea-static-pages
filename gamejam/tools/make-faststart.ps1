# Remux a clip so the MP4 metadata (moov) sits before the media data (mdat).
#
# Browsers can only know a clip's duration and first frame after reading moov.
# In a non-faststart file moov lives at the end, so the browser has to download
# the whole file before `canplay` fires: the loading bar jumps 0 -> 100% and
# playback only starts at the end. Remuxing with -movflags +faststart fixes it
# without re-encoding (stream copy, identical quality and size).
#
#   .\gamejam\tools\make-faststart.ps1
#   .\gamejam\tools\make-faststart.ps1 -Source assets\mirror-26\clip.mp4 `
#       -Target mirror-2610\assets\clip.mp4
#
# Requires ffmpeg on PATH or in FFMPEG_BIN.

param(
    [string]$Source = "assets/mirror-26/video-placeholder.mp4",
    [string]$Target = "mirror-2610/assets/video-placeholder.mp4"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$sourcePath = Join-Path $root (Join-Path "gamejam" $Source)
$targetPath = Join-Path $root (Join-Path "gamejam" $Target)

if (-not (Test-Path -LiteralPath $sourcePath)) {
    throw "source clip not found: $sourcePath"
}

$ffmpeg = $env:FFMPEG_BIN
if (-not $ffmpeg) {
    $command = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($command) { $ffmpeg = $command.Source }
}
if (-not $ffmpeg) {
    throw "ffmpeg not found; put it on PATH or set FFMPEG_BIN"
}

$targetDir = Split-Path -Parent $targetPath
if (-not (Test-Path -LiteralPath $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir | Out-Null
}

& $ffmpeg -y -v error -i $sourcePath -c copy -movflags +faststart $targetPath
if ($LASTEXITCODE -ne 0) {
    throw "ffmpeg failed with exit code $LASTEXITCODE"
}

Write-Host ("faststart remux: {0} -> {1}" -f $Source, $Target)

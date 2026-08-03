# Generate the MSIX tile assets and the app .ico from one square source image.
#
# By default the whole source is used. The crop parameters exist only for a
# source that is not already composed as a square -- a hardcoded crop window
# silently clipped the logo ("Downloader" came out as "Down") in every derived
# asset, including the .ico shown in the window title bar.
param(
    [string]$Source = "$PSScriptRoot\..\assets\stz-downloader.png",
    [string]$OutDir = "$PSScriptRoot\..\assets",
    [double]$Fill = 1.0,
    [int]$IconCropX = 0,
    [int]$IconCropY = 0,
    # 0 => use the largest centred square the source allows (the whole image
    # when it is already square).
    [int]$IconCropSize = 0
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Source)) {
    throw "Source image not found: $Source"
}

New-Item -ItemType Directory -Force $OutDir | Out-Null
Add-Type -AssemblyName System.Drawing

$targets = @(
    @{ Name = "StoreLogo.png"; Size = 50 },
    @{ Name = "Square150x150Logo.png"; Size = 150 },
    @{ Name = "Square44x44Logo.png"; Size = 44 },
    @{ Name = "Square310x310Logo.png"; Size = 310 },
    @{ Name = "Square71x71Logo.png"; Size = 71 }
)

$src = [System.Drawing.Image]::FromFile((Resolve-Path $Source))
try {
    if ($IconCropSize -le 0) {
        $IconCropSize = [Math]::Min($src.Width, $src.Height)
        $IconCropX = [int](($src.Width - $IconCropSize) / 2)
        $IconCropY = [int](($src.Height - $IconCropSize) / 2)
    }
    if ($IconCropX -lt 0 -or $IconCropY -lt 0 -or
        ($IconCropX + $IconCropSize) -gt $src.Width -or
        ($IconCropY + $IconCropSize) -gt $src.Height) {
        throw ("Crop ${IconCropSize}px at ($IconCropX,$IconCropY) falls outside " +
               "the $($src.Width)x$($src.Height) source. Anything outside the " +
               "source would be clipped from every generated asset.")
    }
    Write-Host "Source $($src.Width)x$($src.Height); using ${IconCropSize}px square at ($IconCropX,$IconCropY)"
    $crop = [System.Drawing.Rectangle]::new($IconCropX, $IconCropY, $IconCropSize, $IconCropSize)
    $icoFrames = New-Object System.Collections.Generic.List[System.Drawing.Bitmap]
    foreach ($target in $targets) {
        $size = [int]$target.Size
        $dest = Join-Path $OutDir $target.Name
        $bmp = New-Object System.Drawing.Bitmap $size, $size, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
        try {
            $graphics = [System.Drawing.Graphics]::FromImage($bmp)
            try {
                $graphics.Clear([System.Drawing.Color]::Transparent)
                $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
                $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
                $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
                $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality

                $scale = [Math]::Min($size / $crop.Width, $size / $crop.Height) * $Fill
                $width = [int][Math]::Round($crop.Width * $scale)
                $height = [int][Math]::Round($crop.Height * $scale)
                $x = [int][Math]::Floor(($size - $width) / 2)
                $y = [int][Math]::Floor(($size - $height) / 2)

                $graphics.DrawImage(
                    $src,
                    [System.Drawing.Rectangle]::new($x, $y, $width, $height),
                    $crop,
                    [System.Drawing.GraphicsUnit]::Pixel
                )
                $bmp.Save($dest, [System.Drawing.Imaging.ImageFormat]::Png)
            }
            finally {
                $graphics.Dispose()
            }
        }
        finally {
            $bmp.Dispose()
        }
        Write-Host "Generated $dest"
    }

    foreach ($size in @(16, 24, 32, 48, 64, 128, 256)) {
        $bmp = New-Object System.Drawing.Bitmap $size, $size, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
        $graphics = [System.Drawing.Graphics]::FromImage($bmp)
        try {
            $graphics.Clear([System.Drawing.Color]::Transparent)
            $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
            $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
            $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality

            $scale = [Math]::Min($size / $crop.Width, $size / $crop.Height) * $Fill
            $width = [int][Math]::Round($crop.Width * $scale)
            $height = [int][Math]::Round($crop.Height * $scale)
            $x = [int][Math]::Floor(($size - $width) / 2)
            $y = [int][Math]::Floor(($size - $height) / 2)
            $graphics.DrawImage(
                $src,
                [System.Drawing.Rectangle]::new($x, $y, $width, $height),
                $crop,
                [System.Drawing.GraphicsUnit]::Pixel
            )
            $icoFrames.Add($bmp)
        }
        finally {
            $graphics.Dispose()
        }
    }

    $iconPath = Join-Path $OutDir "stz-downloader.ico"
    $stream = [System.IO.File]::Create($iconPath)
    try {
        $writer = New-Object System.IO.BinaryWriter $stream
        $writer.Write([UInt16]0)
        $writer.Write([UInt16]1)
        $writer.Write([UInt16]$icoFrames.Count)

        $pngs = @()
        $offset = 6 + (16 * $icoFrames.Count)
        foreach ($frame in $icoFrames) {
            $memory = New-Object System.IO.MemoryStream
            $frame.Save($memory, [System.Drawing.Imaging.ImageFormat]::Png)
            $bytes = $memory.ToArray()
            $pngs += ,$bytes
            $entryWidth = if ($frame.Width -eq 256) { 0 } else { $frame.Width }
            $entryHeight = if ($frame.Height -eq 256) { 0 } else { $frame.Height }
            $writer.Write([byte]$entryWidth)
            $writer.Write([byte]$entryHeight)
            $writer.Write([byte]0)
            $writer.Write([byte]0)
            $writer.Write([UInt16]1)
            $writer.Write([UInt16]32)
            $writer.Write([UInt32]$bytes.Length)
            $writer.Write([UInt32]$offset)
            $offset += $bytes.Length
            $memory.Dispose()
        }

        foreach ($bytes in $pngs) {
            $writer.Write($bytes)
        }
        $writer.Dispose()
    }
    finally {
        $stream.Dispose()
        foreach ($frame in $icoFrames) {
            $frame.Dispose()
        }
    }
    Write-Host "Generated $iconPath"
}
finally {
    $src.Dispose()
}

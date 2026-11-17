# Уменьшенные копии фото для сайта: img/photos/<имя>@640.jpg и <имя>@1200.jpg.
# Браузер сам выбирает подходящий размер (srcset в build.py). Без этого при
# отдалении страницы (масштаб < 100%) браузер ужимает большое фото в 3–5 раз,
# и прямые линии на фото «волнятся».
# Запуск после добавления новых фото:  powershell -File tools\resize-photos.ps1
Add-Type -AssemblyName System.Drawing
$dir = Join-Path $PSScriptRoot "..\img\photos" | Resolve-Path
$enc = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq 'image/jpeg' }
$p = New-Object System.Drawing.Imaging.EncoderParameters(1)
$p.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter([System.Drawing.Imaging.Encoder]::Quality, [long]86)
$made = 0
Get-ChildItem $dir -File | Where-Object { $_.Extension -match '^\.(jpe?g|png)$' -and $_.BaseName -notmatch '@\d+$' } | ForEach-Object {
  $src = $_
  foreach ($w in 640, 1200) {
    $out = Join-Path $dir ("{0}@{1}.jpg" -f $src.BaseName, $w)
    if ((Test-Path $out) -and ((Get-Item $out).LastWriteTime -ge $src.LastWriteTime)) { continue }
    $img = [System.Drawing.Image]::FromFile($src.FullName)
    if ($img.Width -le $w) { $img.Dispose(); if (Test-Path $out) { Remove-Item $out }; continue }
    $h = [int][math]::Round($img.Height * $w / $img.Width)
    $bmp = New-Object System.Drawing.Bitmap($w, $h)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.Clear([System.Drawing.Color]::White)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $g.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $attr = New-Object System.Drawing.Imaging.ImageAttributes
    $attr.SetWrapMode([System.Drawing.Drawing2D.WrapMode]::TileFlipXY)
    $g.DrawImage($img, (New-Object System.Drawing.Rectangle(0, 0, $w, $h)), 0, 0, $img.Width, $img.Height, [System.Drawing.GraphicsUnit]::Pixel, $attr)
    $bmp.Save($out, $enc, $p)
    $g.Dispose(); $bmp.Dispose(); $img.Dispose()
    $made++
  }
}
"done: $made new copies"

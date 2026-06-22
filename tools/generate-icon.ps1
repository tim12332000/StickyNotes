param(
    [string]$OutputPath = (Join-Path $PSScriptRoot "..\app\assets\note.ico")
)

Add-Type -AssemblyName System.Drawing

$size = 64
$bitmap = [System.Drawing.Bitmap]::new($size, $size)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.Clear([System.Drawing.Color]::Transparent)

$outline = [System.Drawing.Pen]::new(
    [System.Drawing.ColorTranslator]::FromHtml("#3b3b36"),
    3
)
$outline.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
$paper = [System.Drawing.SolidBrush]::new(
    [System.Drawing.ColorTranslator]::FromHtml("#fff176")
)
$fold = [System.Drawing.SolidBrush]::new(
    [System.Drawing.ColorTranslator]::FromHtml("#fff9c4")
)
$linePen = [System.Drawing.Pen]::new(
    [System.Drawing.ColorTranslator]::FromHtml("#796f2c"),
    2
)
$linePen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
$linePen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round

$page = [System.Drawing.Drawing2D.GraphicsPath]::new()
$page.AddPolygon([System.Drawing.Point[]]@(
    [System.Drawing.Point]::new(10, 4),
    [System.Drawing.Point]::new(44, 4),
    [System.Drawing.Point]::new(56, 16),
    [System.Drawing.Point]::new(56, 60),
    [System.Drawing.Point]::new(10, 60)
))
$graphics.FillPath($paper, $page)
$graphics.DrawPath($outline, $page)

$foldPath = [System.Drawing.Drawing2D.GraphicsPath]::new()
$foldPath.AddPolygon([System.Drawing.Point[]]@(
    [System.Drawing.Point]::new(44, 5),
    [System.Drawing.Point]::new(55, 16),
    [System.Drawing.Point]::new(44, 16)
))
$graphics.FillPath($fold, $foldPath)
$graphics.DrawLines($outline, [System.Drawing.Point[]]@(
    [System.Drawing.Point]::new(44, 5),
    [System.Drawing.Point]::new(44, 16),
    [System.Drawing.Point]::new(55, 16)
))

$graphics.DrawLine($linePen, 20, 28, 47, 28)
$graphics.DrawLine($linePen, 20, 38, 47, 38)
$graphics.DrawLine($linePen, 20, 48, 39, 48)

$outputDirectory = Split-Path -Parent $OutputPath
[System.IO.Directory]::CreateDirectory($outputDirectory) | Out-Null
$icon = [System.Drawing.Icon]::FromHandle($bitmap.GetHicon())
$stream = [System.IO.File]::Create($OutputPath)
try {
    $icon.Save($stream)
}
finally {
    $stream.Dispose()
    $icon.Dispose()
    $foldPath.Dispose()
    $page.Dispose()
    $linePen.Dispose()
    $fold.Dispose()
    $paper.Dispose()
    $outline.Dispose()
    $graphics.Dispose()
    $bitmap.Dispose()
}

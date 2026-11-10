<#
.SYNOPSIS
    Build a Windows .ico from assets\mp_liquid_glass_icon.png.

The tray and desktop shortcuts both use that image. Windows notification
icons and .lnk files need a real icon file, so this writes
assets\mp_liquid_glass_icon.ico from the PNG whenever the PNG is newer.
#>

function Get-MpLiquidGlassIconPath {
    param([Parameter(Mandatory = $true)][string]$InstallRoot)

    $png = Join-Path $InstallRoot "assets\mp_liquid_glass_icon.png"
    $ico = Join-Path $InstallRoot "assets\mp_liquid_glass_icon.ico"
    $fallback = Join-Path $InstallRoot "assets\MP_Mix_Manager_Windows_Icon.ico"

    if (-not (Test-Path -LiteralPath $png)) {
        if (Test-Path -LiteralPath $fallback) { return $fallback }
        return ""
    }

    $pngTime = (Get-Item -LiteralPath $png).LastWriteTimeUtc
    $fresh = $false
    if (Test-Path -LiteralPath $ico) {
        $fresh = (Get-Item -LiteralPath $ico).LastWriteTimeUtc -ge $pngTime
    }
    if ($fresh) { return $ico }

    if (-not ("MpLiquidGlassIcon" -as [type])) {
        Add-Type -AssemblyName System.Drawing
        $drawing = [System.Drawing.Bitmap].Assembly.Location
        Add-Type -ReferencedAssemblies $drawing -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;

public static class MpLiquidGlassIcon {
    public static void Save(string pngPath, string icoPath) {
        int[] sizes = new int[] { 16, 24, 32, 48, 64, 256 };
        using (Bitmap source = new Bitmap(pngPath)) {
            var images = new List<byte[]>();
            foreach (int size in sizes) {
                images.Add(BmpIconImage(source, size));
            }
            string folder = Path.GetDirectoryName(icoPath);
            if (!string.IsNullOrEmpty(folder)) Directory.CreateDirectory(folder);
            using (var fs = new FileStream(icoPath, FileMode.Create, FileAccess.Write))
            using (var bw = new BinaryWriter(fs)) {
                bw.Write((ushort)0);
                bw.Write((ushort)1);
                bw.Write((ushort)images.Count);
                int offset = 6 + (16 * images.Count);
                for (int i = 0; i < images.Count; i++) {
                    int size = sizes[i];
                    byte dim = (byte)(size >= 256 ? 0 : size);
                    bw.Write(dim);
                    bw.Write(dim);
                    bw.Write((byte)0);
                    bw.Write((byte)0);
                    bw.Write((ushort)1);
                    bw.Write((ushort)32);
                    bw.Write(images[i].Length);
                    bw.Write(offset);
                    offset += images[i].Length;
                }
                foreach (byte[] image in images) bw.Write(image);
            }
        }
    }

    static byte[] BmpIconImage(Bitmap source, int size) {
        using (var bmp = new Bitmap(size, size, PixelFormat.Format32bppArgb)) {
            using (var g = Graphics.FromImage(bmp))
            using (var attrs = new ImageAttributes()) {
                g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                g.SmoothingMode = SmoothingMode.HighQuality;
                g.PixelOffsetMode = PixelOffsetMode.HighQuality;
                g.CompositingQuality = CompositingQuality.HighQuality;
                g.Clear(Color.Transparent);
                attrs.SetWrapMode(WrapMode.TileFlipXY);
                g.DrawImage(
                    source,
                    new Rectangle(0, 0, size, size),
                    0, 0, source.Width, source.Height,
                    GraphicsUnit.Pixel,
                    attrs);
            }
            var rect = new Rectangle(0, 0, size, size);
            BitmapData data = bmp.LockBits(rect, ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
            try {
                int stride = data.Stride;
                byte[] pixels = new byte[Math.Abs(stride) * size];
                Marshal.Copy(data.Scan0, pixels, 0, pixels.Length);
                int maskRow = ((size + 31) / 32) * 4;
                int xorSize = size * size * 4;
                int maskSize = maskRow * size;
                byte[] image = new byte[40 + xorSize + maskSize];
                WriteInt(image, 0, 40);
                WriteInt(image, 4, size);
                WriteInt(image, 8, size * 2);
                WriteShort(image, 12, 1);
                WriteShort(image, 14, 32);
                WriteInt(image, 20, xorSize + maskSize);
                int xor = 40;
                int mask = 40 + xorSize;
                for (int y = 0; y < size; y++) {
                    int srcY = size - 1 - y;
                    for (int x = 0; x < size; x++) {
                        int si = srcY * stride + x * 4;
                        int di = xor + (y * size + x) * 4;
                        byte alpha = pixels[si + 3];
                        image[di] = pixels[si];
                        image[di + 1] = pixels[si + 1];
                        image[di + 2] = pixels[si + 2];
                        image[di + 3] = alpha;
                        if (alpha < 128) {
                            image[mask + y * maskRow + (x / 8)] |= (byte)(0x80 >> (x % 8));
                        }
                    }
                }
                return image;
            } finally {
                bmp.UnlockBits(data);
            }
        }
    }

    static void WriteInt(byte[] buffer, int index, int value) {
        buffer[index] = (byte)value;
        buffer[index + 1] = (byte)(value >> 8);
        buffer[index + 2] = (byte)(value >> 16);
        buffer[index + 3] = (byte)(value >> 24);
    }

    static void WriteShort(byte[] buffer, int index, int value) {
        buffer[index] = (byte)value;
        buffer[index + 1] = (byte)(value >> 8);
    }
}
'@
    }

    $temporary = "$ico.tmp"
    try {
        [MpLiquidGlassIcon]::Save($png, $temporary)
        [System.IO.File]::Copy($temporary, $ico, $true)
    } finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
        }
    }
    if (Test-Path -LiteralPath $ico) { return $ico }
    if (Test-Path -LiteralPath $fallback) { return $fallback }
    return ""
}

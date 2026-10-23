#!/usr/bin/env python3
"""
MP Mix Manager v0.3.7 Beta - Ultra-High-Performance YouTube Shorts Promo Generator
Generates a 1080x1920 vertical video (42s) showcasing major features with Dreamworlds
neon visuals, optimized for low-spec systems via cached canvases & hardware acceleration.
"""
import argparse, glob, os, subprocess, tempfile, time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

def _get_app_version() -> str:
    ver = os.environ.get("VERSION")
    if ver:
        return ver.strip()
    s_dir = Path(__file__).resolve().parent
    for cand in [s_dir / "VERSION", s_dir.parent / "VERSION"]:
        if cand.is_file():
            try:
                return cand.read_text(encoding="utf-8").strip()
            except Exception:
                pass
    return "0.4.0 Stable"

VERSION = _get_app_version()

W, H, FPS, DUR = 1080, 1920, 30, 42.0
BG, CARD, BORDER = (13, 15, 24), (21, 25, 40), (45, 53, 85)
PINK, CYAN, GOLD, WHITE, DIM = (247, 37, 133), (0, 229, 255), (255, 170, 0), (245, 247, 250), (140, 155, 185)


def get_font_factory():
    paths = [
        "/usr/share/fonts/google-noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/gnu-free/FreeSansBold.ttf",
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
    ]
    p = next((x for x in paths if os.path.isfile(x)), None) or next(
        iter(glob.glob("/usr/share/fonts/**/NotoSans*Bold*.ttf", recursive=True)), None
    )
    return (lambda sz: ImageFont.truetype(p, sz)) if p else (lambda sz: ImageFont.load_default())


def make_base_canvas():
    """Renders base background glow once to eliminate redundant blur overhead on slow CPUs."""
    im = Image.new("RGB", (W, H), BG)
    o = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(o)
    d.ellipse([W - 300, -100, W + 400, 600], fill=(247, 37, 133, 40))
    d.ellipse([-200, H - 700, 500, H + 100], fill=(0, 229, 255, 35))
    d.ellipse([W // 2 - 250, H // 2 - 250, W // 2 + 250, H // 2 + 250], fill=(155, 89, 182, 25))
    g = o.filter(ImageFilter.GaussianBlur(120))
    im.paste(g, (0, 0), g)
    return im


def round_box(draw, box, r, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def build_slides(tmpdir, cover_path):
    fn = get_font_factory()
    f_badge, f_t1, f_t2, f_bld, f_reg, f_cap = fn(24), fn(56), fn(48), fn(36), fn(26), fn(22)
    base = make_base_canvas()
    slides = []

    def paste_cover(im, box, sz):
        if cover_path and os.path.isfile(cover_path):
            try:
                cov = Image.open(cover_path).convert("RGB").resize(sz, Image.Resampling.LANCZOS)
                im.paste(cov, box)
            except Exception:
                pass

    # Slide 0: Hook & Overview
    im0 = base.copy()
    d0 = ImageDraw.Draw(im0)
    round_box(d0, [W // 2 - 240, 140, W // 2 + 240, 200], 30, (PINK[0], PINK[1], PINK[2], 50), PINK, 2)
    d0.text((W // 2, 170), f"🔥 MAJOR RELEASE • v{VERSION}", font=f_badge, fill=PINK, anchor="mm")
    d0.text((W // 2, 280), "MP MIX ARCHIVE", font=f_t1, fill=WHITE, anchor="mm")
    d0.text((W // 2, 360), "MANAGER", font=f_t1, fill=CYAN, anchor="mm")
    d0.text((W // 2, 430), "THE ULTIMATE DJ & AUDIO WORKSTATION", font=f_cap, fill=DIM, anchor="mm")
    round_box(d0, [W // 2 - 312, 508, W // 2 + 312, 1132], 28, CARD, PINK, 4)
    paste_cover(im0, (W // 2 - 300, 520), (600, 600))
    round_box(d0, [80, 1200, W - 80, 1680], 32, CARD, BORDER, 2)
    callouts = [
        ("⚡ <20ms Instant TUI Navigation", CYAN),
        ("🔍 Auto-ID Unknown Tracks (Shazam/AcoustID)", PINK),
        ("📼 1-Click YouTube Chapters & Rekordbox XML", GOLD),
        ("🎛️ Mastering Health & True-Peak Audit", CYAN),
        ("📱 DJ Booth Mobile Web Companion", PINK),
    ]
    for i, (txt, col) in enumerate(callouts):
        d0.text((120, 1270 + i * 84), txt, font=f_bld, fill=col, anchor="lm")
    d0.text((W // 2, 1780), "7 POWERFUL NEW FEATURES IN THIS UPDATE", font=f_cap, fill=DIM, anchor="mm")
    p0 = os.path.join(tmpdir, "slide_0.png")
    im0.save(p0)
    slides.append(p0)

    # Slides 1-5: Detailed Feature Showcases
    features = [
        ("⚡ SPEED & NAVIGATION", "BLISTERING PERFORMANCE", "<20ms Instant TUI", [
            ("Zero Latency Menus", "Refreshes in under 20ms instead of 1.7s", CYAN),
            ("Cached Archive Telemetry", "Instant multi-drive scans without FUSE bottlenecks", PINK),
            ("24-Bit TrueColor Theme", "Hand-crafted MPlanetarian Dreamworlds palette", GOLD),
            ("Keyboard Fluidity", "Seamless Arrow, Enter & Esc navigation across all menus", CYAN)]),
        ("🔍 AUDIO INTELLIGENCE", "AUTO-ID TRACKS", "AcoustID & Shazam", [
            ("Mix Transition Slicing", "Probes audio snippets at transition cue points", CYAN),
            ("Resolve Unknown IDs", "Automatically identifies 'ID - ID' mystery tracks", PINK),
            ("Draft Tracklist Generation", "Exports timestamped text tracklists with one click", GOLD),
            ("Red Book CUE Alignment", "Ready to burn or split into individual lossless tracks", CYAN)]),
        ("📼 STREAMING & CDJ EXPORT", "YOUTUBE CHAPTERS", "& Rekordbox XML Export", [
            ("YouTube Video Chapters", "Exact format (00:00:00 Artist - Title) ready for uploads", CYAN),
            ("SoundCloud & Mixcloud", "Formatted descriptions with duration validation", PINK),
            ("Pioneer Rekordbox XML", "Converts Traktor / M3U into standard rekordbox.xml", GOLD),
            ("CDJ Stage Prep", "Load ascending harmonic keys straight onto USB drives", CYAN)]),
        ("🎛️ AUDIO MASTERING AUDIT", "STUDIO HEALTH CHECK", "True Peak & Phase Analysis", [
            ("True Peak (ISP) Check", "Flags clipping distortion before lossy MP3 encoding", CYAN),
            ("Stereo Phase Correlation", "Guarantees mono compatibility on club sound systems", PINK),
            ("EBU R128 Loudness Audit", "Integrated LUFS & LRA dynamic range measurement", GOLD),
            ("Silence Trimming Detection", "Detects dead air at start/end of sets automatically", CYAN)]),
        ("📱 WIRELESS DJ BOOTH REMOTE", "MOBILE WEB COMPANION", "Phone & Tablet Control", [
            ("Local LAN Dashboard", "Accessible on port 8888 from phone or tablet", CYAN),
            ("Live Track Information", "Now-playing track title, artist & elapsed playback time", PINK),
            ("Wireless Transport Controls", "Play, Pause, Next & Previous right from the DJ booth", GOLD),
            ("Zero Dependencies", "Lightweight Python HTTP server — no bloated installs", CYAN)])
    ]
    for idx, (badge, t1, t2, items) in enumerate(features, start=1):
        im = base.copy()
        d = ImageDraw.Draw(im)
        round_box(d, [W // 2 - 240, 150, W // 2 + 240, 215], 32, (CYAN[0], CYAN[1], CYAN[2], 40), CYAN, 2)
        d.text((W // 2, 182), badge, font=f_badge, fill=CYAN, anchor="mm")
        d.text((W // 2, 290), t1, font=f_t1, fill=WHITE, anchor="mm")
        d.text((W // 2, 360), t2, font=f_t2, fill=PINK, anchor="mm")
        round_box(d, [80, 460, W - 80, 1640], 36, CARD, BORDER, 2)
        y = 540
        for h, det, col in items:
            d.ellipse([120, y + 8, 144, y + 32], fill=col)
            d.text((170, y + 20), h, font=f_bld, fill=WHITE, anchor="lm")
            d.text((170, y + 70), det, font=f_reg, fill=DIM, anchor="lm")
            d.line([120, y + 150, W - 120, y + 150], fill=(35, 42, 65), width=1)
            y += 180
        d.text((W // 2, 1760), "MPlanetarian • Stream of Frequency Edition", font=f_cap, fill=DIM, anchor="mm")
        p = os.path.join(tmpdir, f"slide_{idx}.png")
        im.save(p)
        slides.append(p)

    # Slide 6: Outro & Download CTA
    im6 = base.copy()
    d6 = ImageDraw.Draw(im6)
    round_box(d6, [W // 2 - 200, 160, W // 2 + 200, 225], 32, (GOLD[0], GOLD[1], GOLD[2], 40), GOLD, 2)
    d6.text((W // 2, 192), "🚀 AVAILABLE NOW", font=f_badge, fill=GOLD, anchor="mm")
    d6.text((W // 2, 310), "MP MIX MANAGER", font=f_t1, fill=WHITE, anchor="mm")
    d6.text((W // 2, 390), f"VERSION {VERSION.upper()}", font=f_t1, fill=CYAN, anchor="mm")
    round_box(d6, [W // 2 - 290, 470, W // 2 + 290, 1050], 24, CARD, PINK, 3)
    paste_cover(im6, (W // 2 - 280, 480), (560, 560))
    round_box(d6, [80, 1120, W - 80, 1680], 32, CARD, BORDER, 2)
    platforms = [
        ("🐧 Linux Native", "Bazzite • Fedora • SteamOS • Ubuntu"),
        ("🍏 Apple macOS", "Sonoma • Sequoia • Apple Silicon M1-M4 & Intel"),
        ("🪟 Windows 10 & 11", "PowerShell • WSL2 • Git Bash"),
        ("💯 100% Free & Open Source", "Enterprise-grade DJ mix management & archiving"),
    ]
    for i, (plat, desc) in enumerate(platforms):
        y = 1180 + i * 125
        d6.text((120, y + 15), plat, font=f_bld, fill=CYAN, anchor="lm")
        d6.text((120, y + 60), desc, font=f_reg, fill=DIM, anchor="lm")
    d6.text((W // 2, 1780), "Like & Subscribe • youtube.com/@mplanetarian", font=f_bld, fill=PINK, anchor="mm")
    p6 = os.path.join(tmpdir, "slide_6.png")
    im6.save(p6)
    slides.append(p6)
    return slides


def encode_video(slides, audio, out_path, dur=42.0):
    try:
        encs = subprocess.check_output(["ffmpeg", "-encoders"], stderr=subprocess.DEVNULL).decode('utf-8', 'ignore')
        nv = "h264_nvenc" in encs
    except Exception:
        nv = False

    vc = "h264_nvenc" if nv else "libx264"
    print(f"[•] Video Encoder: {vc}")
    tmpdir = os.path.dirname(slides[0])
    seg_dur = dur / len(slides)
    segs = []

    print(f"[•] Rendering {len(slides)} vertical slide segments ({seg_dur:.1f}s each)...")
    for idx, s in enumerate(slides):
        sp = os.path.join(tmpdir, f"seg_{idx}.mp4")
        cmd = ["ffmpeg", "-y", "-loop", "1", "-t", str(seg_dur), "-i", s, "-c:v", vc, "-pix_fmt", "yuv420p", "-r", str(FPS)]
        cmd.extend(["-preset", "p4", "-cq", "20", "-b:v", "8M"] if nv else ["-preset", "veryfast", "-crf", "20"])
        cmd.append(sp)
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        segs.append(sp)

    clist = os.path.join(tmpdir, "concat.txt")
    with open(clist, "w") as f:
        f.write("".join(f"file '{x}'\n" for x in segs))

    v_merged = os.path.join(tmpdir, "merged.mp4")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", clist, "-c", "copy", v_merged],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    print(f"[•] Muxing and fading audio (Duration: {dur}s)...")
    afade = f"afade=t=in:ss=0:d=1.5,afade=t=out:st={dur - 2.5}:d=2.5"
    if audio and os.path.isfile(audio):
        cmd = ["ffmpeg", "-y", "-i", v_merged, "-ss", "60", "-t", str(dur), "-i", audio,
               "-map", "0:v:0", "-map", "1:a:0", "-dn", "-map_metadata", "-1", "-af", afade,
               "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart", "-shortest", out_path]
    else:
        cmd = ["ffmpeg", "-y", "-i", v_merged, "-f", "lavfi", "-t", str(dur), "-i", "sine=frequency=440:sample_rate=44100",
               "-map", "0:v:0", "-map", "1:a:0", "-dn", "-af", afade,
               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out_path]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def main():
    p = argparse.ArgumentParser(description=f"Generate YouTube Shorts Promo Video for MP Mix Manager v{VERSION}")
    p.add_argument("--audio", "-a", default="/run/media/mplanetarian/DATA/Sensorium Interface/MPlanetarian - Stream of Frequency 074.wav")
    p.add_argument("--cover", "-c", default="Cover.png")
    p.add_argument("--output", "-o", default=f"MP_Mix_Manager_v{VERSION.replace(' ', '_')}_New_Features_YouTube_Short.mp4")
    args = p.parse_args()

    cover = args.cover if os.path.isfile(args.cover) else ("assets/Cover.png" if os.path.isfile("assets/Cover.png") else "")
    out_abs = os.path.abspath(args.output)
    t0 = time.time()
    print("\n======================================================================")
    print("  🎥 YOUTUBE SHORTS PROMO GENERATOR (1080x1920 VERTICAL)")
    print(f"  MPlanetarian Dreamworlds Edition • MP Mix Archive Manager v{VERSION}")
    print("======================================================================\n")
    with tempfile.TemporaryDirectory() as td:
        print("[•] Step 1: Generating high-resolution vertical Dreamworlds slide graphics...")
        slides = build_slides(td, cover)
        print("[•] Step 2: Assembling 42-second YouTube Shorts video with hardware acceleration...")
        encode_video(slides, args.audio, out_abs, dur=DUR)

    elapsed = time.time() - t0
    print(f"\n[✓] Render completed in {elapsed:.1f}s!\n[•] Output File: {out_abs}")
    if os.path.isfile(out_abs):
        print(f"[•] File Size:   {os.path.getsize(out_abs) / (1024 * 1024):.2f} MB")
        print("[•] Resolution:  1080x1920 (9:16 Vertical YouTube Shorts / TikTok / Reels)")
        print("[•] Audio:       320 kbps AAC Stereo with smooth studio fades\n")


if __name__ == "__main__":
    main()

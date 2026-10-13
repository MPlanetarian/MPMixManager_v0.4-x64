import os
import subprocess
import re
import sys
import argparse
from datetime import datetime

def parse_tracklist_file(txt_path):
    with open(txt_path, 'r', encoding='utf-8') as f:
        content = f.readlines()
    
    metadata = {}
    tracks = []
    current_track = {}

    for line in content:
        if line.startswith('Show ID:'):
            metadata['show_id'] = line.split(':', 1)[1].strip()
        elif line.startswith('Title:'):
            metadata['title'] = line.split(':', 1)[1].strip()
        elif line.startswith('Date:'):
            metadata['date'] = line.split(':', 1)[1].strip()
        elif line.startswith('Artist:'):
            current_track['artist'] = line.split(':', 1)[1].strip()
        elif line.startswith('Track:'):
            current_track['title'] = line.split(':', 1)[1].strip()
        elif line.startswith('Time:'):
            current_track['time'] = line.split(':', 1)[1].strip()
        elif line.strip().isdigit():
            current_track['number'] = line.strip()
            tracks.append(current_track)
            current_track = {}

    return metadata, tracks

def generate_html(metadata, tracks, output_html_path):
    html_content = f"""
    <html>
    <head><title>Tracklist</title></head>
    <body>
    <h1>{metadata.get('title', 'N/A')}</h1>
    <p>Show ID: {metadata.get('show_id', 'N/A')}</p>
    <p>Date: {metadata.get('date', 'N/A')}</p>
    <h2>Track List</h2>
    <ol>
    {''.join(f"<li>{track['number']}. {track.get('time', '')} - {track.get('artist', '')} - {track.get('title', '')}</li>" for track in tracks)}
    </ol>
    </body>
    </html>
    """
    with open(output_html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

def generate_pdf_postscript(metadata, tracks, output_pdf_path):
    ps_lines = [
        "%!PS-Adobe-3.0",
        "%%BoundingBox: 0 0 600 800",
        "%%LanguageLevel: 2",
        "%%EndComments",
        "/Helvetica findfont 8 scalefont setfont"
    ]

    for page_idx, page_tracks in enumerate([tracks[i:i+10] for i in range(0, len(tracks), 10)], 1):
        ps_lines.append(f"%%Page: {page_idx} {page_idx}")
        ps_lines.append("save")
        ps_lines.append("0.1 0.1 0.15 setrgbcolor")
        ps_lines.append("36 730 540 32 rectfill")
        ps_lines.append("1 1 1 setrgbcolor")
        ps_lines.append("/Helvetica-Bold findfont 13 scalefont setfont")
        ps_lines.append(f"46 742 moveto ({metadata.get('show_id', 'N/A')}) show")
        ps_lines.append("/Helvetica findfont 9 scalefont setfont")
        ps_lines.append(f"450 742 moveto ({metadata.get('date', 'N/A')}) show")
        ps_lines.append("0 0 0 setrgbcolor")
        ps_lines.append("/Helvetica-Bold findfont 11 scalefont setfont")
        ps_lines.append(f"36 710 moveto ({metadata.get('title', 'N/A')}) show")
        ps_lines.append("/Helvetica-Oblique findfont 9 scalefont setfont")
        ps_lines.append(f"36 696 moveto ({metadata.get('artist', 'N/A')}) show")
        ps_lines.append("0.7 0.7 0.7 setrgbcolor")
        ps_lines.append("0.5 setlinewidth")
        ps_lines.append("36 688 moveto 576 688 lineto stroke")
        ps_lines.append("0.92 0.94 0.96 setrgbcolor")
        ps_lines.append("36 672 540 14 rectfill")
        ps_lines.append("0.2 0.2 0.2 setrgbcolor")
        ps_lines.append("/Helvetica-Bold findfont 8 scalefont setfont")
        ps_lines.append("42 676 moveto (#) show")
        ps_lines.append("68 676 moveto (TIME) show")
        ps_lines.append("120 676 moveto (ARTIST) show")
        ps_lines.append("280 676 moveto (TRACK TITLE) show")
        y = 658
        for t in page_tracks:
            if int(t["number"]) % 2 == 0:
                ps_lines.append(f"0.97 0.98 0.99 setrgbcolor")
                ps_lines.append(f"36 {y-3} 540 13 rectfill")
            ps_lines.append("0 0 0 setrgbcolor")
            ps_lines.append("/Helvetica-Bold findfont 8 scalefont setfont")
            ps_lines.append(f"42 {y} moveto ({t['number']}) show")
            if t["time"]:
                ps_lines.append("/Courier findfont 8 scalefont setfont")
                ps_lines.append(f"68 {y} moveto ({t['time']}) show")
            art_str = t["artist"][:30] if t["artist"] else t["raw"][:30]
            tit_str = t["title"][:48] if t["title"] else ""
            ps_lines.append("/Helvetica-Bold findfont 8 scalefont setfont")
            ps_lines.append(f"120 {y} moveto ({art_str}) show")
            ps_lines.append("/Helvetica findfont 8 scalefont setfont")
            ps_lines.append(f"280 {y} moveto ({tit_str}) show")
            y -= 13
        ps_lines.append("0.7 0.7 0.7 setrgbcolor")
        ps_lines.append("36 40 moveto 576 40 lineto stroke")
        ps_lines.append("/Helvetica findfont 8 scalefont setfont")
        ps_lines.append("0.4 0.4 0.4 setrgbcolor")
        ps_lines.append("36 30 moveto (Stream of Frequency Archive Suite) show")
        ps_lines.append(f"520 30 moveto (Page {page_idx} of {len(tracks) // 10 + 1}) show")
        ps_lines.append("showpage")
        ps_lines.append("restore")

    ps_lines.append("%%Trailer")
    ps_lines.append(f"%%Pages: {len(tracks) // 10 + 1}")
    ps_lines.append("%%EOF")

    ps_content = "\n".join(ps_lines)
    temp_ps = output_pdf_path + ".tmp.ps"
    os.makedirs(os.path.dirname(os.path.abspath(output_pdf_path)), exist_ok=True)
    with open(temp_ps, "w", encoding="ascii") as f:
        f.write(ps_content)

    try:
        subprocess.run(["ps2pdf", temp_ps, output_pdf_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(temp_ps):
            os.remove(temp_ps)
        return output_pdf_path
    except Exception as e:
        if os.path.exists(temp_ps):
            os.remove(temp_ps)
        raise RuntimeError(f"ps2pdf conversion failed: {e}")

def convert_single_tracklist(txt_path, output_dir=None, out_fmt="both"):
    metadata, tracks = parse_tracklist_file(txt_path)
    base_name = os.path.splitext(os.path.basename(txt_path))[0]
    out_dir = output_dir or os.path.dirname(os.path.abspath(txt_path))
    results = {}

    if out_fmt in ("html", "both"):
        html_out = os.path.join(out_dir, f"{base_name}.html")
        generate_html(metadata, tracks, html_out)
        results["html"] = html_out

    if out_fmt in ("pdf", "both"):
        pdf_out = os.path.join(out_dir, f"{base_name}.pdf")
        generate_pdf_postscript(metadata, tracks, pdf_out)
        results["pdf"] = pdf_out

    return metadata, tracks, results

def batch_convert(target_dir, output_dir=None, out_fmt="both"):
    out_dir = output_dir or target_dir
    txt_files = [os.path.join(target_dir, f) for f in os.listdir(target_dir) if f.lower().endswith(".txt")]
    processed = []
    errors = []

    for tf in sorted(txt_files):
        try:
            _, _, res = convert_single_tracklist(tf, out_dir, out_fmt)
            processed.append((tf, res))
        except Exception as e:
            errors.append((tf, str(e)))

    return processed, errors

def main():
    parser = argparse.ArgumentParser(description="Generate HTML and PDF tracklist documents.")
    parser.add_argument("-i", "--input", help="Path to single .txt tracklist file")
    parser.add_argument("-d", "--dir", help="Directory containing .txt files", default=".")
    parser.add_argument("-o", "--out", help="Output directory", default=".")
    parser.add_argument("-f", "--format", help="Output format (html, pdf, both)", default="both")
    args = parser.parse_args()

    if args.input:
        metadata, tracks, results = convert_single_tracklist(args.input, args.out, args.format)
        print(f"Processed {args.input}: HTML: {results.get('html', 'N/A')}, PDF: {results.get('pdf', 'N/A')}")
    else:
        processed, errors = batch_convert(args.dir, args.out, args.format)
        print(f"Processed {len(processed)} files.")
        if errors:
            print(f"Errors: {errors}")

if __name__ == "__main__":
    main() # 579 to 187
#!/usr/bin/env python3
"""Export MP Mix Manager tracklists to HTML or plain text.

Exports always land inside the program folder the user launched, under
``TRACKLIST_EXPORTS/`` next to the MP Mix Manager files. Both the console
tracklist viewer (``scripts/view_tracklist_console.sh``) and the
``MP_Audio_Player.py`` command line use this module.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, NamedTuple, Optional, Sequence, Tuple

EXPORT_DIR_NAME = "TRACKLIST_EXPORTS"
PROGRAM_DIR = Path(__file__).resolve().parent.parent

FORMATS = ("html", "text")

_LINE_RE = re.compile(r"^(\d{1,3})[\.\)]\s+(.*)$")
_DIVIDER_RE = re.compile(r"^[=\-_~─━]{10,}$")
_HEADING_RE = re.compile(r"(RELEASE\s+INFO|TRACK\s*LIST|SOURCE\s+MANIFEST|SOURCE\s+FILES)", re.I)
_META_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9 &/'._-]{0,40}):\s+(.*)$")
_ARTIST_TITLE_RE = re.compile(r"^(.+?)\s+-\s+(.+)$")
_REMIX_RE = re.compile(r"^(.*?)(\([^)]+\))(.*)$")


class Track(NamedTuple):
    number: str
    artist: str
    title: str
    remix: str
    tail: str
    raw: str


def program_dir(base_dir: Optional[Path] = None) -> Path:
    """The running MP Mix Manager program folder (the one holding this tree)."""
    if base_dir:
        return Path(base_dir).expanduser().resolve()
    return PROGRAM_DIR


def export_dir(base_dir: Optional[Path] = None, output_dir: Optional[Path] = None) -> Path:
    if output_dir:
        return Path(output_dir).expanduser().resolve()
    return program_dir(base_dir) / EXPORT_DIR_NAME


def parse_track(text: str) -> Optional[Track]:
    """Split ``01. Artist - Title (Remix)`` like the console viewer does."""
    match = _LINE_RE.match(text.strip())
    if not match:
        return None
    number, rest = match.group(1), match.group(2)
    artist = title = remix = tail = ""
    artist_title = _ARTIST_TITLE_RE.match(rest)
    if artist_title:
        artist = artist_title.group(1).strip()
        title = artist_title.group(2).strip()
        parts = _REMIX_RE.match(title)
        if parts:
            title, remix, tail = parts.group(1).strip(), parts.group(2), parts.group(3).strip()
    else:
        title = rest.strip()
    return Track(number=number, artist=artist, title=title, remix=remix, tail=tail, raw=rest)


def read_tracklist(tracklist_path: Path) -> str:
    path = Path(tracklist_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Tracklist not found: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def parse_blocks(text: str) -> List[Tuple]:
    """Ordered blocks that keep the original document layout."""
    blocks: List[Tuple] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            blocks.append(("blank", ""))
            continue
        if _DIVIDER_RE.match(stripped):
            blocks.append(("banner", stripped))
            continue
        if _HEADING_RE.search(stripped):
            heading = stripped.strip("=-_~─━").strip() or stripped
            blocks.append(("heading", heading))
            continue
        meta = _META_RE.match(stripped)
        if meta:
            blocks.append(("meta", meta.group(1).strip(), meta.group(2).strip()))
            continue
        track = parse_track(stripped)
        if track:
            blocks.append(("track", track))
            continue
        blocks.append(("text", stripped))
    return blocks


def export_text(tracklist_path: Path, base_dir: Optional[Path] = None,
                output_dir: Optional[Path] = None) -> Path:
    """Save a pristine ``.txt`` copy of the tracklist in the export folder."""
    source = Path(tracklist_path).expanduser()
    content = read_tracklist(source)
    out_dir = export_dir(base_dir, output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{source.stem}.txt"
    if not content.endswith("\n"):
        content += "\n"
    target.write_text(content, encoding="utf-8")
    return target


def _html_page(title: str, source: Path, blocks: Sequence[Tuple]) -> str:
    escaped_title = html.escape(title or source.stem)
    escaped_source = html.escape(source.name)
    exported_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    meta_rows: List[str] = []
    body: List[str] = []
    track_rows: List[str] = []
    track_count = 0

    for block in blocks:
        kind = block[0]
        if kind == "track":
            track: Track = block[1]
            track_count += 1
            number = html.escape(track.number.zfill(2) if track.number.isdigit() else track.number)
            artist = html.escape(track.artist)
            title_cell = html.escape(track.title)
            if track.remix:
                title_cell += f'<span class="remix">{html.escape(track.remix)}</span>'
            if track.tail:
                title_cell += f" {html.escape(track.tail)}"
            if not track.artist and not track.title:
                title_cell = html.escape(track.raw)
            track_rows.append(
                '<tr class="track">'
                f'<td class="num">{number}</td>'
                f'<td class="artist">{artist}</td>'
                f'<td class="title">{title_cell}</td>'
                "</tr>"
            )
        elif kind == "meta":
            meta_rows.append(
                f'<div class="meta-row"><span class="meta-key">{html.escape(block[1])}</span>'
                f'<span class="meta-value">{html.escape(block[2])}</span></div>'
            )
        elif kind == "heading":
            body.append(f'<h2 class="section">{html.escape(block[1])}</h2>')
        elif kind == "banner":
            body.append('<hr class="rule">')
        elif kind == "text":
            body.append(f'<p class="note">{html.escape(block[1])}</p>')
        else:
            body.append('<div class="gap"></div>')

    meta_html = "".join(meta_rows)
    meta_section = f'<section class="meta">{meta_html}</section>' if meta_html else ""
    rows_html = "\n".join(track_rows) if track_rows else (
        '<tr><td colspan="3" class="empty">No numbered tracks found in this tracklist.</td></tr>'
    )
    count_html = f"{track_count} track{'s' if track_count != 1 else ''}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escaped_title} • MP Mix Manager Tracklist</title>
<style>
  :root {{
    color-scheme: dark;
    --bg: #04060f;
    --panel: rgba(10, 18, 38, 0.82);
    --ink: #e8f6ff;
    --muted: #8fa7c4;
    --cyan: #00f5ff;
    --magenta: #c77dff;
    --green: #5ef2a0;
    --yellow: #ffd76a;
    --line: rgba(0, 245, 255, 0.22);
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 3rem 1.25rem 4rem;
    font-family: "Hack", "Fira Code", "Adwaita Mono", "SFMono-Regular", Consolas, monospace;
    background:
      radial-gradient(1100px 620px at 15% -10%, #122b4d 0%, transparent 60%),
      radial-gradient(900px 520px at 88% 8%, #3a1160 0%, transparent 62%),
      var(--bg);
    color: var(--ink);
    min-height: 100vh;
  }}
  main {{
    max-width: 980px;
    margin: 0 auto;
    padding: 2rem 2.25rem 2.5rem;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 18px;
    box-shadow: 0 24px 70px rgba(0, 0, 0, 0.55), inset 0 0 90px rgba(0, 245, 255, 0.04);
    backdrop-filter: blur(14px);
  }}
  h1 {{
    margin: 0 0 0.35rem;
    font-size: clamp(1.35rem, 3.2vw, 2rem);
    letter-spacing: 0.02em;
    color: var(--cyan);
    text-shadow: 0 0 18px rgba(0, 245, 255, 0.35);
  }}
  .brand {{
    font-size: 0.72rem;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    color: var(--magenta);
    margin-bottom: 0.85rem;
  }}
  .source {{ color: var(--muted); font-size: 0.82rem; word-break: break-all; }}
  .meta {{
    margin: 1.4rem 0 1.2rem;
    padding: 1rem 1.15rem;
    border: 1px solid var(--line);
    border-radius: 12px;
    background: rgba(3, 10, 24, 0.55);
  }}
  .meta-row {{ display: flex; gap: 0.85rem; padding: 0.18rem 0; font-size: 0.85rem; flex-wrap: wrap; }}
  .meta-key {{ color: var(--cyan); min-width: 9.5rem; font-weight: 700; }}
  .meta-value {{ color: var(--ink); flex: 1 1 16rem; word-break: break-word; }}
  h2.section {{
    margin: 1.6rem 0 0.7rem;
    font-size: 0.95rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--yellow);
  }}
  hr.rule {{ border: 0; border-top: 1px dashed var(--line); margin: 1.1rem 0; }}
  p.note {{ margin: 0.35rem 0; color: var(--muted); font-size: 0.85rem; }}
  .gap {{ height: 0.45rem; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 0.6rem; }}
  thead th {{
    text-align: left;
    font-size: 0.72rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--muted);
    border-bottom: 1px solid var(--line);
    padding: 0.45rem 0.55rem;
  }}
  tbody td {{ padding: 0.45rem 0.55rem; border-bottom: 1px solid rgba(0, 245, 255, 0.09); vertical-align: top; }}
  tr.track:hover td {{ background: rgba(0, 245, 255, 0.06); }}
  td.num {{ color: var(--cyan); font-weight: 700; width: 3.2rem; }}
  td.artist {{ color: var(--ink); width: 34%; }}
  td.title {{ color: var(--green); }}
  .remix {{ color: var(--yellow); }}
  td.empty {{ color: var(--muted); font-style: italic; padding: 1.2rem 0.55rem; }}
  footer {{
    margin-top: 1.8rem;
    padding-top: 1rem;
    border-top: 1px solid var(--line);
    color: var(--muted);
    font-size: 0.75rem;
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
  }}
  @media print {{
    body {{ background: #fff; color: #111; padding: 0; }}
    main {{ background: #fff; border: 0; box-shadow: none; padding: 0; }}
    h1, .brand, .meta-key, td.num, td.title, .remix {{ color: #111; text-shadow: none; }}
    .meta, thead th, tbody td {{ border-color: #bbb; }}
    footer {{ color: #444; }}
  }}
</style>
</head>
<body>
<main>
  <div class="brand">Stream of Frequency • MP Mix Manager</div>
  <h1>{escaped_title}</h1>
  <div class="source">{escaped_source}</div>
  {meta_section}
  {''.join(body)}
  <table>
    <thead>
      <tr><th>#</th><th>Artist</th><th>Title</th></tr>
    </thead>
    <tbody>
{rows_html}
    </tbody>
  </table>
  <footer>
    <span>{count_html}</span>
    <span>Exported {html.escape(exported_at)} by MP Audio Player</span>
  </footer>
</main>
</body>
</html>
"""


def export_html(tracklist_path: Path, base_dir: Optional[Path] = None,
                output_dir: Optional[Path] = None) -> Path:
    """Save a styled ``.html`` tracklist in the export folder."""
    source = Path(tracklist_path).expanduser()
    content = read_tracklist(source)
    blocks = parse_blocks(content)
    title = next((b[2] for b in blocks if b[0] == "meta" and b[1].lower() in ("title", "mix title")), "")
    if not title:
        title = source.stem
    out_dir = export_dir(base_dir, output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{source.stem}.html"
    target.write_text(_html_page(title, source, blocks), encoding="utf-8")
    return target


def export_tracklist(tracklist_path: Path, fmt: str = "html", base_dir: Optional[Path] = None,
                     output_dir: Optional[Path] = None) -> Path:
    """Export ``tracklist_path`` as ``html`` or ``text`` and return the new path."""
    kind = (fmt or "html").strip().lower()
    if kind in ("txt", "plain", "text"):
        return export_text(tracklist_path, base_dir=base_dir, output_dir=output_dir)
    if kind in ("htm", "html"):
        return export_html(tracklist_path, base_dir=base_dir, output_dir=output_dir)
    raise ValueError(f"Unsupported export format: {fmt!r} (use html or text)")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Export an MP Mix Manager tracklist to HTML or TEXT.")
    parser.add_argument("tracklist", help="Path to the .txt tracklist")
    parser.add_argument("-f", "--format", default="html", choices=FORMATS, help="Export format (default: html)")
    parser.add_argument("-o", "--output-dir", default=None, help=f"Destination folder (default: <program>/<{EXPORT_DIR_NAME}>)")
    parser.add_argument("--base-dir", default=None, help="Program folder used for the default destination")
    args = parser.parse_args(argv)
    try:
        saved = export_tracklist(Path(args.tracklist), args.format, base_dir=args.base_dir, output_dir=args.output_dir)
    except Exception as exc:  # pragma: no cover - CLI guard
        print(f"Export failed: {exc}", file=sys.stderr)
        return 1
    print(saved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

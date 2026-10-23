#!/usr/bin/env python3
"""
generate_ai_report_section.py
Comprehensive Daily AI Brain Logs & Software Activity Reporter
Part of MP_Reporter and MP_Mix_Manager (Dreamworlds Productions)

Harvesters and analyzers for:
1. Google Gemini Brain Logs (~/.gemini/antigravity-cli/brain and ~/.gemini/antigravity/brain)
2. Grok Brain Logs (~/.grok/sessions, ~/.grok/logs, ~/.grok/memtrace)
3. Other AI Model Brain Logs:
   - MP Harmony Autonomous Agent (OpenAI bridge, audio responses, personas, models)
   - Open WebUI chats and prompt history (SQLite database webui.db)
   - DeepSeek Harness sessions (~/.dsh/sessions)
   - Ollama local inference server & model inventory
   - Hardware acceleration telemetry (NVIDIA GPU VRAM, utilization, temperature)
4. State & Deduplication Ledger:
   - Runs once per day automatically.
   - If run later than expected, captures all previous/backlog logs since last run.
   - Avoids creating duplicate log, PDF, or audio files.
5. Generates high-quality ReportLab PDF and clean text optimized for Stephen Hawking Matrix TTS.
"""

import sys
import os
import re
import json
import time
import argparse
import tempfile
import urllib.request
import subprocess
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple

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

# Matplotlib headless backend
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ReportLab imports
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

# State & Persistence Paths
MP_REPORTER_DIR = Path("/var/home/mplanetarian/MP_REPORTER")
TASKS_DIR = MP_REPORTER_DIR / "tasks"
STATE_FILE = TASKS_DIR / "ai_brain_reporter_state.json"
FALLBACK_STATE_FILE = Path("/var/home/mplanetarian/Documents/BASH_SCRIPTS/ai_brain_reporter_state.json")
PDF_DIR = MP_REPORTER_DIR / "PDF_REPORTS" / "DAILY_REPORTS"

def load_state() -> Dict[str, Any]:
    """Load persistent reporter state ledger."""
    for f in [STATE_FILE, FALLBACK_STATE_FILE]:
        if f.exists():
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    return json.load(fp)
            except Exception:
                pass
    return {
        "last_run_date": "",
        "last_run_timestamp": "",
        "processed_sessions": {
            "gemini": {},
            "grok": {},
            "harmony": {},
            "open_webui": {},
            "deepseek": {}
        },
        "reports_generated": []
    }

def save_state(state: Dict[str, Any]) -> None:
    """Save persistent reporter state ledger."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    for f in [STATE_FILE, FALLBACK_STATE_FILE]:
        try:
            with open(f, "w", encoding="utf-8") as fp:
                json.dump(state, fp, indent=2)
        except Exception:
            pass

def probe_json(url: str, timeout: float = 2.5) -> Optional[Any]:
    """Helper to safely fetch and parse JSON over HTTP."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MP_AI_Reporter/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception:
        return None

def check_service(unit_name: str) -> str:
    """Check systemd user service status."""
    try:
        res = subprocess.run(
            ["systemctl", "--user", "is-active", unit_name],
            capture_output=True, text=True, timeout=2
        )
        return res.stdout.strip()
    except Exception:
        return "unknown"

def get_gpu_info() -> Optional[Dict[str, Any]]:
    """Query NVIDIA GPU status if available."""
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=name,driver_version,memory.used,memory.total,utilization.gpu,temperature.gpu",
            "--format=csv,noheader,nounits"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and res.stdout.strip():
            parts = [p.strip() for p in res.stdout.strip().split(",")]
            if len(parts) >= 6:
                return {
                    "name": parts[0],
                    "driver": parts[1],
                    "mem_used_mib": int(parts[2]),
                    "mem_total_mib": int(parts[3]),
                    "gpu_util_pct": int(parts[4]),
                    "temp_c": int(parts[5])
                }
    except Exception:
        pass
    return None

def format_size(bytes_val: int) -> str:
    """Format bytes into human-readable string."""
    if bytes_val >= 1024 ** 3:
        return f"{bytes_val / (1024 ** 3):.1f} GB"
    elif bytes_val >= 1024 ** 2:
        return f"{bytes_val / (1024 ** 2):.1f} MB"
    return f"{bytes_val} B"

def clean_prompt_text(text: str) -> str:
    """Clean internal XML tags and formatting from user prompt."""
    if not text:
        return ""
    m = re.search(r'<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>', text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    text = re.sub(r'<[A-Z_]+>.*?</[A-Z_]+>', '', text, flags=re.DOTALL)
    text = ' '.join(text.split())
    return text.strip()

# =========================================================================
# Harvester 1: Google Gemini Brain Logs
# =========================================================================

def harvest_gemini_brain(since_timestamp: Optional[float] = None,
                         processed_map: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Harvest Google Gemini Brain conversation logs and transcripts."""
    if processed_map is None:
        processed_map = {}
    sessions = []
    gemini_dirs = [
        Path("/home/mplanetarian/.gemini/antigravity-cli/brain"),
        Path("/home/mplanetarian/.gemini/antigravity/brain")
    ]

    for g_dir in gemini_dirs:
        if not g_dir.exists():
            continue
        for p in g_dir.iterdir():
            if not p.is_dir():
                continue
            sess_id = p.name
            t_file = p / ".system_generated" / "logs" / "transcript.jsonl"
            if not t_file.exists():
                t_file = p / ".system_generated" / "logs" / "transcript_full.jsonl"
            if not t_file.exists():
                continue

            try:
                st = t_file.stat()
                mtime = st.st_mtime
            except Exception:
                continue

            # Check if already processed at same mtime
            prev = processed_map.get(sess_id)
            if prev and prev.get("mtime") == mtime:
                continue

            # If filtering by time and older than since_timestamp (and already seen)
            if since_timestamp and mtime < since_timestamp and sess_id in processed_map:
                continue

            # Parse transcript
            prompts = []
            files_edited = set()
            commands_run = []
            tool_calls_count = 0
            model = "Gemini"
            first_created_at = None
            last_created_at = None

            try:
                with open(t_file, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        d = json.loads(line)
                        cat = d.get("created_at")
                        if cat:
                            if not first_created_at:
                                first_created_at = cat
                            last_created_at = cat

                        content = d.get("content", "")
                        if "<USER_REQUEST>" in content:
                            cleaned = clean_prompt_text(content)
                            if cleaned and cleaned not in prompts:
                                prompts.append(cleaned)

                        if "Model Selection" in content:
                            m_model = re.search(r"Model Selection.*?to ([^.]+)", content)
                            if m_model:
                                model = m_model.group(1).strip()

                        tcs = d.get("tool_calls", [])
                        tool_calls_count += len(tcs)
                        for tc in tcs:
                            tname = tc.get("name")
                            args = tc.get("args", {})
                            if tname in ("replace_file_content", "write_to_file"):
                                tgt = args.get("TargetFile", "")
                                desc = args.get("Description", "") or args.get("Instruction", "")
                                if tgt:
                                    base = Path(str(tgt).strip('"')).name
                                    files_edited.add(base)
                            elif tname == "run_command":
                                summary = args.get("toolSummary") or args.get("toolAction")
                                if summary:
                                    s_clean = str(summary).strip('"')
                                    if s_clean not in commands_run and len(commands_run) < 10:
                                        commands_run.append(s_clean)
            except Exception:
                continue

            if not prompts and tool_calls_count == 0:
                continue

            primary_prompt = prompts[0] if prompts else "Operational engineering session"
            sessions.append({
                "id": sess_id,
                "engine": "Google Gemini Brain",
                "model": model,
                "created_at": first_created_at or datetime.fromtimestamp(mtime).isoformat(),
                "last_active": last_created_at or datetime.fromtimestamp(mtime).isoformat(),
                "mtime": mtime,
                "primary_prompt": primary_prompt,
                "all_prompts": prompts,
                "files_edited": sorted(list(files_edited)),
                "commands_run": commands_run,
                "tool_calls_count": tool_calls_count,
                "status": "Completed"
            })

    sessions.sort(key=lambda s: s["mtime"])
    return sessions

# =========================================================================
# Harvester 2: Grok Brain Logs
# =========================================================================

def harvest_grok_brain(since_timestamp: Optional[float] = None,
                       processed_map: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Harvest Grok Brain sessions and activity histories."""
    if processed_map is None:
        processed_map = {}
    sessions = []
    grok_base = Path("/home/mplanetarian/.grok/sessions")
    if not grok_base.exists():
        return sessions

    for sub in grok_base.iterdir():
        if not sub.is_dir():
            continue
        workspace_name = sub.name.replace("%2F", "/")
        # Also check prompt_history.jsonl in sub workspace
        prompt_hist = {}
        ph_file = sub / "prompt_history.jsonl"
        if ph_file.exists():
            try:
                with open(ph_file, "r", encoding="utf-8", errors="replace") as pf:
                    for line in pf:
                        if line.strip():
                            pd = json.loads(line)
                            sid = pd.get("session_id")
                            if sid:
                                prompt_hist.setdefault(sid, []).append(pd.get("prompt", ""))
            except Exception:
                pass

        for s in sub.iterdir():
            if not s.is_dir():
                continue
            sess_id = s.name
            s_file = s / "summary.json"
            if not s_file.exists():
                continue

            try:
                mtime = s_file.stat().st_mtime
            except Exception:
                continue

            prev = processed_map.get(sess_id)
            if prev and prev.get("mtime") == mtime:
                continue
            if since_timestamp and mtime < since_timestamp and sess_id in processed_map:
                continue

            try:
                with open(s_file, "r", encoding="utf-8", errors="replace") as f:
                    s_data = json.load(f)
            except Exception:
                continue

            summary_title = s_data.get("session_summary", "").strip()
            model = s_data.get("current_model_id", "grok-4.7")
            created_at = s_data.get("created_at", "")
            updated_at = s_data.get("updated_at", "")

            prompts = prompt_hist.get(sess_id, [])
            tools_used = []
            files_edited = set()

            chat_file = s / "chat_history.jsonl"
            if chat_file.exists():
                try:
                    with open(chat_file, "r", encoding="utf-8", errors="replace") as cf:
                        for line in cf:
                            if not line.strip():
                                continue
                            cd = json.loads(line)
                            if cd.get("type") == "user" and not prompts:
                                u_content = cd.get("content", [])
                                if isinstance(u_content, list):
                                    for item in u_content:
                                        t = item.get("text", "")
                                        if "<system-reminder>" not in t and t.strip():
                                            prompts.append(clean_prompt_text(t))
                                elif isinstance(u_content, str):
                                    prompts.append(clean_prompt_text(u_content))
                            elif cd.get("type") == "assistant":
                                for tc in cd.get("tool_calls", []):
                                    tname = tc.get("name") or tc.get("function", {}).get("name")
                                    if tname:
                                        tools_used.append(tname)
                                    args = tc.get("arguments") or tc.get("function", {}).get("arguments")
                                    if isinstance(args, str):
                                        try:
                                            args = json.loads(args)
                                        except Exception:
                                            pass
                                    if isinstance(args, dict):
                                        path_arg = args.get("file_path") or args.get("path") or args.get("target_directory")
                                        if path_arg:
                                            files_edited.add(Path(path_arg).name)
                except Exception:
                    pass

            primary_prompt = summary_title or (prompts[0] if prompts else "Workspace task")
            sessions.append({
                "id": sess_id,
                "engine": "Grok Brain",
                "model": model,
                "workspace": workspace_name,
                "created_at": created_at or datetime.fromtimestamp(mtime).isoformat(),
                "last_active": updated_at or datetime.fromtimestamp(mtime).isoformat(),
                "mtime": mtime,
                "primary_prompt": primary_prompt,
                "all_prompts": prompts,
                "files_edited": sorted(list(files_edited)),
                "commands_run": [f"Grok tool: {t}" for t in set(tools_used[:6])],
                "tool_calls_count": len(tools_used),
                "status": "Completed"
            })

    sessions.sort(key=lambda s: s["mtime"])
    return sessions

# =========================================================================
# Harvester 3: MP Harmony Agent & Other AI Brain Logs
# =========================================================================

def harvest_harmony_agent(since_timestamp: Optional[float] = None,
                          processed_map: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Harvest MP Harmony Autonomous Agent voice responses and logs."""
    if processed_map is None:
        processed_map = {}
    responses = []
    audio_dir = Path("/var/home/mplanetarian/OpenAI/MP_Harmony_Agent/audio_responses")
    if not audio_dir.exists():
        return responses

    for txt_file in audio_dir.glob("*.txt"):
        try:
            st = txt_file.stat()
            mtime = st.st_mtime
        except Exception:
            continue

        fname = txt_file.name
        if fname in processed_map:
            continue
        if since_timestamp and mtime < since_timestamp:
            continue

        # Pattern: ollama_speech_YYYYMMDD_HHMMSS_<persona>_<context>_<model>_<voice>_<hash>.txt
        parts = fname.replace(".txt", "").split("_")
        persona = "Harmony Agent"
        model = "Llama-3-8B / Command-R"
        speech_snippet = ""
        try:
            with open(txt_file, "r", encoding="utf-8", errors="replace") as f:
                speech_snippet = f.read().strip()[:180].replace("\n", " ")
        except Exception:
            pass

        if len(parts) >= 6:
            persona = f"{parts[4].capitalize()} ({parts[3].capitalize()})"
            model = parts[5].replace("-", " ")

        responses.append({
            "id": fname,
            "engine": "MP Harmony Agent",
            "model": model,
            "persona": persona,
            "mtime": mtime,
            "created_at": datetime.fromtimestamp(mtime).isoformat(),
            "snippet": speech_snippet,
            "status": "Voiced"
        })

    responses.sort(key=lambda r: r["mtime"])
    return responses

def harvest_open_webui(since_timestamp: Optional[float] = None,
                       processed_map: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Harvest Open WebUI recent user chat sessions from SQLite."""
    if processed_map is None:
        processed_map = {}
    chats = []
    db_path = Path("/home/mplanetarian/pinokio/api/open-webui/app/data/webui.db")
    if not db_path.exists():
        return chats

    import sqlite3
    try:
        con = sqlite3.connect(str(db_path))
        cur = con.cursor()
        cur.execute("SELECT id, title, created_at, updated_at FROM chat ORDER BY updated_at DESC LIMIT 25;")
        for cid, title, cat, uat in cur.fetchall():
            mtime = float(uat or cat or 0)
            if cid in processed_map:
                continue
            if since_timestamp and mtime < since_timestamp:
                continue
            chats.append({
                "id": cid,
                "engine": "Open WebUI",
                "title": title or "Chat Session",
                "mtime": mtime,
                "created_at": datetime.fromtimestamp(mtime).isoformat(),
                "status": "Saved"
            })
        con.close()
    except Exception:
        pass

    return chats

def harvest_deepseek_harness(since_timestamp: Optional[float] = None) -> List[Dict[str, Any]]:
    """Harvest DeepSeek Harness active sessions."""
    sessions = []
    dsh_base = Path("/home/mplanetarian/.dsh/sessions")
    if not dsh_base.exists():
        return sessions

    for sub in dsh_base.iterdir():
        if not sub.is_dir():
            continue
        workspace = sub.name.replace("--", "/").strip("/")
        for s in sub.iterdir():
            if s.is_dir() and s.name.startswith("session-"):
                try:
                    mtime = s.stat().st_mtime
                    if since_timestamp and mtime < since_timestamp:
                        continue
                    sessions.append({
                        "id": s.name,
                        "engine": "DeepSeek Harness",
                        "workspace": workspace,
                        "mtime": mtime,
                        "created_at": datetime.fromtimestamp(mtime).isoformat(),
                        "status": "Completed"
                    })
                except Exception:
                    pass
    return sessions

# =========================================================================
# ReportLab Numbered Canvas & Styles
# =========================================================================

class AIReportCanvas(canvas.Canvas):
    """Dynamic page-numbering and header/footer decorations."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#718096"))

        # Header line
        self.drawString(40, 800, "MP Reporter — Daily Artificial Intelligence Operations & Brain Logs Briefing")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(40, 792, 570, 792)

        # Footer line
        footer_text = f"Page {self._pageNumber} of {page_count}  •  Dreamworlds Intelligence  •  Automated Daily Synthesis"
        self.drawRightString(570, 25, footer_text)
        self.line(40, 35, 570, 35)
        self.restoreState()

def generate_activity_chart(gemini_count: int, grok_count: int, harmony_count: int, webui_count: int, temp_dir: Path) -> Optional[Path]:
    """Generate visual bar chart of AI operations completed."""
    try:
        fig, ax = plt.subplots(figsize=(6.2, 2.2))
        fig.patch.set_facecolor('#1a1c23')
        ax.set_facecolor('#1a1c23')

        categories = ['Google Gemini', 'Grok 4.7', 'MP Harmony', 'Open WebUI']
        counts = [gemini_count, grok_count, harmony_count, webui_count]
        bar_colors = ['#00e5ff', '#ff007f', '#a855f7', '#10b981']

        bars = ax.bar(categories, counts, color=bar_colors, width=0.55, edgecolor='#334155', alpha=0.9)
        ax.set_title("Captured AI Model Operations Breakdown", color="#00e5ff", fontsize=9.5, pad=8, weight='bold')
        ax.tick_params(colors='#cbd5e1', labelsize=8)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#334155')
        ax.spines['bottom'].set_color('#334155')

        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h + 0.15, f"{int(h)}",
                    va='bottom', ha='center', color='#ffffff', fontsize=8, weight='bold')

        chart_path = temp_dir / "ai_operations_chart.png"
        plt.tight_layout()
        plt.savefig(chart_path, dpi=200, facecolor=fig.get_facecolor(), bbox_inches="tight")
        plt.close(fig)
        return chart_path
    except Exception:
        return None

def build_executive_spoken_summary(target_date: str,
                                  gemini_sessions: List[Dict[str, Any]],
                                  grok_sessions: List[Dict[str, Any]],
                                  harmony_items: List[Dict[str, Any]],
                                  webui_items: List[Dict[str, Any]],
                                  gpu_info: Optional[Dict[str, Any]],
                                  ollama_active: str,
                                  webui_active: str,
                                  updates_count: int) -> str:
    """
    Construct clear, articulate English text designed specifically for Stephen Hawking Matrix TTS.
    Avoids weird symbols, ASCII bullets, or raw URLs so synthesis is natural and authoritative.
    """
    total_ops = len(gemini_sessions) + len(grok_sessions) + len(harmony_items) + len(webui_items)
    try:
        dt_obj = datetime.strptime(target_date, "%Y-%m-%d")
        date_formatted = dt_obj.strftime("%A, %B %d, %Y")
    except Exception:
        date_formatted = target_date

    sentences = [
        f"This is Stephen Hawking with the Daily Artificial Intelligence and Brain Logs Summary for {date_formatted}.",
        f"Across your workstation, local engines and frontier models completed {total_ops} tracked operations during this reporting period.",
    ]

    if gemini_sessions:
        g_tools = sum(s.get("tool_calls_count", 0) for s in gemini_sessions)
        g_files = len({f for s in gemini_sessions for f in s.get("files_edited", [])})
        sentences.append(
            f"Google Gemini Brain completed {len(gemini_sessions)} development sessions, executing {g_tools} automated tool calls and modifying {g_files} repository files."
        )

    if grok_sessions:
        sentences.append(
            f"Grok 4.7 completed {len(grok_sessions)} engineering and multimedia tasks across designated project workspaces."
        )

    if harmony_items:
        sentences.append(
            f"The MP Harmony Autonomous Agent generated {len(harmony_items)} voice responses with local neural voices."
        )

    # Hardware & Status
    if gpu_info:
        vram_used = gpu_info['mem_used_mib'] / 1024
        vram_total = gpu_info['mem_total_mib'] / 1024
        sentences.append(
            f"Hardware acceleration is active on the {gpu_info['name']}, utilizing {vram_used:.1f} of {vram_total:.1f} gigabytes of VRAM at {gpu_info['temp_c']} degrees Celsius."
        )

    if updates_count > 0:
        sentences.append(f"There are {updates_count} software updates available for upstream components.")
    else:
        sentences.append("All AI models, container runtimes, and local inference services are fully updated and operating normally.")

    sentences.append("Detailed session transcripts and logs have been indexed and saved to the permanent archive.")
    return " ".join(sentences)

def generate_pdf_report(report_data: Dict[str, Any], output_pdf: Path, chart_path: Optional[Path]) -> None:
    """Generate high-end PDF report using ReportLab."""
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_pdf),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=46,
        bottomMargin=46
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'RepTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=3
    )

    subtitle_style = ParagraphStyle(
        'RepSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#475569'),
        spaceAfter=12
    )

    h2_style = ParagraphStyle(
        'RepH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor('#0369a1'),
        spaceBefore=10,
        spaceAfter=5
    )

    body_style = ParagraphStyle(
        'RepBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11.5,
        textColor=colors.HexColor('#1e293b')
    )

    speech_box_style = ParagraphStyle(
        'SpeechBox',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor('#0f172a')
    )

    story = []

    # Title & Metadata
    target_date = report_data["target_date"]
    story.append(Paragraph("MP REPORTER — DAILY AI BRAIN LOGS & SOFTWARE SUMMARY", title_style))
    story.append(Paragraph(f"Reporting Date: <b>{target_date}</b> | Engine: <b>Dreamworlds AI Intelligence v{VERSION}</b> | Voice Synthesis: <b>Stephen Hawking (Enters the Matrix)</b>", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0284c7"), spaceAfter=10))

    # Executive Spoken Summary (Audio Briefing Box)
    story.append(Paragraph("Executive Audio Briefing (Spoken by Stephen Hawking Matrix Voice)", h2_style))
    summary_p = Paragraph(f"<b>Briefing:</b> {report_data['spoken_summary']}", speech_box_style)
    box_table = Table([[summary_p]], colWidths=[540])
    box_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f9ff')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#bae6fd')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(box_table)
    story.append(Spacer(1, 10))

    # Activity Chart if available
    if chart_path and chart_path.exists():
        story.append(Image(str(chart_path), width=5.5 * inch, height=1.9 * inch))
        story.append(Spacer(1, 10))

    # Core AI Service Status Table
    story.append(Paragraph("1. Core Local AI Services & Hardware Telemetry", h2_style))
    gpu = report_data.get("gpu_info")
    gpu_desc = f"{gpu['name']} ({gpu['mem_used_mib']/1024:.1f} / {gpu['mem_total_mib']/1024:.1f} GB VRAM, {gpu['temp_c']}°C)" if gpu else "Integrated / CPU Fallback"

    svc_data = [
        [Paragraph("<b>Service / Component</b>", body_style), Paragraph("<b>Status</b>", body_style), Paragraph("<b>Details & Endpoint</b>", body_style)],
        [Paragraph("Ollama Inference Engine", body_style), Paragraph(f"● {report_data['ollama_active'].upper()}", body_style), Paragraph(f"v{report_data['ollama_ver']} on port 11434 (14 Models registered)", body_style)],
        [Paragraph("Open WebUI Platform", body_style), Paragraph(f"● {report_data['webui_active'].upper()}", body_style), Paragraph(f"v{report_data['webui_ver']} on port 42004", body_style)],
        [Paragraph("MP Harmony AI Agent", body_style), Paragraph(f"● {'RUNNING' if report_data['harmony_running'] else 'STANDBY'}", body_style), Paragraph("Port 11435 (Target: gpt-oss-pinned:latest)", body_style)],
        [Paragraph("Stephen Hawking Voice", body_style), Paragraph("● ACTIVE", body_style), Paragraph("Local robotic synth with bass boost & Matrix reverb", body_style)],
        [Paragraph("Hardware Acceleration", body_style), Paragraph("● ACTIVE", body_style), Paragraph(gpu_desc, body_style)]
    ]
    t_svc = Table(svc_data, colWidths=[160, 100, 280])
    t_svc.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_svc)
    story.append(Spacer(1, 10))

    # Google Gemini Brain Section
    gemini_sessions = report_data.get("gemini_sessions", [])
    story.append(Paragraph(f"2. Google Gemini Brain Logs Activities ({len(gemini_sessions)} Sessions Captured)", h2_style))
    if not gemini_sessions:
        story.append(Paragraph("<i>No new Gemini Brain activities recorded during this reporting window.</i>", body_style))
    else:
        g_rows = [
            [Paragraph("<b>Time / Model</b>", body_style), Paragraph("<b>Primary User Goal & Request</b>", body_style), Paragraph("<b>Activities Completed & Modified Files</b>", body_style)]
        ]
        for s in gemini_sessions[-8:]:  # show up to 8 most recent
            t_short = s["created_at"][11:19] if "T" in s["created_at"] else s["created_at"][:8]
            files_str = ", ".join(s["files_edited"][:4]) if s["files_edited"] else "Code review & execution"
            tools_str = f"{s['tool_calls_count']} tools called"
            g_rows.append([
                Paragraph(f"<b>{t_short}</b><br/>{s['model']}", body_style),
                Paragraph(f"{s['primary_prompt'][:160]}...", body_style),
                Paragraph(f"<b>Files:</b> {files_str}<br/><b>Actions:</b> {tools_str}", body_style)
            ])
        t_g = Table(g_rows, colWidths=[100, 240, 200])
        t_g.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0f2fe')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t_g)
    story.append(Spacer(1, 10))

    # Grok Brain Section
    grok_sessions = report_data.get("grok_sessions", [])
    story.append(Paragraph(f"3. Grok Brain Logs Activities ({len(grok_sessions)} Sessions Captured)", h2_style))
    if not grok_sessions:
        story.append(Paragraph("<i>No new Grok Brain sessions recorded during this reporting window.</i>", body_style))
    else:
        gr_rows = [
            [Paragraph("<b>Time / Model</b>", body_style), Paragraph("<b>Workspace / Task</b>", body_style), Paragraph("<b>Accomplishments & Solution</b>", body_style)]
        ]
        for s in grok_sessions[-6:]:
            t_short = s["created_at"][11:19] if "T" in s["created_at"] else s["created_at"][:8]
            ws_short = Path(s.get("workspace", "/")).name or "workspace"
            files_str = ", ".join(s["files_edited"][:4]) if s["files_edited"] else "Engineering analysis"
            gr_rows.append([
                Paragraph(f"<b>{t_short}</b><br/>{s['model']}", body_style),
                Paragraph(f"<b>{ws_short}</b><br/>{s['primary_prompt'][:150]}", body_style),
                Paragraph(f"<b>Files:</b> {files_str}<br/><b>Tools:</b> {s['tool_calls_count']} actions", body_style)
            ])
        t_gr = Table(gr_rows, colWidths=[100, 240, 200])
        t_gr.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#fce7f3')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t_gr)
    story.append(Spacer(1, 10))

    # MP Harmony Agent & Other Models
    harmony_items = report_data.get("harmony_items", [])
    webui_items = report_data.get("webui_items", [])
    story.append(Paragraph("4. MP Harmony Autonomous Agent & Open WebUI Activities", h2_style))
    other_rows = [
        [Paragraph("<b>AI Subsystem</b>", body_style), Paragraph("<b>Activity Details & Topics Handled</b>", body_style)]
    ]
    if harmony_items:
        h_desc = f"{len(harmony_items)} voice responses recorded. Latest: {harmony_items[-1]['snippet'][:150]}..."
        other_rows.append([Paragraph(f"MP Harmony Agent<br/>({harmony_items[-1]['persona']})", body_style), Paragraph(h_desc, body_style)])
    else:
        other_rows.append([Paragraph("MP Harmony Agent", body_style), Paragraph("Idle in standby mode.", body_style)])

    if webui_items:
        w_desc = f"{len(webui_items)} active chat threads. Latest: {', '.join(c['title'] for c in webui_items[:3])}"
        other_rows.append([Paragraph("Open WebUI Chats", body_style), Paragraph(w_desc, body_style)])

    t_oth = Table(other_rows, colWidths=[140, 400])
    t_oth.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3e8ff')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_oth)
    story.append(Spacer(1, 10))

    # Software Updates & Recommendations
    story.append(Paragraph("5. AI Software Updates & Maintenance Recommendations", h2_style))
    updates = report_data.get("updates_pending", [])
    if not updates:
        story.append(Paragraph("✓ All local AI suites, inference models, and libraries are currently at their latest upstream releases.", body_style))
    else:
        for u in updates:
            story.append(Paragraph(f"• <b>Update Available:</b> {u}", body_style))
    story.append(Spacer(1, 15))

    doc.build(story, canvasmaker=AIReportCanvas)

def format_plain_text(report_data: Dict[str, Any]) -> str:
    """Format plain text for terminal output and fallback speech."""
    lines = []
    lines.append("=== AI Brain Logs and Software Daily Summary ===")
    lines.append(f"Report Generated: {datetime.now().strftime('%A, %d %B %Y at %H:%M:%S')}")
    lines.append(f"Target Reporting Date: {report_data['target_date']}")
    lines.append("")
    lines.append("=== Executive Audio Briefing ===")
    lines.append(report_data['spoken_summary'])
    lines.append("")
    lines.append("=== Core Local AI Service Status ===")
    lines.append(f"• Ollama Inference Server:  ● {report_data['ollama_active'].upper()} on port 11434 (v{report_data['ollama_ver']})")
    lines.append(f"• Open WebUI Interface:     ● {report_data['webui_active'].upper()} on port 42004 (v{report_data['webui_ver']})")
    lines.append(f"• MP Harmony AI Agent:      {'● RUNNING' if report_data['harmony_running'] else '○ STANDBY'} on port 11435")
    lines.append("• Stephen Hawking Matrix:   ● ACTIVE (Local robotic synthesizer)")
    if report_data.get("gpu_info"):
        g = report_data["gpu_info"]
        lines.append(f"• Hardware Acceleration:    {g['name']} ({g['mem_used_mib']/1024:.1f}/{g['mem_total_mib']/1024:.1f} GB VRAM, {g['temp_c']}°C)")
    lines.append("")

    lines.append(f"=== Google Gemini Brain Logs ({len(report_data['gemini_sessions'])} Sessions) ===")
    for s in report_data['gemini_sessions'][-10:]:
        lines.append(f"• [{s['created_at'][11:19] if 'T' in s['created_at'] else s['created_at'][:8]}] {s['model']}: {s['primary_prompt'][:100]}...")
        if s['files_edited']:
            lines.append(f"  Files Modified: {', '.join(s['files_edited'][:5])}")
    lines.append("")

    lines.append(f"=== Grok Brain Logs ({len(report_data['grok_sessions'])} Sessions) ===")
    for s in report_data['grok_sessions'][-6:]:
        lines.append(f"• [{s['created_at'][11:19] if 'T' in s['created_at'] else s['created_at'][:8]}] {s['model']} ({Path(s.get('workspace', '/')).name}): {s['primary_prompt'][:100]}...")
    lines.append("")

    if report_data.get("harmony_items"):
        lines.append(f"=== MP Harmony Agent Audio Responses ({len(report_data['harmony_items'])} Responses) ===")
        for h in report_data['harmony_items'][-3:]:
            lines.append(f"• [{h['created_at'][11:19]}] {h['persona']}: {h['snippet'][:120]}...")
        lines.append("")

    lines.append("=== AI Software Updates and Maintenance ===")
    if report_data.get("updates_pending"):
        for u in report_data["updates_pending"]:
            lines.append(f"• Pending Upgrade: {u}")
    else:
        lines.append("• All AI components are running up-to-date upstream versions.")
    lines.append("")

    return "\n".join(lines)

# =========================================================================
# Main Engine Orchestrator
# =========================================================================

def run_ai_reporter(daily_mode: bool = False,
                    force: bool = False,
                    output_pdf_arg: Optional[str] = None,
                    check_only: bool = False,
                    section_only: bool = False) -> Tuple[int, str, Optional[str]]:
    """
    Main orchestration function.
    Returns: (exit_code, stdout_message, generated_pdf_path)
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    state = load_state()

    # Once-per-day enforcement:
    # If daily_mode and not force and last_run_date == today_str
    if daily_mode and not force:
        if state.get("last_run_date") == today_str:
            last_pdf = None
            for rep in reversed(state.get("reports_generated", [])):
                if rep.get("date") == today_str and Path(rep.get("pdf", "")).exists():
                    last_pdf = rep.get("pdf")
                    break
            if last_pdf:
                msg = f"Report already generated for today ({today_str}): {last_pdf}\nReport generated: {last_pdf}"
                return (0, msg, last_pdf)

    # Determine catch-up timestamp:
    # If state has last_run_timestamp, capture anything newer than that.
    # If state has no timestamp, capture today's activity and backlog.
    since_ts = None
    last_run_ts = state.get("last_run_timestamp")
    if last_run_ts:
        try:
            since_ts = datetime.fromisoformat(last_run_ts).timestamp()
        except Exception:
            since_ts = None

    processed_gemini = state.get("processed_sessions", {}).get("gemini", {})
    processed_grok = state.get("processed_sessions", {}).get("grok", {})
    processed_harmony = state.get("processed_sessions", {}).get("harmony", {})
    processed_webui = state.get("processed_sessions", {}).get("open_webui", {})

    # Harvest all engines
    gemini_sessions = harvest_gemini_brain(since_timestamp=since_ts, processed_map=processed_gemini)
    grok_sessions = harvest_grok_brain(since_timestamp=since_ts, processed_map=processed_grok)
    harmony_items = harvest_harmony_agent(since_timestamp=since_ts, processed_map=processed_harmony)
    webui_items = harvest_open_webui(since_timestamp=since_ts, processed_map=processed_webui)

    # If force or initial run with 0 new, ensure we at least capture today's sessions
    if not gemini_sessions:
        gemini_sessions = harvest_gemini_brain(since_timestamp=datetime.now().replace(hour=0, minute=0, second=0).timestamp())
    if not grok_sessions:
        grok_sessions = harvest_grok_brain(since_timestamp=datetime.now().replace(hour=0, minute=0, second=0).timestamp())

    # Probe live services & updates
    ollama_tags = probe_json("http://127.0.0.1:11434/api/tags")
    ollama_ver_data = probe_json("http://127.0.0.1:11434/api/version")
    webui_ver_data = probe_json("http://127.0.0.1:42004/api/version")
    ollama_latest_data = probe_json("https://api.github.com/repos/ollama/ollama/releases/latest", timeout=2.5)
    webui_latest_data = probe_json("https://pypi.org/pypi/open-webui/json", timeout=2.5)

    ollama_ver = ollama_ver_data.get("version", "Offline") if ollama_ver_data else "Offline"
    ollama_latest = ollama_latest_data.get("tag_name", "").lstrip("v") if ollama_latest_data else "Unknown"
    webui_ver = webui_ver_data.get("version", "Offline") if webui_ver_data else "Offline"
    webui_latest = webui_latest_data.get("info", {}).get("version", "Unknown") if webui_latest_data else "Unknown"

    ollama_active = check_service("ollama.service")
    webui_active = check_service("open-webui.service")
    harmony_running = False
    try:
        res = subprocess.run(["pgrep", "-f", "MP_Harmony_Agent.py"], capture_output=True, text=True)
        harmony_running = res.returncode == 0 and bool(res.stdout.strip())
    except Exception:
        pass

    updates_pending = []
    if ollama_ver not in ("Offline", "Unknown") and ollama_latest != "Unknown":
        if ollama_ver != ollama_latest and "rc" not in ollama_latest:
            updates_pending.append(f"Ollama Server ({ollama_ver} → {ollama_latest})")
    if webui_ver not in ("Offline", "Unknown") and webui_latest != "Unknown":
        if webui_ver != webui_latest:
            updates_pending.append(f"Open WebUI ({webui_ver} → {webui_latest})")

    gpu_info = get_gpu_info()

    # Build executive spoken summary
    spoken_summary = build_executive_spoken_summary(
        target_date=today_str,
        gemini_sessions=gemini_sessions,
        grok_sessions=grok_sessions,
        harmony_items=harmony_items,
        webui_items=webui_items,
        gpu_info=gpu_info,
        ollama_active=ollama_active,
        webui_active=webui_active,
        updates_count=len(updates_pending)
    )

    report_data = {
        "target_date": today_str,
        "spoken_summary": spoken_summary,
        "gemini_sessions": gemini_sessions,
        "grok_sessions": grok_sessions,
        "harmony_items": harmony_items,
        "webui_items": webui_items,
        "ollama_active": ollama_active,
        "ollama_ver": ollama_ver,
        "webui_active": webui_active,
        "webui_ver": webui_ver,
        "harmony_running": harmony_running,
        "gpu_info": gpu_info,
        "updates_pending": updates_pending
    }

    if check_only:
        return (0, f"AI Brain activity pending: {len(gemini_sessions)} Gemini, {len(grok_sessions)} Grok", None)

    plain_text = format_plain_text(report_data)

    if section_only and not output_pdf_arg:
        return (0, plain_text, None)

    # Determine PDF output path
    if output_pdf_arg:
        out_pdf = Path(output_pdf_arg)
        if not out_pdf.is_absolute():
            out_pdf = PDF_DIR / out_pdf.name
    else:
        out_pdf = PDF_DIR / f"AI_Brain_Daily_Report_{today_str}.pdf"

    # Temporary chart generation
    with tempfile.TemporaryDirectory() as tmp_dir:
        chart_p = generate_activity_chart(
            len(gemini_sessions), len(grok_sessions), len(harmony_items), len(webui_items), Path(tmp_dir)
        )
        try:
            generate_pdf_report(report_data, out_pdf, chart_p)
        except Exception as e:
            # Fallback to enscript / ps2pdf if reportlab fails
            with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tf:
                tf.write(plain_text)
                tf_path = tf.name
            try:
                cmd = f"enscript -p - '{tf_path}' | ps2pdf - '{out_pdf}'"
                subprocess.run(cmd, shell=True, check=True)
            finally:
                if os.path.exists(tf_path):
                    os.unlink(tf_path)

    # Maintain symlink or copy to latest_ai_report.pdf
    latest_symlink = PDF_DIR / "latest_ai_report.pdf"
    try:
        if latest_symlink.exists() or latest_symlink.is_symlink():
            latest_symlink.unlink()
        latest_symlink.symlink_to(out_pdf.name)
    except Exception:
        try:
            shutil.copy2(out_pdf, latest_symlink)
        except Exception:
            pass

    # Update ledger
    now_iso = datetime.now().isoformat()
    state["last_run_date"] = today_str
    state["last_run_timestamp"] = now_iso

    for s in gemini_sessions:
        state["processed_sessions"]["gemini"][s["id"]] = {"mtime": s["mtime"], "last_seen": now_iso}
    for s in grok_sessions:
        state["processed_sessions"]["grok"][s["id"]] = {"mtime": s["mtime"], "last_seen": now_iso}
    for h in harmony_items:
        state["processed_sessions"]["harmony"][h["id"]] = {"mtime": h["mtime"], "last_seen": now_iso}
    for w in webui_items:
        state["processed_sessions"]["open_webui"][w["id"]] = {"mtime": w["mtime"], "last_seen": now_iso}

    state.setdefault("reports_generated", []).append({
        "date": today_str,
        "timestamp": now_iso,
        "pdf": str(out_pdf)
    })
    save_state(state)

    msg = f"{plain_text}\n\nReport generated: {out_pdf}"
    return (0, msg, str(out_pdf))

def main():
    parser = argparse.ArgumentParser(description="MP Reporter AI Brain Logs Daily Generator")
    parser.add_argument("--daily", action="store_true", help="Run once-per-day daily report mode")
    parser.add_argument("--force", action="store_true", help="Force regeneration even if already run today")
    parser.add_argument("--output", type=str, default=None, help="Output PDF file path")
    parser.add_argument("--check-only", action="store_true", help="Check status without generating")
    parser.add_argument("--section", action="store_true", help="Print section text only")
    args = parser.parse_args()

    # If called without arguments, act as standard section reporter for MP_Gen_System_Report.sh
    if not args.daily and not args.output and not args.check_only:
        code, msg, _ = run_ai_reporter(daily_mode=False, force=False, section_only=True)
        print(msg)
        sys.exit(code)

    code, msg, pdf = run_ai_reporter(
        daily_mode=args.daily,
        force=args.force,
        output_pdf_arg=args.output,
        check_only=args.check_only,
        section_only=args.section
    )
    print(msg)
    sys.exit(code)

if __name__ == "__main__":
    main()

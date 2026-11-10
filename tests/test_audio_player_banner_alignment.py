#!/usr/bin/env python3
"""The menu footer rule and the MP Audio Player panel share one width.

At the MP Gui grid the blue line above Selection matches the section rule
two lines above it, and every player row ends on that same column. The
player's right edge is bright white so the border stays visible.
"""

import unittest
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPT = BASE_DIR / "Mix_Archive_Manager.sh"


class TestAudioPlayerBannerAlignment(unittest.TestCase):
    def test_live_script_uses_shared_rule_and_white_right_edge(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("printf -v menu_rule '%*s' \"$((inner_w + 1))\"", text)
        self.assertIn("printf -v p_rule '%*s' \"$((inner_w - 1))\"", text)
        self.assertEqual(text.count('frame_buf+="  ${BOLD}${BLUE}${menu_rule}\\033[K${NC}\\n"'), 2)
        self.assertNotIn('frame_buf+="  ${BOLD}${BLUE}${h_border}\\033[K${NC}\\n"', text)
        self.assertIn("text_w - ${#pos_pct_str} - ${#st_raw} - 4", text)
        self.assertIn("text_w - 17 - ${#eq_raw}", text)
        self.assertIn("inner_w - ${#p_mode_title} - 5", text)
        for glyph in ("╮", "│", "╯"):
            self.assertIn(f"\\033[1;37m{glyph}", text)

    def test_banner_box_straight_right_border(self):
        """Section rule, footer rule, and the four player rows are one length."""
        bash_script = r"""
measure() {
  local box_w="$1" rec="$2" mode="$3"
  local inner_w=$(( box_w - 2 ))
  local text_w=$(( box_w - 4 ))
  local menu_rule p_rule
  printf -v menu_rule '%*s' "$((inner_w + 1))" ''
  menu_rule="${menu_rule// /─}"
  printf -v p_rule '%*s' "$((inner_w - 1))" ''
  p_rule="${p_rule// /─}"
  local label="Library And Playback"
  local sec_rem=$(( inner_w - ${#label} - 8 ))
  [ "$sec_rem" -lt 4 ] && sec_rem=4
  local sec_dashes
  printf -v sec_dashes '%*s' "$sec_rem" ''
  sec_dashes="${sec_dashes// /─}"
  local section="  ─── [ ${label} ] ${sec_dashes}"
  local footer="  ${menu_rule}"

  local st_raw="▶ playing"
  [ "$rec" = "true" ] && st_raw+=" ● REC"
  local p_mode_title="♫ MP AUDIO PLAYER"
  [ "$mode" = "MUSIC" ] && p_mode_title="♫ MP AUDIO PLAYER [MUSIC MODE - TRACKS]"
  local rem_dashes=$(( inner_w - ${#p_mode_title} - 5 ))
  [ "$rem_dashes" -lt 0 ] && rem_dashes=0
  local p_top_dashes
  printf -v p_top_dashes '%*s' "$rem_dashes" ''
  p_top_dashes="${p_top_dashes// /─}"
  local row1="  ╭── ${p_mode_title} ${p_top_dashes}╮"

  local title="MPlanetarian - Stream of Frequency - Stream_of_Frequency_2026-04-10_0h06m16.flac"
  local pos_pct_str="36:54/02:26:04 (25%)"
  local max_t_len=$(( text_w - ${#pos_pct_str} - ${#st_raw} - 4 ))
  [ "$max_t_len" -lt 4 ] && max_t_len=4
  [ "$max_t_len" -gt "$text_w" ] && max_t_len="$text_w"
  local disp_title="$title"
  if [ ${#disp_title} -gt "$max_t_len" ]; then
    disp_title="${disp_title:0:$((max_t_len - 3))}..."
  fi
  local raw_l1_len=$(( ${#st_raw} + 2 + ${#disp_title} + ${#pos_pct_str} ))
  local l1_pad=$(( text_w - raw_l1_len - 1 ))
  if [ "$l1_pad" -lt 1 ]; then
    local _over=$((1 - l1_pad))
    local _tlen=${#disp_title}
    if [ $((_tlen - _over)) -gt 3 ]; then
      disp_title="${disp_title:0:$((_tlen - _over - 3))}..."
    else
      disp_title="${disp_title:0:$(( _tlen > _over ? _tlen - _over : 0 ))}"
    fi
    raw_l1_len=$(( ${#st_raw} + 2 + ${#disp_title} + ${#pos_pct_str} ))
    l1_pad=$(( text_w - raw_l1_len - 1 ))
    [ "$l1_pad" -lt 1 ] && l1_pad=1
  fi
  local l1_sp
  printf -v l1_sp '%*s' "$l1_pad" ''
  local row2="  │ ${st_raw}  ${disp_title}${l1_sp}${pos_pct_str} │"

  local line2_ctrl="[Space] Toggle [M] Player [L] Liquid [G] MP Gui [C] Theme [n] Next [</>] Track [p] UI [f] FM"
  local eq_raw="▁▂▁     "
  local l2_pad=$(( text_w - 17 - ${#eq_raw} - ${#line2_ctrl} ))
  if [ "$l2_pad" -lt 0 ]; then
    local _keep=$(( ${#line2_ctrl} + l2_pad ))
    [ "$_keep" -lt 0 ] && _keep=0
    if [ "$_keep" -gt 3 ]; then
      line2_ctrl="${line2_ctrl:0:$((_keep - 3))}..."
    else
      line2_ctrl="${line2_ctrl:0:$_keep}"
    fi
    l2_pad=0
  fi
  local l2_sp=""
  [ "$l2_pad" -gt 0 ] && printf -v l2_sp '%*s' "$l2_pad" ''
  local row3="  │   EQ: ${eq_raw}${l2_sp}Controls: ${line2_ctrl} │"
  local row4="  ╰${p_rule}╯"
  echo "WIDTH:${box_w}:${#section}:${#footer}:${#row1}:${#row2}:${#row3}:${#row4}:${row1: -1}:${row2: -1}:${row3: -1}:${row4: -1}"
}
for box_w in 100 116 120 140 160 170 190; do
  for rec in false true; do
    for mode in MIX MUSIC; do
      measure "$box_w" "$rec" "$mode"
    done
  done
done
"""
        proc = subprocess.run(
            ["bash", "-c", bash_script],
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        lines = [line for line in proc.stdout.splitlines() if line.startswith("WIDTH:")]
        self.assertEqual(len(lines), 7 * 2 * 2)
        for line in lines:
            parts = line.split(":")
            box_w = int(parts[1])
            lengths = [int(part) for part in parts[2:8]]
            ends = parts[8:12]
            expected = box_w + 1
            self.assertEqual(
                lengths,
                [expected] * 6,
                f"Mismatch at box_w={box_w}: {lengths}, expected {expected}",
            )
            self.assertEqual(ends, ["╮", "│", "│", "╯"])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""The menu footer matches the section rule. The player panel matches the header.

The blue line above Selection is the section rule's length. The MP Audio
Player panel's right edge is the theme border colour and lands on the same
column as the header panel above it.
"""

import unittest
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPT = BASE_DIR / "Mix_Archive_Manager.sh"


class TestAudioPlayerBannerAlignment(unittest.TestCase):
    def test_live_script_uses_theme_colour_on_the_player_edge(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("printf -v menu_rule '%*s' \"$((inner_w + 1))\"", text)
        self.assertNotIn("p_rule", text)
        self.assertEqual(text.count('frame_buf+="  ${BOLD}${BLUE}${menu_rule}\\033[K${NC}\\n"'), 2)
        self.assertNotIn('frame_buf+="  ${BOLD}${BLUE}${h_border}\\033[K${NC}\\n"', text)
        self.assertIn("text_w - ${#pos_pct_str} - ${#st_raw} - 4", text)
        self.assertIn("text_w - raw_l1_len", text)
        self.assertNotIn("text_w - raw_l1_len - 1", text)
        self.assertIn("text_w - 16 - ${#eq_raw}", text)
        self.assertIn("inner_w - ${#p_mode_title} - 4", text)
        self.assertIn(
            'player_banner+="  ${BOLD}${MAGENTA}╭── ${p_mode_title} ${p_top_dashes}╮\\033[K${NC}\\n"',
            text,
        )
        self.assertIn(
            'player_banner+="  ${BOLD}${MAGENTA}│${NC} ${l1_left}${l1_sp}${l1_right} ${BOLD}${MAGENTA}│\\033[K${NC}\\n"',
            text,
        )
        self.assertIn(
            'player_banner+="  ${BOLD}${MAGENTA}│${NC}   ${DIM}EQ:${NC} ${eq_disp}${l2_sp}${DIM}Controls: ${line2_ctrl}${NC} ${BOLD}${MAGENTA}│\\033[K${NC}\\n"',
            text,
        )
        self.assertIn(
            'player_banner+="  ${BOLD}${MAGENTA}╰${h_border}╯\\033[K${NC}\\n"',
            text,
        )
        for glyph in ("╮", "│", "╯"):
            self.assertNotIn(f"\\033[1;37m{glyph}", text)

    def test_banner_box_straight_right_border(self):
        """Player rows end on the header's right column. Section and footer match each other."""
        bash_script = r"""
measure() {
  local box_w="$1" rec="$2" mode="$3"
  local inner_w=$(( box_w - 2 ))
  local text_w=$(( box_w - 4 ))
  local menu_rule h_border
  printf -v menu_rule '%*s' "$((inner_w + 1))" ''
  menu_rule="${menu_rule// /─}"
  printf -v h_border '%*s' "$inner_w" ''
  h_border="${h_border// /─}"
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
  local rem_dashes=$(( inner_w - ${#p_mode_title} - 4 ))
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
  local l1_pad=$(( text_w - raw_l1_len ))
  if [ "$l1_pad" -lt 1 ]; then
    local _over=$((1 - l1_pad))
    local _tlen=${#disp_title}
    if [ $((_tlen - _over)) -gt 3 ]; then
      disp_title="${disp_title:0:$((_tlen - _over - 3))}..."
    else
      disp_title="${disp_title:0:$(( _tlen > _over ? _tlen - _over : 0 ))}"
    fi
    raw_l1_len=$(( ${#st_raw} + 2 + ${#disp_title} + ${#pos_pct_str} ))
    l1_pad=$(( text_w - raw_l1_len ))
    [ "$l1_pad" -lt 1 ] && l1_pad=1
  fi
  local l1_sp
  printf -v l1_sp '%*s' "$l1_pad" ''
  local row2="  │ ${st_raw}  ${disp_title}${l1_sp}${pos_pct_str} │"

  local line2_ctrl="[Space] Toggle [M] Player [L] Liquid [G] MP Gui [C] Theme [n] Next [</>] Track [p] UI [f] FM"
  local eq_raw="▁▂▁     "
  local l2_pad=$(( text_w - 16 - ${#eq_raw} - ${#line2_ctrl} ))
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
  local row4="  ╰${h_border}╯"
  local header="  ╭${h_border}╮"
  echo "WIDTH:${box_w}:${#section}:${#footer}:${#header}:${#row1}:${#row2}:${#row3}:${#row4}:${row1: -1}:${row2: -1}:${row3: -1}:${row4: -1}"
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
            section, footer = int(parts[2]), int(parts[3])
            player = [int(part) for part in parts[4:9]]
            ends = parts[9:13]
            rule = box_w + 1
            edge = box_w + 2
            self.assertEqual(section, rule, f"section at box_w={box_w}")
            self.assertEqual(footer, rule, f"footer at box_w={box_w}")
            self.assertEqual(
                player,
                [edge] * 5,
                f"player/header mismatch at box_w={box_w}: {player}, expected {edge}",
            )
            self.assertEqual(ends, ["╮", "│", "│", "╯"])


if __name__ == "__main__":
    unittest.main()

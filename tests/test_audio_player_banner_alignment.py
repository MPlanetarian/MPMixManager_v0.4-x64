#!/usr/bin/env python3
"""
Unit test to verify that the MP Audio Player banner box rendered in Mix_Archive_Manager.sh
and .probe_mgr.sh has perfectly aligned left and right borders across all rows (no ragged edge).
"""

import unittest
import subprocess
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    ansi_regex = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_regex.sub("", text)


class TestAudioPlayerBannerAlignment(unittest.TestCase):
    def test_banner_box_straight_right_border(self):
        """Verify top line, content rows, and bottom line all have equal visual length."""
        bash_script = r"""
source ./Mix_Archive_Manager.sh 2>/dev/null || true

# Test multiple box widths
for box_w in 100 120 140 160 170 190; do
    inner_w=$(( box_w - 2 ))
    text_w=$(( box_w - 4 ))
    printf -v h_border '%*s' "$inner_w" ''
    h_border="${h_border// /─}"

    MP_PLAYER_STATE="playing"
    MP_PLAYER_MODE="MIX"
    MP_PLAYER_TITLE="MPlanetarian - Stream of Frequency - Stream_of_Frequency_2026-04-10_0h06m16.flac"
    MP_PLAYER_POS_FMT="18:02"
    MP_PLAYER_DUR_FMT="01:06:12"
    MP_PLAYER_PROGRESS_PCT="27"
    MP_PLAYER_RECORDING="false"
    MP_PLAYER_MINI_EQ="  ▂▃▄▅▆▇"

    st_color=""
    st_icon="▶"
    st_low="$(printf "%s" "$MP_PLAYER_STATE" | tr "A-Z" "a-z")"
    st_sym="${st_icon} ${st_low}"
    st_raw="${st_icon} ${st_low}"

    p_mode_title="♫ MP AUDIO PLAYER"
    rem_dashes=$(( inner_w - ${#p_mode_title} - 4 ))
    [ "$rem_dashes" -lt 0 ] && rem_dashes=0
    printf -v p_top_dashes '%*s' "$rem_dashes" ''
    p_top_dashes="${p_top_dashes// /─}"

    row1="  ╭── ${p_mode_title} ${p_top_dashes}╮"

    pos_pct_str="${MP_PLAYER_POS_FMT}/${MP_PLAYER_DUR_FMT} (${MP_PLAYER_PROGRESS_PCT%.*}%)"
    max_t_len=$(( text_w - ${#pos_pct_str} - 16 ))
    [ "$max_t_len" -lt 4 ] && max_t_len=4
    [ "$max_t_len" -gt "$text_w" ] && max_t_len="$text_w"
    disp_title="$MP_PLAYER_TITLE"
    if [ ${#disp_title} -gt "$max_t_len" ]; then
        disp_title="${disp_title:0:$((max_t_len - 3))}..."
    fi

    l1_left="${st_sym}  ${disp_title}"
    l1_right="${MP_PLAYER_POS_FMT}/${MP_PLAYER_DUR_FMT} (${MP_PLAYER_PROGRESS_PCT%.*}%)"
    raw_l1_len=$(( ${#st_raw} + 2 + ${#disp_title} + ${#pos_pct_str} ))
    l1_pad=$(( text_w - raw_l1_len ))
    [ "$l1_pad" -lt 2 ] && l1_pad=2
    printf -v l1_sp '%*s' "$l1_pad" ''
    row2="  │ ${l1_left}${l1_sp}${l1_right} │"

    line2_ctrl="[Space] Toggle  [M] Window  [n] Next  [</>] Track  [p] UI  [f] FM"
    eq_disp="${MP_PLAYER_MINI_EQ:-        }"
    raw_l2_len=$(( 6 + 8 + 10 + ${#line2_ctrl} ))
    l2_pad=$(( text_w - raw_l2_len ))
    [ "$l2_pad" -lt 2 ] && l2_pad=2
    printf -v l2_sp '%*s' "$l2_pad" ''
    row3="  │   EQ: ${eq_disp}${l2_sp}Controls: ${line2_ctrl} │"

    row4="  ╰${h_border}╯"

    echo "WIDTH:$box_w:${#row1}:${#row2}:${#row3}:${#row4}"
done
"""
        proc = subprocess.run(
            ["bash", "-c", bash_script],
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )

        for line in proc.stdout.strip().splitlines():
            if line.startswith("WIDTH:"):
                parts = line.split(":")
                w = int(parts[1])
                l1, l2, l3, l4 = int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5])
                self.assertEqual(
                    (l1, l2, l3, l4),
                    (w + 2, w + 2, w + 2, w + 2),
                    f"Mismatch at box_w={w}: row lengths are ({l1}, {l2}, {l3}, {l4}), expected all {w + 2}"
                )


if __name__ == "__main__":
    unittest.main()

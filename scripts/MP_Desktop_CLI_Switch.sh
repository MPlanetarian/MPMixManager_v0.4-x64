#!/usr/bin/env bash
# Toggle between the KDE Plasma Wayland session and a TTY login.
# Run from Plasma to log out and leave a text console. Run from that console
# to bring the login screen back.
#
# Plasma's compositor is a user service (plasma-kwin_wayland.service). It is
# not part of graphical.target, and user@.service keeps running across a
# runlevel change. Stopping the greeter therefore leaves the desktop on screen.
# Logout is handed to a system unit so it still runs after this process, which
# belongs to the desktop session, is killed.

set -euo pipefail

# Terminus 12x24. Bazzite does not ship terminus-fonts-console, so the glyph
# file is kept in the user account and copied to /etc for early-boot setfont.
TTY_FONT_FILE="ter-v24n.psf.gz"
TTY_FONT_ETC="/etc/mp-desktop-cli-switch/${TTY_FONT_FILE}"

in_plasma() {
  case "${XDG_CURRENT_DESKTOP:-}" in
    *KDE*|*Plasma*) return 0 ;;
  esac
  systemctl --user is-active --quiet plasma-kwin_wayland.service 2>/dev/null
}

install_tty_font() {
  local user_home src="" candidate
  user_home=$(getent passwd "${SUDO_USER:?}" | cut -d: -f6)
  for candidate in \
    "$TTY_FONT_ETC" \
    "$(dirname "$(readlink -f "$0")")/${TTY_FONT_FILE}" \
    "${user_home}/.local/share/mp-desktop-cli-switch/${TTY_FONT_FILE}" \
    "/usr/lib/kbd/consolefonts/${TTY_FONT_FILE}"
  do
    if [[ -f "$candidate" ]]; then
      src=$candidate
      break
    fi
  done
  if [[ -z "$src" ]]; then
    echo "Terminus 24 console font not found; TTY keeps the default font." >&2
    return 0
  fi
  mkdir -p "$(dirname "$TTY_FONT_ETC")"
  if [[ "$src" != "$TTY_FONT_ETC" ]]; then
    cp -f "$src" "$TTY_FONT_ETC"
  fi
  if [[ -f /etc/vconsole.conf ]] && grep -q '^FONT=' /etc/vconsole.conf; then
    sed -i "s|^FONT=.*|FONT=${TTY_FONT_ETC}|" /etc/vconsole.conf
  else
    printf 'FONT=%s\n' "$TTY_FONT_ETC" >> /etc/vconsole.conf
  fi
  # Debian and Ubuntu read this file. Bazzite uses vconsole.conf above.
  # Leave the file alone when the distro does not have it.
  local setup="/etc/default/console-setup"
  if [[ -f "$setup" ]]; then
    local tmp found_face=0 found_size=0 line
    tmp="$(mktemp)"
    while IFS= read -r line || [[ -n "$line" ]]; do
      case "$line" in
        FONTFACE=*) printf '%s\n' 'FONTFACE="Terminus"' >>"$tmp"; found_face=1 ;;
        FONTSIZE=*) printf '%s\n' 'FONTSIZE="12x24"' >>"$tmp"; found_size=1 ;;
        *) printf '%s\n' "$line" >>"$tmp" ;;
      esac
    done <"$setup"
    [[ "$found_face" -eq 0 ]] && printf '%s\n' 'FONTFACE="Terminus"' >>"$tmp"
    [[ "$found_size" -eq 0 ]] && printf '%s\n' 'FONTSIZE="12x24"' >>"$tmp"
    cat "$tmp" >"$setup"
    rm -f "$tmp"
  fi
}

if [[ "$(id -u)" -ne 0 ]]; then
  if in_plasma; then
    exec /usr/bin/sudo "$0" --to-tty
  fi
  if [[ "$(systemctl get-default)" == "multi-user.target" ]]; then
    exec /usr/bin/sudo "$0" --to-desktop
  fi
  echo "Plasma is not running, and the graphical login is still enabled." >&2
  echo "Run this from a Plasma session to switch to the TTY login." >&2
  exit 1
fi

case "${1:-}" in
  --to-tty)
    echo "Stopping Plasma and the Wayland login screen."
    echo "MP Mix Manager opens on tty1 and restarts if it exits."
    echo "Ctrl+Alt+F2 stays a login shell. TTY font is Terminus 24."
    user="${SUDO_USER:-}"
    if [[ -z "$user" || "$user" == root ]]; then
      echo "Run this from your user account, not as root." >&2
      exit 1
    fi

    install_tty_font

    kiosk="$(dirname "$(readlink -f "$0")")/mp_tty_kiosk.sh"
    if [[ -f "$kiosk" ]]; then
      bash "$kiosk" --install || echo "MP Mix Manager TTY service was not installed. tty1 stays a login." >&2
    fi

    systemctl set-default multi-user.target
    systemctl stop mp-drop-to-tty.service 2>/dev/null || true
    systemctl reset-failed mp-drop-to-tty.service 2>/dev/null || true

    # Executed by /usr/bin/bash as a system service (shell_exec_t), not as this
    # file (user_home_t), so the system unit is allowed to run it under SELinux.
    # systemd must not expand the $ variables; bash in the unit does.
    helper=$(cat <<'EOF'
set -euo pipefail
user="${MP_SWITCH_USER:?}"
runtime="/run/user/$(id -u "$user")"

# This unit sets IgnoreOnIsolate=yes, so the runlevel change leaves it running.
systemctl isolate multi-user.target

if [[ -S "${runtime}/bus" ]]; then
  timeout 15 runuser -u "$user" -- env \
    XDG_RUNTIME_DIR="$runtime" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=${runtime}/bus" \
    busctl --user call org.kde.Shutdown /Shutdown org.kde.Shutdown logout \
    || true
fi

for _ in $(seq 1 40); do
  if ! systemctl --user --machine="${user}@" is-active --quiet plasma-kwin_wayland.service; then
    break
  fi
  sleep 0.25
done

# Stopping an already-inactive target does not stop services that outlived it.
systemctl --user --machine="${user}@" stop \
  graphical-session.target \
  plasma-kwin_wayland.service \
  plasma-plasmashell.service \
  || true

while read -r id _ _ seat _; do
  [[ "$seat" == seat0 ]] || continue
  loginctl terminate-session "$id" || true
done < <(loginctl list-sessions --no-legend || true)

systemctl stop plasmalogin.service || true
systemctl start getty@tty2.service || true
if systemctl cat mp-mix-manager-tty.service >/dev/null 2>&1; then
  systemctl mask getty@tty1.service || true
  systemctl stop getty@tty1.service || true
  systemctl restart mp-mix-manager-tty.service || true
else
  systemctl start getty@tty1.service
fi

switched=0
for _ in 1 2 3 4 5 6 7 8; do
  if chvt 1; then
    switched=1
    break
  fi
  sleep 0.4
done

if [[ -n "${MP_TTY_FONT:-}" && -f "$MP_TTY_FONT" ]]; then
  for n in 1 2 3 4 5 6; do
    setfont -C "/dev/tty${n}" "$MP_TTY_FONT" || true
  done
fi

if systemctl --user --machine="${user}@" is-active --quiet plasma-kwin_wayland.service; then
  echo "KWin is still running." >&2
  exit 1
fi
if [[ "$switched" -ne 1 ]]; then
  echo "Could not switch the console to tty1." >&2
  exit 1
fi
EOF
)
    bash -n <<<"$helper"
    systemd-run --wait --collect --quiet --unit=mp-drop-to-tty \
      --service-type=exec \
      --expand-environment=no \
      --property=IgnoreOnIsolate=yes \
      --property=RuntimeMaxSec=180 \
      --setenv=MP_SWITCH_USER="$user" \
      --setenv=MP_TTY_FONT="$TTY_FONT_ETC" \
      --working-directory=/ \
      /usr/bin/bash -c "$helper" || switch_rc=$?
    if [[ "${switch_rc:-0}" -ne 0 ]]; then
      systemctl disable --now mp-mix-manager-tty.service 2>/dev/null || true
      systemctl unmask getty@tty1.service 2>/dev/null || true
      systemctl start getty@tty1.service 2>/dev/null || true
      exit "$switch_rc"
    fi
    ;;
  --to-desktop)
    echo "Enabling the Plasma Wayland login screen."
    kiosk="$(dirname "$(readlink -f "$0")")/mp_tty_kiosk.sh"
    if [[ -f "$kiosk" ]]; then
      bash "$kiosk" --remove || true
    else
      systemctl disable --now mp-mix-manager-tty.service 2>/dev/null || true
      systemctl unmask getty@tty1.service 2>/dev/null || true
    fi
    systemctl set-default graphical.target
    systemctl reset-failed plasmalogin.service 2>/dev/null || true
    systemctl start graphical.target
    ;;
  *)
    echo "Usage: $0" >&2
    exit 1
    ;;
esac

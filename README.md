# MP Mix Manager 0.3.6 Beta by Dreamworlds Productions (MPlanetarian)

> 📅 **Last Updated:** October 17, 2026 • **Latest Release:** `v0.3.6 Beta`

[![Last Updated](https://img.shields.io/badge/Last%20Updated-October%2017%2C%202026-brightgreen.svg)]()
[![Version](https://img.shields.io/badge/Version-0.3.6%20Beta-f72585.svg)](VERSION)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows%20%7C%20FreeBSD-00e5ff.svg)](README.md)
[![macOS](https://img.shields.io/badge/macOS-Sonoma%20%7C%20Sequoia%20%7C%20Apple%20Silicon%20M1--M4%20%26%20Intel-silver.svg)]()
[![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011%20%7C%20Git%20Bash%20%7C%20WSL2-0078D6.svg)]()
[![FreeBSD](https://img.shields.io/badge/FreeBSD-14.x%20%7C%2015--CURRENT%20%7C%20Ports%20%26%20Pkg-red.svg)]()
[![Shell](https://img.shields.io/badge/Language-Bash%205.x%20%7C%20Python%203.10%2B%20%7C%20PowerShell-ff8c00.svg)]()
[![Audio](https://img.shields.io/badge/Audio-32bit%20Lossless%20FLAC%20%7C%20EBU%20R128-00ff66.svg)]()
[![Player](https://img.shields.io/badge/MP%20Audio%20Player-Mini%20%26%20Micro%20Modes%20%7C%2031K%2B%20SMB%20Tracks-bd93f9.svg)](MP_Audio_Player.py)
[![Web Companion](https://img.shields.io/badge/Web%20Companion-DJ%20Booth%20Remote%20%3A8888-ff007f.svg)](mix_web_companion.py)
[![AI Suite](https://img.shields.io/badge/AI%20Suite-Harmony%20%7C%20Matrix%20XTTS--v2%20%7C%20Infinite%20Talker%20%7C%20WAN2GP-9b59b6.svg)](scripts/manage_harmony_agent.sh)
[![MP Reporter](https://img.shields.io/badge/MP%20Reporter-Daily%2FWeekly%2FMonthly%2FYearly%20%2B%20AI%20Brain%20Logs-00e5ff.svg)](mp_report_generator.py)
[![Alarm Clock](https://img.shields.io/badge/Alarm%20Clock-Steam%20%26%20FLAC%20Mix%20(Linux)-FF5722.svg)](mplanetarians-alarm-clock/README.md)
[![Congen](https://img.shields.io/badge/Congen%20v1.1-KDE%20Connect%2018--Theme%20Workstation%20Bridge-1D99F3.svg)](Congen/README.md)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

An enterprise-grade workstation orchestration console and media management suite designed for high-resolution audio production, multi-hour DJ mix archiving, automated 32-bit FLAC mastering, 31,000+ track SMB network streaming, Traktor Pro playlist extraction, live tracklist tracking, YouTube & AI Talking-Head video synthesis, automated multi-period intelligence reporting, system maintenance, and AI workflow control across **Linux (Bazzite / SteamOS / Fedora / Ubuntu)**, **macOS (Latest Sequoia / Sonoma, Apple Silicon M1–M4 & Intel)**, **Microsoft Windows 10 & 11**, and **FreeBSD (14.x / 15-CURRENT)**.

---

## 📑 Table of Contents

- [🚀 New Features Added in the Last 3 Days (October 14–17, 2026)](#-new-features-added-in-the-last-3-days-october-1417-2026)
- [🔥 Core v0.3.5 / v0.3.6 Architecture Highlights](#-core-v035--v036-architecture-highlights)
- [🌌 MPlanetarian Dreamworlds & TUI Navigation](#-spotlight-mplanetarian-dreamworlds--tui-navigation)
- [🎧 MP Audio Player (Terminal Audio Suite)](#-spotlight-mp-audio-player-terminal-audio-suite)
- [📱 DJ Booth & Studio Mobile Web Companion](#-spotlight-dj-booth--studio-mobile-web-companion)
- [🎬 YouTube Shorts 1080x1920 Promotional Video Generator](#-spotlight-youtube-shorts-1080x1920-promotional-video-generator)
- [🎥 Screencast YouTube Video Generator with NVENC & Image Transitions](#-spotlight-screencast-youtube-video-generator-with-nvenc--image-transitions)
- [🤖 Next-Gen AI Orchestration Suite](#-spotlight-next-gen-ai-orchestration-suite)
- [📱 Congen v1.1 by Dreamworlds Productions (MPlanetarian)](#-spotlight-congen-v100-by-dreamworlds-productions-mplanetarian)
- [✂️ Auto-Split DJ Mixes & Multi-Part Spek Spectrograms](#️-spotlight-auto-split-dj-mixes--multi-part-spek-spectrograms)
- [⏰ MPlanetarians Alarm Clock (Wake Up Edition)](#-spotlight-mplanetarians-alarm-clock-wake-up-edition)
- [⚡ Traktor History Harmonic Playlist & Stage Setup](#-spotlight-traktor-history-harmonic-playlist--stage-setup)
- [🎛️ EBU R128 Loudness Mastering, Audio Audit & CUE Engine](#️-spotlight-ebu-r128-loudness-mastering-audio-audit--cue-engine)
- [🔍 Audio Fingerprinting, Chapters & Rekordbox Export](#-spotlight-audio-fingerprinting-chapters--rekordbox-export)
- [🖥️ KDE Plasma Desktop Shortcuts & Global Keyboard Binder](#️-spotlight-kde-plasma-desktop-shortcuts--global-keyboard-binder)
- [📢 Unified Multi-Channel Notification Dispatcher](#-spotlight-unified-multi-channel-notification-dispatcher)
- [🚀 Quick Start by Operating System](#-quick-start-by-operating-system)
- [🎛️ Master Feature Matrix (3 Sections, Options 0–36)](#️-master-feature-matrix-3-sections-options-035)
- [💻 Command Line Interface & Direct Shortcuts](#-command-line-interface--direct-shortcuts)
- [📂 Repository & Codebase Layout](#-repository--codebase-layout)
- [⚙️ Configuration Guide (`config.env`)](#️-configuration-guide-configenv)
- [🧪 Automated Test Suite & Quality Assurance](#-automated-test-suite--quality-assurance)
- [📜 License](#-license)

---

## 🚀 New Features Added in the Last 3 Days (October 14–17, 2026)

> [!IMPORTANT]
> **72-Hour Velocity Sprint (`v0.3.6 Beta` — Oct 14–17, 2026):** Over the last 3 days, MP Mix Manager received major upgrades across **MP Audio Player**, **SMB Network Track Streaming**, **Zero-Fork Low-Spec Bash Optimization**, **Matrix & Stephen Hawking AI Voice Cloning**, **WAN2GP Infinite Talker AI Video**, and the **MP Reporter Intelligence & Email Suite**.

| Feature Area | Component | New Capabilities Added (Oct 14–17, 2026) |
| :--- | :--- | :--- |
| **🪟 MP Mini & Micro Player** | **[MP Audio Player (`M` Key)](MP_Audio_Player.py)** | Press **`M`** in `MP_Audio_Player.py` to launch an independent compact transparent console window with **dynamic quasi-periodic color gradients** shifting via irrational phase modulation (`OSC 11`), real-time mini equalizer, volume/pitch controls, and full track metadata without the playlist. Press **`M`** again inside Mini Mode to toggle the ultra-compact hidden **MICRO Mode**. Mute moved to **`u` / `U`**, plus a new **Old Style Unix Terminal Retro Mode (White on Black)** theme. |
| **📊 In-Player Spek Generator** | **[Local Spek in Player (`G` Key)](MP_Audio_Player.py)** | Press **`G`** during playback, playlist browsing, or inside the **`[I]` Track Inspector HUD** to asynchronously generate and save a local **1080p logarithmic Spek spectrogram** (`.png`) for any playing/selected track or mix directly into `SPEK_OUTPUTS`. |
| **🌐 SMB DJ Music Streaming** | **[Option 1: MUSIC Folders Mode](MP_Audio_Player.py)** | Streams **31,271+ DJ tracks** from remote SMB network shares (`/MUSIC001` & `/MUSIC002` at `192.168.1.138`) with `rclone` VFS full caching (`--vfs-cache-mode full`), pre-cached `.m3u8` playlists, asynchronous background **Track Duration (`00:00`)** column in the playlist browser, and the modal **Track Audio Inspector HUD (`I` key)** displaying codec, sample rate, volume/pitch, output engine, and SMB path. |
| **✨ Equalizers & Cosmic Theme** | **[Stardust Chroma & Cosmic Supernova](themes/Cosmic_Supernova_MP_Mix_Manager.theme)** | Added the **Stardust Chroma** equalizer (ultra-thin vertical bars with falling cosmic dust particle physics), **Neon Chroma Prism** EQ visualizer, and the **Cosmic Supernova [Special Edition]** 24-bit TrueColor theme across `Mix_Archive_Manager.sh`, `MP_Audio_Player.py`, `Congen`, `mix_web_companion.py`, and `btop`. |
| **🎧 Bluetooth Auto-Routing** | **[Live Sink Switcher (`[a]` Key)](monitor_bluetooth_audio.py)** | Real-time `pactl subscribe` event listener + 1.2s heartbeat monitor for Bluetooth headphones (Skullcandy Crusher ANC 2, Sony WH-1000XM, AirPods, Bose). Auto-switches the default PipeWire/PulseAudio sink and live-migrates active audio streams (`pactl move-sink-input`) while respecting manual sink overrides. |
| **🔍 Interactive `/` Menu Search** | **[Mix_Archive_Manager.sh](Mix_Archive_Manager.sh)** | Press **`/`** on the Main Page or any submenu to filter menu options in real time by number, title, or description (`_find_menu_search_match`). Navigate matches with `↑`/`↓`, press `Enter` to launch, or `Esc` to clear. |
| **⚡ Zero-Fork Low-Spec Engine** | **[Mix_Archive_Manager.sh](Mix_Archive_Manager.sh) & [.probe_mgr.sh](.probe_mgr.sh)** | Massive performance rewrite for slow/low-spec hardware: reduced `Mix_Archive_Manager.sh` from 13,572 → **1,978 lines** (-85%) and `.probe_mgr.sh` from 14,583 → **264 lines** (-98% line count) by eliminating subshell forks (`$(...)`), external `awk`/`sed`/`grep`/`wc` calls, and redundant DOM/IPC overhead across `Make_SOF_FLAC_CONVERSION.sh`, `convert_audio_format.sh`, `traktor_monitor.py`, and `align_mix_windows.py` (KDE KWin DBus + X11 fallback). |
| **📊 MP Reporter & AI Brain Logs** | **[Option 27: MP Reporter Suite](mp_report_generator.py)** | Automated **Daily, Weekly, Monthly, and Yearly** intelligence reports (`mp_report_generator.py`, `mp_scheduled_reporter.sh`, `manage_mp_reporter.sh`) with consolidated PDF/HTML rendering, `REPORTS/{DAILY,WEEKLY,MONTHLY,YEARLY}` hierarchy, interactive 12-month calendar dashboard, **Daily AI Brain Logs reporter** (scanning Gemini, Grok & local models), **Stephen Hawking AI Voice TTS audio briefings**, and automated **SMTP daily email delivery** (`mp_email_manager.sh`). |
| **🕶️ Matrix & Hawking Voice Lab** | **[Ollama & WAN2GP Voice Suite](scripts/wan2gp_tts_batch.py)** | Expanded local XTTS-v2 neural voice cloning and Edge-TTS with **Agent Smith / Elrond (Hugo Weaving)**, **5 Morpheus variants** (Construct, Red Pill, Dojo, System, Classic), **Neo**, **Trinity**, **The Oracle**, **Zion**, and **Stephen Hawking (Enters the Matrix)**, plus automatic voice chat recording to the **MP Harmony Agent Audio Speech Archive**. |
| **🎬 WAN2GP Infinite Talker & Monitors** | **[Infinite Talker & Output Monitors](scripts/wan2gp.sh)** | Integrated **WAN2GP Infinite Talker** in Option 33 and MP Reporter to generate talking-head AI videos (including Stephen Hawking video briefings) with custom duration and auto-venv detection; added **WAN2GP Video Output Monitor (`--wan2gp-monitor`)**, **Audio/Video File Output Monitor (`--audio-monitor`)**, and one-click WAN2GP upstream Git updater. |
| **🦙 Ollama 32K CUDA & Open WebUI** | **[manage_ollama.sh](scripts/manage_ollama.sh)** | Optimized Ollama local LLMs with a **32K context window** (`num_ctx 32768`), CUDA flash-attention tuning, automatic GPU VRAM unloading, **Open WebUI v0.12.2** support, and interactive **DSH Mobile Token Manager** (`dsh_mobile.sh`). |
| **📱 Congen v1.1 & Deduplicator** | **[Congen v1.1](Congen/Congen) & [find_duplicate_mixes.py](find_duplicate_mixes.py)** | Upgraded **Congen to v1.1** with an expanded **18-theme palette** (adding Old Style Unix Terminal Retro, Matrix, Solarized, Tokyo Night, Monokai, Gruvbox, Emerald) and workstation bridge; refactored `find_duplicate_mixes.py` for deterministic O(1) partial-hash pre-filtering and safe non-interactive execution. |

---

## 🔥 Core v0.3.5 / v0.3.6 Architecture Highlights

| Feature Area | Component | Highlights & Capability Summary |
| :--- | :--- | :--- |
| **📱 Mobile Remote Suite** | **[Congen v1.1](Congen/README.md)** | Full-featured KDE Connect interactive CLI manager with **11 menus**, **18 TrueColor palettes**, desktop shortcut runner/binder (`kioclient` & `kwriteconfig6`), algorithmic 2-tone synthetic chime sound daemon (`.congen_alert.wav`), multi-format manual generator (Plain Text, dark HTML5, PDF fallback cascade), mobile keyboard simulation (Wayland/X11), and 30+ bundled `.congen` profiles with multi-device deduplication. |
| **🎥 YouTube Video Suite** | **[Screencast NVENC Generator](scripts/generate_screencast_youtube_video.py)** | Generates 1080p/4K YouTube videos with NVIDIA NVENC hardware acceleration (`h264_nvenc`), 5-second intro/outro fade effects, periodic 5-second image transition cycles every 5 minutes (cycling artwork), source-matched or 320kbps looped studio AAC audio, and uniform 90000 timescale stream architecture. |
| **🗣️ AI Video & Audio** | **[WAN2GP TTS & Infinite Talker](scripts/wan2gp_tts_batch.py)** | Integrated Text-to-Speech batch converter and XTTS-v2 voice cloner transforming `.txt` scripts into uncompressed `.wav` audio and **Infinite Talker** talking-head AI videos alongside Flux Klein 9B and LTX Video 2B/13B video generators. |
| **🎙️ AI Voice Autonomy** | **[MP Harmony AI Voice Agent](scripts/manage_harmony_agent.sh)** | Autonomous engineering agent running on port 11435 with background setsid detachment, zero-lag port readiness wait, model tag sanitization, automatic speech archiving, and interactive **Voice Chat CLIs** (`local-voice-talk` for MP Harmony Bridge and local Ollama models with Matrix & Stephen Hawking voice cloning). |
| **🎛️ Audio Mastering & Storage** | **Multi-Archive Routing** | Ingest and batch-convert across multiple physical drives (`MIX_ARCHIVE_DIR` & `EXTRA_MIX_ARCHIVE_DIRS`), with origin-aware output routing that deposits converted FLACs and spectrograms back to their respective origin drives. |
| **🎧 Terminal Audio Player** | **[MP Audio Player](MP_Audio_Player.py)** | "DREAMWORLDS ULTRA AUDIO MODE" expanded 118-column panoramic layout, **MP Mini & Micro Modes (`M` key)**, **In-Player Spek Generator (`G` key)**, **Track Audio Inspector HUD (`I` key)**, instant tracklist viewer (`T` key & `--tracklist`), and universal playlist exporter (`E` key & `--export-playlist`) strictly saving to `.m3u` files. |
| **📱 Social Media Outreach** | **[YouTube Shorts Generator](generate_youtube_short_promo.py)** | 1080x1920 60fps vertical promo videos with animated waveform overlays for TikTok, Instagram Reels, and YouTube Shorts. |
| **📑 Master Tracklists** | **HTML Auto-Open & Paths** | Generates master tracklists with rich file path metadata and auto-opens in default web browser. |

---

## 🌌 Spotlight: MPlanetarian Dreamworlds & TUI Navigation

> [!IMPORTANT]
> **Experience the default aesthetic, Cosmic Supernova Special Edition, and instant `/` search navigation!** MP Mix Archive Manager defaults to the **MPlanetarian Dreamworlds** theme — inspired by the iconic KDE Plasma Sweet / Nice neon aesthetic (sweet hot pink `#f72585`, electric coral `#ed254e`, vibrant orange `#ff7200`, electric cyan `#00e5ff`, and neon violet `#bd93f9`). It features a modern **zero-fork interactive TUI menu system** with real-time **`/` search filtering**, arrow-key navigation, instant Enter selection, and single-key `Esc` returns across all menus.

```mermaid
flowchart TD
    A["🌈 MPlanetarian Dreamworlds & Cosmic Supernova"] --> C["⌨️ Interactive TUI Navigation (↑/↓ Arrows, /, Enter, Esc)"]
    A --> D["🔊 Audio Chime Feedback on Theme Switch & Storage Config"]
    C --> E["⚡ Sub-20ms Zero-Fork Menu Redraws (Pure Bash Built-Ins)"]
    C --> F["🔍 Live '/' Menu Search Filtering Across Main & Submenus"]
```

### 🎨 Dreamworlds, Cosmic Supernova & Zero-Fork TUI Features:
- 🌈 **MPlanetarian Dreamworlds & Cosmic Supernova Palettes**: Hand-crafted 24-bit TrueColor RGB schemes matching KDE Plasma Sweet / Nice themes, plus the **Cosmic Supernova [Special Edition]** interstellar palette and **Old Style Unix Terminal Retro Mode (White on Black)**.
- 🔍 **Interactive `/` Menu Option Search Filtering**: Press `/` on the Main Page or any submenu to filter options in real time as you type (matching option number, title, or description via `_find_menu_search_match`), cycle matches with `Up`/`Down` arrows, press `Enter` to execute, or press `Esc` to clear the filter.
- ⚡ **Zero-Fork Bash Architecture & Sub-20ms Redraws**: Engineered for maximum responsiveness even on ultra-slow systems — `Mix_Archive_Manager.sh` and `.probe_mgr.sh` use pure Bash parameter expansion, in-memory caching, and zero external subshell forks during rendering.
- ⌨️ **Interactive Arrow-Key Navigation**: Navigate effortlessly using `Up` and `Down` arrow keys, jump with `Home` and `End`, type numbers or letters to quick-search, press `Enter` to select, and press `Esc` to instantly return to the previous screen.
- 🔊 **System Sound Feedback**: Plays soothing system audio chimes via PipeWire / ALSA when switching themes or configuring mix archive storage locations.
- 🎭 **14+ Built-in Themes**: Dreamworlds (Default), Dreamworlds Ultra (BTOP HotPurpleTrafficLight), Cosmic Supernova [Special Edition], Old Style Unix Terminal Retro (White on Black), Cyberpunk, Dracula, Nord, Matrix, Solarized, Tokyo Night, Monokai, Gruvbox, Emerald, and Classic ANSI (synchronized with `mix_web_companion.py` and `Congen` v1.1's 18-theme selector).

---

## 🎧 Spotlight: MP Audio Player (Terminal Audio Suite)

> [!TIP]
> **Built-in Audio Playback with Mini/Micro Modes, Local Spek Generation, 31K+ SMB Track Streaming & DJ Mode!** Launchable directly via **Option 1** (Advanced MUSIC Mode for SMB music folders `/MUSIC001` & `/MUSIC002`) or **Option 12** (Mix Archive Mode), or `mix-archive-manager p`, **MP Audio Player** (`MP_Audio_Player.py`) is an in-terminal high-resolution music player engineered for seamless playback of 32-bit, 24-bit, and 16-bit FLAC, WAV, MP3, OGG, and AAC tracks.

```mermaid
flowchart LR
    A["🎵 High-Res Audio Archive & 31K+ SMB MUSIC Folders"] --> B["🎛️ MP Audio Player (Option 1 & 12)"]
    B --> C["🪟 MP Mini & Micro Modes (Press M) with OSC 11 Dynamic Gradients"]
    B --> D["📊 Stardust Chroma & Neon Chroma Prism Equalizers"]
    B --> E["🔍 Track Audio Inspector HUD (Press I) & Local Spek Generator (Press G)"]
    B --> F["📜 Live Tracklist Window (Press T) & .m3u Exporter (Press E)"]
    B --> G["🎧 Bluetooth Auto-Routing (Press a) & DJ Pitch Fader (-20% to +20%)"]
```

### 🎛️ Audio Player Highlights:
- 🪟 **MP Mini Audio Player Mode (`M` Key) & Hidden MICRO Mode**: Press **`M`** to launch an independent compact transparent console window featuring **dynamic quasi-periodic color gradients** shifting smoothly via irrational phase modulation (`OSC 11`), a real-time mini equalizer, volume/pitch controls, and complete track metadata without the playlist. Press **`M`** again inside Mini Mode to toggle the ultra-compact **MICRO Mode**.
- 📊 **Local 1080p Spek Spectrogram Generator (`G` / `g` Key)**: Press **`G`** at any time during playback, browsing, or inside the Track Inspector HUD to generate a high-resolution 1920x1080 logarithmic Spek spectrogram (`.png`) for the currently selected or playing track/mix, saved directly to `SPEK_OUTPUTS`.
- 🔍 **Track Audio Inspector HUD (`I` / `i` Key)**: Opens a centered modal telemetry overlay inspecting active track format/codec, sample rate, bit depth, channels, file size, live volume & DJ pitch state, hardware audio output engine, and full SMB network or local disk path.
- 🌐 **SMB Network MUSIC Folders Streaming (Option 1)**: Connects to `/MUSIC001` and `/MUSIC002` SMB shares (`192.168.1.138`, **31,271+ tracks**) using `rclone` VFS full caching (`--vfs-cache-mode full`), pre-cached `.m3u8` playlists, and an asynchronous background **Track Duration (`00:00`)** column in the playlist browser.
- ✨ **Stardust Chroma & Neon Chroma Prism Equalizers (`e` Key)**: Includes the **Stardust Chroma** visualizer (thin vertical bars with falling dust particle physics), **Neon Chroma Prism**, Cosmic Supernova gradients, Stereo, Mirror, Fire, Rainbow, and Waves.
- 🌌 **DREAMWORLDS ULTRA AUDIO MODE & 118-Column Panoramic Grid**: High-resolution studio playback console with real-time audio telemetry, bit-depth/sample-rate metrics, stereo level meters, and dedicated DJ pitch fader window aligned flush at column 118.
- 📜 **Instant Tracklist Viewer (`T` / `t` / `--tracklist`)**: Press `T` during playback or browsing to automatically locate and launch the matching mix tracklist (`.txt`) in a dedicated borderless console window (`scripts/view_tracklist_console.sh`).
- 💾 **Universal Playlist Exporter (`E` / `w` / `--export-playlist`)**: Export the entire mix archive playlist to any directory strictly as a standard `.m3u` file (`#EXTM3U` format with `#EXTINF` track descriptions) via native `kdialog`/`zenity` or CLI.
- 🎧 **Intelligent Bluetooth Audio Auto-Routing (`[a]` Key & `monitor_bluetooth_audio.py`)**: Automatically detects connected Bluetooth headphones (Skullcandy Crusher ANC 2, Sony WH-1000XM, AirPods, Bose) in real-time via `pactl subscribe` + 1.2s polling heartbeat. Switches default output (`wpctl`/`pactl`) and migrates active streams live (`pactl move-sink-input`) while respecting manual user sink overrides.
- 🎚️ **DJ Pitch & Tempo Engine**: Real-time tempo adjustment from -20% to +20% via `[` / `]` (or `+` / `-`) with single-key reset via `\`.
- ⌨️ **Unbuffered Zero-Lag Keyboard Controls**:
  - `Space`: Instant pause / play toggle.
  - `M` / `m`: Launch **MP Mini Audio Player Mode** (press `M` again inside Mini Mode for **MICRO Mode**).
  - `G` / `g`: Generate local 1080p **Spek spectrogram** for selected / playing track or mix.
  - `I` / `i`: Open **Track Audio Inspector HUD** modal overlay.
  - `/`: Interactive live playlist search filter.
  - `Left` / `Right` arrows: Precision seek backward / forward (5s / 30s).
  - `Up` / `Down` arrows (or `v` / `V`): Volume control (0%–100%).
  - `u` / `U`: Instant audio mute / unmute toggle.
  - `[` / `]` (or `-` / `+`): Adjust DJ pitch (-20% to +20%); `\` resets pitch to 0.00%.
  - `a` / `A`: Route / check Bluetooth audio output status.
  - `T` / `t`: Open tracklist for currently selected or playing mix in dedicated window.
  - `E` / `w` / `W`: Export entire mix playlist to `.m3u` file.
  - `n` / `p`: Next / Previous track in mix catalog.
  - `c` / `C`: Cycle TrueColor visualizer theme palette (including Cosmic Supernova & Retro Unix White-on-Black).
  - `e`: Toggle EQ visualizer style (Stardust Chroma, Neon Chroma Prism, Stereo, Mirror, Fire, Rainbow, Waves, Classic).
  - `F`: Open currently selected / playing mix in desktop file manager (Dolphin / Nautilus / Explorer / Finder).
  - `s` / `r`: Shuffle / Repeat mode toggles.
  - `q` / `Esc`: Return cleanly to master manager menu.
- 🔍 **Integrated Archive Catalog Browser & Flexible Path Ingestion**: Pass specific mix audio paths directly via CLI or browse the entire catalog by mix episode, artist, title, or date with instant enter-to-play dispatch.
- 🎧 **Audio Bit-Perfect Output**: Direct integration with PipeWire, ALSA, PulseAudio, macOS CoreAudio, and WASAPI.

---

## 📱 Spotlight: DJ Booth & Studio Mobile Web Companion

> [!IMPORTANT]
> **Control your workstation from your phone or tablet in the DJ booth!** MP Mix Archive Manager includes **mix_web_companion.py** (Option 28.5 or `mix_web_companion.sh`), a zero-dependency local HTTP server running on port **`8888`** designed specifically for smartphones, tablets, and touchscreens.

```mermaid
flowchart TD
    A["💻 Workstation Host (Port 8888)"] --> B["📡 mix_web_companion.py Daemon"]
    B --> C["📱 Mobile Smartphone in DJ Booth"]
    B --> D["📲 Studio iPad / Android Tablet"]
    C & D --> E["✨ Touch-Friendly Dreamworlds Neon Web Interface"]
    E --> F["▶️ Real-Time Play / Pause / Seek / Volume Controls"]
    E --> G["📜 Live Tracklist & Session Timecode Inspection"]
    E --> H["📁 Interactive Mix Archive Catalog Browser & Trigger"]
```

### 📱 Mobile Web Companion Highlights:
- 🌐 **Zero Dependencies**: Powered by Python's built-in standard library HTTP server (`mix_web_companion.py`) — requires no external Node.js, Flask, or heavy web frameworks.
- 🎨 **Responsive Dreamworlds UI**: Tailored dark neon palette optimized for OLED mobile displays in low-light DJ booths and studio environments.
- 🎛️ **Full Remote Control**: Play, pause, skip, seek, mute, adjust master volume, inspect now-playing audio bit depth/sample rate, and browse the mix archive catalog over local Wi-Fi.
- 🔒 **Local Network Isolation**: Binds securely to your local LAN IP (`http://<WORKSTATION-IP>:8888`) with optional trusted-host verification.

---

## 🎬 Spotlight: YouTube Shorts 1080x1920 Promotional Video Generator

> [!TIP]
> **Need vertical social media promo videos for YouTube Shorts, Instagram Reels, or TikTok?** Option 20.7 (`generate_youtube_short_promo.py`) automatically synthesizes dynamic **1080x1920 vertical videos** (42 seconds default) straight from your master FLAC mix and cover art!

```mermaid
flowchart LR
    A["🎵 Master FLAC / WAV Mix"] & B["🖼️ Album / Episode Cover Art"] --> C["🎬 generate_youtube_short_promo.py"]
    C --> D["📊 Vertical Audio Waveform Synthesizer"]
    C --> E["✨ Dreamworlds Gradient Background & Particles"]
    C --> F["🔤 Title, Artist & Episode Typography Overlay"]
    D & E & F --> G["📱 1080x1920 60fps MP4 (NVENC / H.264 Accelerated)"]
    G --> H["🚀 Instant Social Upload: YouTube Shorts / TikTok / Reels"]
```

### 🎥 Shorts Generator Highlights:
- 📐 **True 1080x1920 Vertical Canvas**: Perfectly formatted for YouTube Shorts, Instagram Reels, and TikTok without letterboxing.
- 🌊 **Dynamic Audio Visualizer**: Renders an animated audio waveform reflecting the highest-energy section of your mix.
- 🚀 **Hardware Acceleration**: Automatic GPU encoding using NVIDIA NVENC (`h264_nvenc`), Apple VideoToolbox (`h264_videotoolbox`), or CPU `libx264`.
- 🎚️ **Smooth Audio Fades**: Includes studio-grade 320kbps AAC audio with smooth 1.5s intro and outro fades.

---

## 🎥 Spotlight: Screencast YouTube Video Generator with NVENC & Image Transitions

> [!TIP]
> **Need full-length 1080p/4K YouTube videos with seamless image transitions for live streams and studio sessions?** Located in `scripts/generate_screencast_youtube_video.py`, this tool automates full episode screencast rendering with hardware-accelerated NVIDIA NVENC encoding, cyclic artwork transitions, and broadcast-grade audio mastering.

```mermaid
flowchart LR
    A["🎬 Screencast Video (.mp4)"] & B["🎵 Studio Mix (.wav / .flac)"] --> C["🎥 generate_screencast_youtube_video.py"]
    C --> D["⚡ NVIDIA NVENC (h264_nvenc 1080p 60/30fps)"]
    C --> E["🖼️ 5s Intro & Outro Studio Fades to Black"]
    C --> F["🔄 Cyclic 5-Min Image Transitions (Artwork Carousel)"]
    C --> G["🎚️ 320kbps High-Fidelity AAC Audio Loop"]
    D & E & F & G --> H["🚀 Ready-to-Publish YouTube Video (.mp4)"]
```

### 🎬 Screencast Video Generator Highlights:
- ⚡ **Hardware-Accelerated NVIDIA NVENC**: Leverages dedicated NVENC silicon (`h264_nvenc`) for blazing-fast 1080p / 4K video rendering without pegging CPU cores.
- 🖼️ **Seamless 5-Minute Image Transitions**: Automatically cycles through high-resolution episode artwork and interface graphics every 5 minutes with smooth 1-second crossfades.
- 🌑 **Studio Intro & Outro Fades**: Elegant 5-second fade-in from black at video start and 5-second fade-out to black at video conclusion.
- 🎶 **Broadcast-Grade Looped Audio**: Synchronizes pristine 320kbps AAC studio audio, looping seamlessly to match video length with smooth 5-second audio intro/outro envelopes.
- ⏱️ **Uniform Timescale Architecture**: Single-stream segment concatenation enforcing a standardized 90,000 timescale to eliminate audio/video desync and YouTube processing errors.

---

## 🤖 Spotlight: Next-Gen AI Orchestration, Matrix Voice Lab & Infinite Talker Suite

> [!IMPORTANT]
> **Orchestrate Local LLMs, Matrix & Stephen Hawking Neural Voice Cloning, Infinite Talker AI Video Synthesis, and System Diagnostics from One Central Hub!** Main menu **Option 33** unites local and remote artificial intelligence pipelines:

```mermaid
flowchart TD
    A["🤖 AI Assistant & Local LLM Servers Suite (Option 33)"] --> B["🎙️ MP Harmony AI Agent (:11435)"]
    A --> C["🌐 Open WebUI v0.12.2 Chat Harness (:42004 / :8080)"]
    A --> D["🦙 Ollama Server & 32K CUDA Models (:11434)"]
    A --> E["📱 DeepSeek Harness Server dsh-mobile (:3080)"]
    A --> F["🎥 WAN2GP AI Video, Infinite Talker & TTS Suite"]
    A --> G["📊 Beszel Workstation & GPU Hub (:8090)"]
    B --> B1["🗣️ Matrix & Stephen Hawking Voice Chat CLI + Speech Archive"]
    D --> D1["⚡ 32K Context CUDA Flash-Attention & Auto VRAM Unload"]
    F --> F1["🗣️ XTTS-v2 & Edge-TTS Voice Cloning Batch Converter"]
    F --> F2["🎬 WAN2GP Infinite Talker (Talking-Head AI Video)"]
    F --> F3["🎞️ Flux Klein 9B, LTX Video 2B/13B & Live Output Monitor"]
```

### 🧠 AI Suite Capabilities:
- 🎙️ **MP Harmony AI Agent & Speech Archive** (`manage_harmony_agent.sh` / Option 33.4): Autonomous engineering agent and voice bridge running on port 11435. Includes background daemon with setsid detachment, zero-lag port readiness wait, automatic speech recording to the **MP Harmony Agent Audio Speech Archive**, and interactive **Voice Chat CLIs** (`local-voice-talk` for Harmony Agent or local Ollama models).
- 🕶️ **Matrix Cast & Stephen Hawking Voice Cloning Lab**: Full neural XTTS-v2 and Edge-TTS voice synthesis featuring **Agent Smith / Elrond (Hugo Weaving)**, **5 Morpheus variants** (Construct, Red Pill, Dojo, System, Classic), **Neo**, **Trinity**, **The Oracle**, **Zion**, and **Stephen Hawking (Enters the Matrix)** with authentic acoustic pacing.
- 🎬 **WAN2GP Infinite Talker AI Video & Output Monitors** (`wan2gp.sh`, `wan2gp_tts_batch.py`, `wan2gp_flux_batch.py`, `wan2gp_ltx_batch.py`):
  - **Infinite Talker Integration**: Generates talking-head AI videos (including Stephen Hawking talking-head video briefings) with configurable video length and automatic Python `.venv` discovery.
  - **Live Output Monitors**: Dedicated real-time **WAN2GP Video Output Monitor (`--wan2gp-monitor`)** and **Audio/Video File Output Monitor (`--audio-monitor`)**, plus one-click WAN2GP upstream Git updating.
  - **Text-to-Speech (TTS) Batch Suite**: Converts `.txt` scripts into uncompressed `.wav` speech audio with Matrix/Hawking/British neural voices and interactive playback.
  - **Video Batch Generators**: Flux Klein 9B and LTX Video 2B/13B generation profiles (Profiles 2 and 4.5).
- 🌐 **Open WebUI v0.12.2 Web Chat** (`scripts/manage_open_webui.sh` / Option 33.3): Browser-based chat interface connected to local models on port 42004 / 8080 with automatic version update support.
- 🦙 **Ollama Server & 32K CUDA Models** (`manage_ollama.sh` / Option 33.2): Distrobox / host controller on port 11434 tuned for **32K context windows (`num_ctx 32768`)**, CUDA flash-attention, automatic GPU VRAM unloading, model puller (`qwen2.5`, `llama3.1`, `nemotron`), and CLI voice/text chat.
- 📱 **DeepSeek Harness (`dsh-mobile`) & Token Manager** (`scripts/dsh_mobile.sh` / Option 33.5): Web chat harness on port 3080 optimized for mobile devices with interactive access token management.
- 📊 **Beszel Server Monitoring Hub & Agent** (`beszel.sh` / Option 33.7): Real-time hardware, CPU, NVIDIA GPU, and container telemetry web dashboard on port 8090.

---

## 📊 Spotlight: MP Reporter Suite, AI Brain Logs & Automated Email Briefings

> [!IMPORTANT]
> **Automated Daily, Weekly, Monthly, and Yearly Workstation & Mix Intelligence Reports!** Launchable via **Option 27** (`mp_report_generator.py`, `mp_scheduled_reporter.sh`, `manage_mp_reporter.sh`), the **MP Reporter Suite** aggregates mix archive statistics, task completions, AI agent activity, and system telemetry into styled HTML5 dashboards, printable PDFs, Stephen Hawking audio/video briefings, and scheduled SMTP emails.

### 📈 MP Reporter Highlights:
- 🗓️ **Multi-Period Intelligence Architecture**: Generates **Daily, Weekly, Monthly, and Yearly** reports organized cleanly into `REPORTS/{DAILY,WEEKLY,MONTHLY,YEARLY}` with backward-compatible symlinks and an interactive **12-Month Calendar Dashboard**.
- 🧠 **Daily AI Brain Logs Reporter**: Automatically scans and summarizes activity across **Google Gemini**, **Grok**, and **local LLM models** alongside system and mix archive tasks.
- 🗣️ **Stephen Hawking TTS Audio & Infinite Talker Video Briefings**: Synthesizes spoken audio report briefings in Stephen Hawking's signature voice and optionally renders talking-head AI video briefings via **WAN2GP Infinite Talker**.
- 📧 **Automated SMTP Email Distribution (`mp_email_manager.sh`)**: Sends formatted daily/periodic HTML & PDF intelligence briefings directly to configured email recipients on a systemd/cron schedule.

---

## 📱 Spotlight: Congen v1.1 by Dreamworlds Productions (MPlanetarian)

> [!IMPORTANT]
> **Control your entire Linux workstation, custom scripts, and media workflows straight from your smartphone!** Located in [Congen/](Congen/README.md) and launchable directly via `mix-archive-manager --congen` or Option 29, **Congen v1.1 by Dreamworlds Productions (MPlanetarian)** is an enterprise-grade terminal command orchestration suite and interactive CLI manager for KDE Connect (Plasma 6 & 5).

```mermaid
flowchart TD
    subgraph MobileEndpoints["📱 Paired Mobile Endpoints"]
        Android["Android Phone / Tablet\n(KDE Connect App)"]
        iPhone["Apple iPhone / iPad\n(KDE Connect App)"]
    end

    subgraph CongenEngine["⚡ Congen v1.1 Engine"]
        TUI["11 Interactive Menus\n(18 TrueColor Palettes)"]
        AlertDaemon["Auditory Chime Daemon\n(.congen_alert_daemon.sh)"]
        DocGenerator["Multi-Format Manuals\n(TXT / HTML5 / PDF)"]
        SchedulerEngine["Dual-Backend Scheduler\n(at / systemd-run)"]
        DesktopIntegration["Desktop Shortcut Manager\n(kioclient & kwriteconfig6)"]
    end

    subgraph DesktopTargets["💻 Linux Host System & Studio Workstation"]
        KDECD["kdeconnectd Daemon\n(~/.config/kdeconnect/)"]
        StudioScripts["Mix Manager Scripts & Audio DAWs"]
        WorkstationApps["System Commands, AI Servers & Hotkeys"]
    end

    MobileEndpoints <-->|Encrypted Local Wi-Fi / TLS| KDECD
    KDECD <--> CongenEngine
    CongenEngine --> StudioScripts
    CongenEngine --> WorkstationApps
    AlertDaemon -.->|Plays .congen_alert.wav on Trigger| DesktopTargets
```

### 📱 Congen v1.1 Feature Highlights:
- 🎛️ **11 Interactive Menus**: Create commands (`[1]`), view & remove (`[2]`), direct terminal execution (`[3]`), task scheduling (`[4]`), audit logging (`[5]`), import/export management (`[6]`), multi-format documentation (`[7]`), auditory alerts (`[8]`), keyboard shortcut generator (`[9]`), desktop shortcut manager (`[10]`), and theme switcher (`[11]`).
- 🎨 **18 TrueColor Themes**: Choose between MPlanetarian Dreamworlds (default), Dreamworlds Ultra, Cosmic Supernova [Special Edition], Old Style Unix Terminal Retro (White on Black), Cyberpunk, Dracula, Nord, Matrix, Solarized, Tokyo Night, Monokai, Gruvbox, Emerald, Classic ANSI, and more.
- 🔔 **Algorithmic Chime Alert Daemon**: Background daemon (`.congen_alert_daemon.sh`) monitors remote executions and plays an algorithmic two-tone chime (`.congen_alert.wav`, 1047 Hz → 1319 Hz) generated purely via Python standard library with zero binary media dependencies.
- 🖥️ **Desktop Shortcut Manager (`[10]`)**: Discovers `.desktop` launchers, executes immediately via `kioclient exec`, binds global hotkeys via `kwriteconfig6` into `kglobalshortcutsrc`, and schedules future launches via `at` or `systemd-run`.
- ⌨️ **Keyboard Shortcut Generator (`[9]`)**: Translates KDE global shortcuts into standalone executable scripts using `xdotool` (X11) or `ydotool` (Wayland), registering them as remote mobile triggers.
- 📑 **Multi-Format Manual Generator (`[7]`)**: Generates structured Plain Text (`.txt`), responsive modern dark-mode HTML5 (`.html`), and print-ready PDF (`.pdf`) via an automated converter cascade (`wkhtmltopdf` → `chromium` → `google-chrome` → `weasyprint`).
- 🤖 **Headless CLI & Scripting Suite**: Full non-interactive automation suite (`congen list [--json]`, `congen run`, `congen add`, `congen remove`, `congen status`, `congen ping`, `congen theme`, `congen alert`) for scripts, hotkeys, and pipelines.
- ⚡ **High-Performance Engine & Atomic Safety**: Global telemetry TTL caching (<20ms menu redraws), elimination of N+1 subprocess bottlenecks via batch extraction, live search filtering (`[s]` / `[/]`), and atomic config writes with `.bak` safety backups.
- 📦 **30+ Bundled Command Profiles (`CONGEN_IMPORT/`)**: Pre-configured profiles for Ollama, WAN2GP AI Video, Beszel, DeepSeek, Steam, Strawberry Player, Audacity, VLC, Audio Mute/Unmute, and LAN-only Internet Kill-Switch with multi-device deduplication.

👉 **Explore the dedicated documentation:** [Congen/README.md](Congen/README.md)

---

## ✂️ Spotlight: Auto-Split DJ Mixes & Multi-Part Spek Spectrograms

> [!TIP]
> **Recorded a 4-hour live stream with 4 different DJ sets?** When converting large audio files, MP Mix Archive Manager automatically prompts you: *"Would you like to split the audio file?"*. It slices the audio into equal or custom parts, saves the split files into the **exact same directory**, and offers to generate **individual 1080p Spek spectrograms** for every split part!

```mermaid
flowchart LR
    A["🎧 Audio Conversion Finishes (WAV / FLAC / MP3 / OGG)"] --> B{"✂️ Split Audio File? [y/N]"}
    B -- Yes --> C["🔢 Choose Number of Parts (e.g. 4 DJ Mixes)"]
    C --> D["📁 Output Split Parts to Same Directory"]
    D --> E{"📊 Generate Spek Spectrograms for All Parts? [Y/n]"}
    E -- Yes --> F["🖼️ 1920x1080 Logarithmic Spectrogram for Each Part"]
    B -- No --> G["✅ Continue Ingestion / Archive Workflow"]
    E -- No --> G
```

### 🎛️ Audio Splitting & Spectrogram Highlights:
- 🔁 **Every-Time Conversion Prompt**: Never miss splitting a multi-DJ recording session. Immediately upon conversion completion, the system asks if you want to split the file.
- 📁 **Same Output Directory**: All split parts are saved right alongside the converted audio file.
- 📊 **Batch Spek Spectrogram Generation**: One-click generation of ultra-clean 1920x1080 logarithmic audio spectrograms for every individual split set, proving lossless frequency cutoffs and audio mastering health.
- 🦭 **Full Ogg Vorbis Support**: Seamlessly ingest and convert to/from Ogg Vorbis (`.ogg`) at audio quality (Q8 / Q10 / 320 kbps) across all single and batch conversion routines.
- 🧩 **Multi-Archive Origin-Aware Routing**: Batch conversion detects which archive disk source WAV files came from and automatically deposits converted FLACs and spectrograms back to their respective origin drives.

---

## ⏰ Spotlight: MPlanetarians Alarm Clock (Wake Up Edition)

> [!IMPORTANT]
> **Tired of boring buzzer alarms?** MP Mix Archive Manager includes **MPlanetarians Alarm Clock (Wake Up Edition)** — an invigorating morning wake-up system that blasts a random mix from your local FLAC archive through Strawberry or cliamp, unmuting and ramping volume up over 3 minutes. It tracks your mouse to detect when you're truly awake, opens your default web browser on your secondary right-hand monitor, and queries your Steam library to offer **3 random video games to play for breakfast**! *(Linux Only Support at the Moment)*.

```mermaid
flowchart TD
    A["⏰ Morning Alarm Triggers (systemd User Timer)"] --> B["🔊 Unmute Audio & 3-Minute Volume Ramp (0% → 100%)"]
    B --> C["🎶 Random Archive FLAC Mix on Strawberry / cliamp"]
    C --> D{"🖱️ Mouse Motion Detected?"}
    D -- "No (Mouse Idle for 10 Min)" --> C2["🔀 Switch to Different Local Archive Mix"]
    C2 --> D
    D -- "Yes (Woke Up!)" --> E["🛑 Silence Alarm & Record Wake-Up Time"]
    E --> F["🌐 Open Web Browser on Right Display"]
    E --> G["🎮 Query Steam Library (libraryfolders.vdf)"]
    G --> H["🕹️ Offer 3 Random Steam Games to Play for Breakfast"]
    E --> I["📰 Display Morning Brief: Weather, News, Hardware & Daily Phrase"]
```

### 🌟 Why This Morning Wake-Up Experience Is Game-Changing:
- 🎵 **High-Energy Lossless Wake-Up**: Randomly selects between **Strawberry** and **cliamp**, pulls a random high-resolution mix from your local archive disks (safely skipping cloud mounts), starts softly, and steadily ramps up the volume over 3 minutes until full alarm volume.
- 🖱️ **Active Movement Wake Detection**: Move the mouse to silence the alarm. If your mouse stays still for 10 minutes, the clock knows you fell back asleep and starts playing a completely different archive mix!
- 🎮 **Steam Video Game for Breakfast**: Automatically parses your Steam library (`libraryfolders.vdf`), filters out developer tools and runtimes, and presents 3 random games from your collection, asking: *"Would you like to play a game for breakfast?"* Launch any chosen title directly into Steam with a single keypress!
- 🖥️ **Smart Dual-Screen Browser Placement**: Automatically calculates your monitor coordinates and opens your morning browser window on the display directly to the right of your primary screen.
- ☀️ **Morning Screen & Daily Brief**: Features an animated clock, daily weather forecast, rain alerts, exercise routine, healthy breakfast ideas, system hardware vitals, manual page of the day, and internet word/phrase of the day.
- 🎨 **4 Elegant Color Themes**: Midnight Ink (navy and silver), Warm Brass (amber lamp-light), Forest Hour (deep green and gold), and Porcelain (warm grey and rose).
- 📊 **Main Page Live Status Banner**: The MP Mix Archive Manager main dashboard directly displays your alarm arm state, next alarm countdown, active sound target, Steam library readiness, and morning wake-up action at a glance.
- 🐧 **Linux-Native System Integration**: Powered by systemd user timers, PipeWire `wpctl`, `xdotool`, and Steam Linux desktop protocols.

---

## ⚡ Spotlight: Traktor History Harmonic Playlist & Stage Setup

> [!IMPORTANT]
> **DJing on macOS with Native Instruments Traktor Pro?** You can convert past live gig recordings and rehearsal history logs into clean, harmonically organized playlists and launch straight into your next mix with a single keypress.

```mermaid
flowchart LR
    A["📜 Traktor History (.nml)"] --> B["🔎 Terminal Session Browser"]
    B --> C["👁️ Console Tracklist Preview"]
    C --> D["🎹 Harmonic Key Sorter (Ascending 1A-12B)"]
    D --> E["📁 Root Playlists Collection ($ROOT)"]
    E --> F["🖥️ Full-Screen Traktor Pro Launch"]
    F --> G["🎛️ Auto-Load Decks A, B, C & D"]
```

### 🎧 Why Every Traktor DJ on Mac/Windows Needs This:
- 🔍 **Auto-Detection Across Traktor Versions**: Automatically detects your installed Traktor Pro release (Traktor 3, Traktor Pro 3.11+, Traktor Pro 4) and discovers session History `.nml` archives without manual path configuration.
- 📜 **Interactive Session History Browser**: Lists all past performance sessions with session dates, start timestamps, and total tracks played.
- 👁️ **Console Tracklist Preview**: Inspect the full played setlist (Artist, Title, Duration, Key, BPM) in your terminal *before* committing to generate.
- 🎹 **Harmonic Key Ascending Order**: Tracks are automatically sorted in ascending musical / Camelot key order (1A–12B), ensuring harmonic mixing compatibility right from the first transition!
- 📁 **Native Traktor Playlist Injection**: Generates a standard Traktor playlist `.nml` directly inside Traktor's default Root Playlists directory (`$ROOT`), appearing immediately in Traktor's browser tree.
- 🚀 **Instant Full-Screen Stage Dispatch**: Automatically brings Traktor Pro to the front in **Full Screen** mode and pre-loads Decks A, B, C, and D with the first four tracks.

---

## 🎛️ Spotlight: EBU R128 Loudness Mastering, Audio Audit & CUE Engine

> [!TIP]
> **Deliver studio-grade loudness compliance and verify audio integrity before publishing!** Located in **Option 2** and **Option 8**, the audio mastering suite gives you precision control over dynamics, spectral purity, and archive longevity:

```mermaid
flowchart TD
    A["🎵 Input Mix (WAV / FLAC / MP3)"] --> B["🎛️ EBU R128 Loudness Scanner & Normalizer (master_audio_loudness.py)"]
    B --> C{"Target Profile"}
    C -->|Streaming| C1["-14 LUFS / -1.0 dBTP (Spotify, YouTube, Apple)"]
    C -->|Podcasts| C2["-16 LUFS / -1.0 dBTP (Apple Podcasts, RSS)"]
    C -->|Broadcast| C3["-23 LUFS (EBU R128 Television / Radio)"]
    C -->|DJ / Club| C4["-10.5 LUFS / -0.3 dBTP (Club Sound Systems)"]
    A --> D["🔍 Mastering Quality Audit (verify_audio_mastering.py)"]
    D --> D1["True Peak (ISP) Check • Mono Phase Correlation • Leading Silence Audit"]
    A --> E["🔬 Lossless Legitimacy Inspector (verify_lossless_spectral.py)"]
    E --> E1["Multi-Segment FFT Power Analysis: Detects Fake FLACs & Lossy Transcodes"]
    A --> F["🛡️ Background Bit-Rot Scrubber (scrub_mix_archive.sh)"]
    F --> F1["Low-Priority Background Frame Verification & Systemd User Timer"]
    A --> G["📜 Red Book CUE Sheet Engine (generate_cue_sheet.py)"]
    G --> G1["Frame-Accurate MM:SS:FF Indices & Lossless Track Splitter"]
```

---

## 🔍 Spotlight: Audio Fingerprinting, Chapters & Rekordbox Export

> [!IMPORTANT]
> **Bridge your audio archives with modern streaming platforms and DJ hardware!**

- 🔍 **Acoustic Fingerprinting & Track Identification** (`identify_mix_tracks.py` / Option 12.7): Automatically identifies unknown tracks in live DJ recordings by extracting audio fingerprint snippets and querying AcoustID / Chromaprint (`fpcalc`) and online recognition endpoints.
- 📑 **YouTube & SoundCloud Chapter Exporter** (`export_chapters.py` / Option 12.6): Parses tracklists or CUE sheets to generate clean YouTube description chapters (`00:00:00 Artist - Title`), SoundCloud timestamps, and Markdown tables, automatically copying them to your clipboard (`wl-copy`, `xclip`, `pbcopy`).
- 💿 **Pioneer Rekordbox XML Exporter** (`export_rekordbox_playlist.py` / Option 15.5): Converts Traktor `.nml` histories, CUE sheets, and M3U playlists into standard Pioneer Rekordbox XML (`DJ_PLAYLISTS.xml`), ready for direct import and export to Pioneer CDJ USB drives.
- 🏷️ **Lossless ReplayGain & Metadata Tagger** (`tag_audio_metadata.py` / Option 2.12): Analyzes EBU R128 loudness to write non-destructive Vorbis comments (`REPLAYGAIN_TRACK_GAIN`, `REPLAYGAIN_TRACK_PEAK`) and embeds front cover art into FLAC headers (`metaflac`) without touching audio bits.

---

## 🖥️ Spotlight: KDE Plasma Desktop Shortcuts & Global Keyboard Binder

> [!TIP]
> **Control your workstation tools and AI servers without touching the mouse!** Main menu **Option 0** provides dedicated Linux KDE Plasma desktop automation:

- 🖥️ **Manual Shortcut Runner**: Automatically indexes `.desktop` shortcuts across `~/Desktop`, `~/Desktop/DESKTOP`, and `~/.local/share/applications`, presenting an interactive categorized launcher for games, tools, and servers via `kioclient`.
- ⌨️ **Global Keyboard Shortcut Generator**: Select any installed desktop application or custom script and bind it to a global hotkey (e.g. `Ctrl+Alt+Return`, `Meta+Shift+A`). Automatically registers the binding directly in KDE's `kglobalshortcutsrc` and reloads `kglobalaccel` over D-Bus!

---

## 📢 Spotlight: Unified Multi-Channel Notification Dispatcher

> [!IMPORTANT]
> **Get notified on your phone when 4-hour batch conversions or cloud backups finish!** The unified notification dispatcher (`scripts/send_notification.sh`) broadcasts status updates across four channels simultaneously:

- 🖥️ **Desktop GUI Notifications**: Dispatches native notifications via `notify-send` (Linux), `osascript` (macOS), or PowerShell toast notifications (Windows).
- 💬 **Discord Webhooks**: Posts rich markdown embed notifications to your private Discord server.
- 📱 **Telegram Bot Alerts**: Sends real-time messages to your Telegram chat or channel via the Telegram Bot API.
- 🔔 **Pushover Push Notifications**: Delivers instant push notifications to your iOS and Android devices.

---

## 🚀 Quick Start by Operating System

### 1. Linux (Bazzite / SteamOS / Fedora / Ubuntu / Arch)
For a fresh, step-by-step installation guide from a clean Bazzite Linux setup, see **[INSTALL_BAZZITE.md](INSTALL_BAZZITE.md)**.

```bash
cd ~/MP_Mix_Manager_v0.3
chmod +x install.sh
./install.sh
```

**Launch the Master Console:**
```bash
manager
# or:
./manager.sh
# or launch directly from your application launcher / desktop icon
```

---

### 2. Apple macOS (Sequoia, Sonoma, Apple Silicon M1–M4 & Intel)

#### Prerequisites
Install [Homebrew](https://brew.sh) (if not already installed):
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Install command-line tools:
```bash
brew install bash ffmpeg sox flac rclone jq btop python
```

*(Optional) Install audio/video GUI tools:*
```bash
brew install --cask vlc audacity strawberry musicbrainz-picard gimp reaper foobar2000
```

#### Running on macOS
1. Run the installer:
   ```bash
   cd ~/MP_Mix_Manager_v0.3
   chmod +x install.sh
   ./install.sh
   ```
2. **Double-click** `manager_macos.command` in Finder, or run:
   ```bash
   ./manager_macos.command
   ```
3. **One-Click Traktor Prep:** Press **`15`** ➔ **`3`** to convert any past session into an ascending musical key playlist, inject it into Traktor, and auto-load all 4 decks ready to mix!

---

### 3. Microsoft Windows 10 & 11

#### Prerequisites
MP Mix Archive Manager runs natively on Windows using **Git Bash** or **WSL2**:
- **Git for Windows (Recommended)**: Download from [https://git-scm.com/download/win](https://git-scm.com/download/win).
- **Windows Terminal**: Built-in on Windows 11; available via Microsoft Store on Windows 10.

Install recommended utilities using `winget` in PowerShell:
```powershell
winget install Gyan.FFmpeg Rclone.Rclone jqlang.jq
winget install VideoLAN.VLC Audacity.Audacity MusicBrainz.Picard GIMP.GIMP Cockos.REAPER foobar2000.foobar2000
```

#### Running on Windows
- **Double-click** `manager.bat` or `manager.ps1` from File Explorer.
- Or run inside Git Bash:
  ```bash
  ./Mix_Archive_Manager.sh
  ```

---

### 4. FreeBSD (14.x / 15-CURRENT)

#### Prerequisites
Install dependencies using `pkg`:
```bash
pkg install -y bash python3 ffmpeg sox flac rclone jq btop git py311-mutagen py311-reportlab py311-pillow
```

#### Running on FreeBSD
```bash
cd ~/MP_Mix_Manager_v0.3
chmod +x manager_freebsd.sh install.sh
./manager_freebsd.sh
```

---

## 🎛️ Master Feature Matrix (3 Sections, Options 0–36)

### ─── [ SECTION 1: MIX ARCHIVE WORKFLOW & INGESTION ] ──────────
| # | Operation | Description & Sub-Features |
|---|---|---|
| **0** | **Run Any Desktop Shortcuts — Linux** | Interactive launcher and global keyboard shortcut binder for all KDE Plasma desktop applications, games, audio tools, and AI servers (`_run_desktop_shortcut_manual` & `_bind_desktop_shortcut_keyboard`). |
| **1** | **NEW Feature - Play Tracks from MUSIC Folders using MP Audio Player (Advanced Mode)** | High-performance music tracks playback engine connecting to remote SMB network shares (`/MUSIC001` and `/MUSIC002` at 192.168.1.138, 31,271+ tracks). Features `rclone` VFS full caching (`--vfs-cache-mode full`), pre-cached playlists (`DJ_Tracks_ALL_MUSIC_FOLDERS.m3u8`), asynchronous **Track Duration (`00:00`)** column, **MP Mini & Micro Modes (`M`)**, **In-Player Spek Generator (`G`)**, and the modal **Track Audio Inspector HUD (`I`)**. |
| **2** | **Run Mix Conversion** | High-performance zero-fork batch conversion (`Make_SOF_FLAC_CONVERSION.sh`): multi-archive scanning across configured storage drives, origin-aware output destination routing, sample-accurate split WAV concatenation, 32-bit FLAC encoding, cover art embedding, and Spek spectrogram generation with post-conversion splitting prompt. |
| **3** | **Audio Conversion, EBU R128 Mastering & CUE Sheets** | Comprehensive audio conversion and mastering suite (`convert_audio_format.sh`): converts between FLAC, MP3, Ogg Vorbis, Opus, AAC, ALAC, and WAV bit depths (16/24/32-bit float/int); 2-pass EBU R128 loudness normalizer (`master_audio_loudness.py`); Red Book CUE sheet engine (`generate_cue_sheet.py`); mastering quality audit (`verify_audio_mastering.py`); and Vorbis tag / ReplayGain tagger (`tag_audio_metadata.py`). |
| **4** | **Retrieve Unconverted WAVs from Archive** | Scans archive storage and quarantines/moves unconverted WAV files lacking a matching FLAC master back to the staging area (`MOVE_NOT_CONVERTED_WAVS.sh`). |
| **5** | **Search & Import Mixes from Local Drives & SMB** | Auto-discovers local storage volumes, USB drives, and SMB network shares (`search_and_import_mixes.sh` / `import_new_mixes.sh`). Filters by mix size (>=100MB), deduplicates against archive, and copies with live progress and audit logging. |
| **6** | **Rename a Mix and Associated Assets** | Atomically renames master FLAC files, `.txt` tracklists, and `.png` Spek spectrograms across all archive directories simultaneously. |
| **7** | **Find & Remove Duplicate Audio Files / Mixes** | Deterministic two-tier O(1) partial-hash pre-filter + full SHA-256 and episode duplicate detector (`find_duplicate_mixes.py`); supports audit reports, quarantine to `DUPLICATES_QUARANTINE/`, or safe deletion. |
| **8** | **Export / Copy Mixes to Specified Path** | Bundles and copies complete mix packages (FLAC + Covers + Tracklists TXT/HTML/PDF + Spek) or filtered assets to removable USB flash drives or external directories. |
| **9** | **Audio Integrity, Bit-Rot Scrub & FLAC Verification** | Multi-level integrity suite (`manage_integrity_and_verification`): SHA-256 manifests (`manage_checksums.sh`), multi-threaded FLAC bitstream scanner (`Verify_FLAC_Files.sh`), FFT spectral cutoff inspector to detect fake FLACs (`verify_lossless_spectral.py`), and non-destructive background bit-rot scrub daemon with systemd user timer (`scrub_mix_archive.sh`). |
| **10**| **Cloud & Remote Backup Suite** | Automated multi-cloud backup engine (`backup_mix_archive.sh`): rclone integration for Google Drive, iCloud Drive, Dropbox, and custom destinations with companion asset bundling and sync state badging. |
| **11**| **Storage Management & Multiple Mix Archives Setup** | Displays drive capacity, mount point, free space progress bars, and file counts for all configured mix archive drives; full rescan and refresh; and secondary archive folder configuration (`EXTRA_MIX_ARCHIVE_DIRS`). |

---

### ─── [ SECTION 2: STUDIO AUDIO, PLAYBACK, METADATA & VIDEO ] ──
| # | Operation | Description & Sub-Features |
|---|---|---|
| **12**| **Play Mix/Audio File (MP Audio Player)** | Built-in terminal audio player (`MP_Audio_Player.py`): "DREAMWORLDS ULTRA AUDIO MODE" expanded 118-column layout, **MP Mini & Micro Modes (`M` key)** with dynamic OSC 11 color gradients, **In-Player Spek Generator (`G` key)**, **Track Audio Inspector HUD (`I` key)**, **Stardust Chroma & Neon Chroma Prism** equalizers, Bluetooth auto-routing (`a` key), dedicated tracklist viewer (`T` / `-t`), universal playlist exporter (`E` / `-e` strictly saving as `.m3u` files), DJ pitch fader (-20% to +20%), and bit-perfect lossless 32-bit/24-bit/16-bit FLAC/WAV/MP3/OGG playback. |
| **13**| **Tracklist Management, Scanning & Metadata Suite** | Complete metadata suite (`manage_tracklist_suite`): browse/search archive tracklists, view in borderless console, export to styled HTML and vector PDF (`generate_tracklist_docs.py`), Traktor XML history extractor (`Check_Find_Tracklists.sh`), master HTML index generator with browser auto-open (`Generate_Master_Tracklist.sh`), MusicBrainz Picard tagger, YouTube/SoundCloud chapter exporter (`export_chapters.py`), and AcoustID audio fingerprint identifier (`identify_mix_tracks.py`). |
| **14**| **Audio Players & Retro Playback Suite** | Universal player launcher (`manage_audio_players`): cliamp retro terminal player, Audacious, VLC, Haruna, Kodi, Strawberry, foobar2000 (macOS & Windows), Winamp (Windows), Apple Music (macOS), Apple Podcasts, Audacity, and MIDI hardware device inspector. |
| **15**| **Configure Mix Archive Storage Locations** | Interactive setup wizard for primary mix storage folder (`MIX_ARCHIVE_DIR`) and additional secondary archive drives (`EXTRA_MIX_ARCHIVE_DIRS`). |
| **16**| **Custom Mix Playlists & Traktor History Suite** | Playlist suite (`manage_playlists_and_history`): create/edit `.m3u8` / `.xspf` playlists, generate Mix Archive Folder Playlists (`PLAYLISTS_GENERATED`), macOS Native Traktor history-to-harmonic playlist converter (1A–12B Camelot order with 4-deck full-screen stage loader), Top 5 Tracks launcher, and Pioneer Rekordbox XML playlist exporter (`export_rekordbox_playlist.py`). |
| **17**| **Digital Audio Workstations (DAWs) & Mix Dispatch** | Unified launch hub (`manage_daws_suite`): REAPER, Logic Pro (macOS), FL Studio (macOS, Windows, Linux via Wine), GarageBand, Ardour, LMMS, Bitwig Studio, Bespoke Synth, and direct mix search & dispatch into DAW. |
| **18**| **Studio Hardware, Audio Interfaces & Master Volume Control** | Studio diagnostics (`manage_studio_hardware_and_volume`): PipeWire, ALSA, PulseAudio, macOS CoreAudio, and Windows WASAPI hardware inspector (`inspect_audio_studio.sh`), USB MIDI controller mapper, and instant live master audio mute/unmute toggle (`wpctl`/`pactl`/AppleScript). |
| **19**| **Spectrogram Generation & Audio Frequency Analysis** | Acoustic spectrogram suite (`manage_spek_generation` / `generate_spek.sh`): single-file and batch directory 1080p logarithmic Spek generation, native Spek GUI launcher, SPEK_OUTPUTS browser, Sonic Visualiser, SoX multi-colormap spectrograms, and Praat analysis. |
| **20**| **Morning Alarm Clock & DJ Mix Playback Suite** | Morning wake-up suite (`manage_mix_scheduler` / `mplanetarians-alarm-clock/alarm.sh`): random lossless mix playback with 3-minute volume ramp, mouse motion wake detection, secondary right-monitor browser opening, 3 random Steam games for breakfast, and future mix playback scheduler (`schedule_mix_playback.py`). |
| **21**| **YouTube Video Suite** | Video production suite (`generate_youtube_video`): encode 4K UHD, 1080p Full HD, and 720p HD videos with NVENC/VideoToolbox/libx264 acceleration and source-matched audio bitrates; Screencast YouTube video generator with NVENC transitions (`generate_screencast_youtube_video.py`); vertical 1080x1920 YouTube Shorts promo video generator (`generate_youtube_short_promo.py`); looping MP4-to-MP4 video generator; and full-resolution YouTube Channel and Shorts downloader (`MP_YouTube_Channel_Downloader.sh`). |
| **22**| **Visual Media, Cover Art & Companion Video Suite** | Visual media hub (`manage_visual_media_suite`): NFT & Defasten video playlists, start/end video cutter (`Cut_Video.sh`), MP4 video splitter (`Split_Video_File.sh`), cover art converter & 1MB podcast byte targeter (`convert_cover_art.py`), procedural Netpbm P6 PPM gradient generator (`generate_ppm_cover.sh`), Electric Sheep screensaver, GeeXLab demo runner, and synchronized mix-video companion daemon (`sync_video_companion.sh`). |
| **23**| **Record Video of DJ Mix using GPU Screen Recorder (Linux)** | Direct launcher (`launch_gpu_screen_recorder`): launches hardware-accelerated GPU Screen Recorder in a new desktop window (`gpu-screen-recorder-gtk` or Flatpak) and returns cleanly to the menu. |
| **24**| **Listen to Your Top 5 Tracks Right Now (Special Option)** | Instant music discovery (`manage_top_5_tracks` / `top_5_tracks_manager.py`): unlocks and launches a curated top 5 tracks listening session. |

---

### ─── [ SECTION 3: SYSTEM, NETWORK, AI & SETTINGS ] ───────────
| # | Operation | Description & Sub-Features |
|---|---|---|
| **25**| **Live Session, Stream & Transfer Monitors Suite** | Diagnostics suite (`manage_live_monitors`): real-time CLI tracklist monitor (`SOF_Live_Tracker.sh`), Traktor Live Monitor & Audio Recorder (`traktor_monitor.py`), Audio/Video Conversion Output Monitor (`MP_Mix_Manager_Audio_File_Output_Monitor.py` / `--audio-monitor`), WAN2GP Video Output Monitor (`--wan2gp-monitor`), live file transfer inspector (`transfer-monitor`), Chrome / podcast web upload monitor (`chrome_upload_monitor.py`), and running background tasks inspector. |
| **26**| **System & Hardware Process Monitors Suite** | System telemetry (`manage_system_process_monitors`): launches `btop` with auto-applied Dreamworlds Ultra or Cosmic Supernova theme, `nvtop` for NVIDIA GPU clock and VRAM monitoring, and `top`. |
| **27**| **MP Reporter Suite & Automated Reports Management** | Comprehensive automated reporting engine (`manage_mix_reports_menu` / `mp_report_generator.py`): generates Daily, Weekly, Monthly, and Yearly intelligence reports in `REPORTS/{DAILY,WEEKLY,MONTHLY,YEARLY}` with PDF & HTML rendering, interactive 12-month calendar dashboard, **Daily AI Brain Logs reporter** (Gemini, Grok & local models), **Stephen Hawking AI Voice TTS & Infinite Talker video briefings**, and automated SMTP email distribution (`mp_email_manager.sh`). |
| **28**| **Promotional Outreach, Syndication & Music Shopping** | Marketing suite (`manage_promo_and_syndication`): send rich HTML/plaintext promo emails with artwork attachments (`send_promo_email.py`), manage publishing calendar & podcast RSS feeds (`publish_calendar_scheduler.sh`), and launch parallel music store browser tabs for Beatport, Apple Music, and Bandcamp (`shop_music.sh`). |
| **29**| **Network Services, Congen & Internet Control** | Networking suite (`manage_network_and_internet`): bulk control for SSH, Samba, and FTP; **Congen v1.1** KDE Connect mobile remote control suite with 11 menus, 18 themes, desktop shortcut manager, chime sound daemon, and multi-device deduplication (`Congen/Congen` & [Congen/README.md](Congen/README.md)); isolated LAN-only firewall toggle (`block-internet` / `unblock-internet`); and DJ Booth Mobile Web Companion server on port 8888 (`mix_web_companion.py`). |
| **30**| **Desktop Display Settings, Audio Routing & App Control** | Desktop manager (`manage_desktop_and_display`): switch between Plasma Wayland and X11 on Linux; align mix windows via KDE KWin DBus / X11 (`align_mix_windows.py`); open macOS / Windows Display and Sound Settings; and gracefully close external desktop applications (`close_allapps.sh`). |
| **31**| **Universal System Maintenance & Cleanup** | OS-tailored maintenance (`manage_system_maintenance`): Linux (`ujust clean-system`, `dnf5 clean`, systemd journal vacuum, SSD fstrim, system RAM & PageCache drop `sudo sync && drop_caches=3` with swap cycling), macOS (`brew cleanup` & `sudo purge`), Windows (`winget upgrade --all`, temp clean, TRIM), and FreeBSD (`pkg clean`/`upgrade`). |
| **32**| **Monitor System Processes and Bash Commands with System Info** | Real-time terminal diagnostic monitor (`MP_Monitor_Bash.sh`): opens a dedicated terminal tab tracking system vitals, active CPU load, RAM usage, and Bash execution history. |
| **33**| **AI Assistant & Local LLM Servers Suite** | Complete AI control center (`manage_ai_and_servers`): Antigravity CLI AI assistant sessions (Claude Sonnet/Opus, GPT-OSS, Gemini); Ollama local LLM server with 32K CUDA context (:11434); Open WebUI v0.12.2 web chat harness (:42004 / :8080); MP Harmony AI Agent with background daemon, Speech Archive, and Matrix/Hawking Voice Chat CLI `local-voice-talk` (:11435); DeepSeek Harness mobile web server & token manager (:3080); WAN2GP AI Video, **Infinite Talker**, & XTTS-v2/Edge-TTS batch suite (`wan2gp_tts_batch.py`); and Beszel server monitoring hub & agent (:8090). |
| **34**| **Dynamic MOTD Banner Manager & Drive Burner** | System utilities (`manage_motd_and_tools`): generates dynamic stylized Message Of The Day ANSI banners highlighting live running kernel (`uname -r`), recent mixes, dates, formats, and technical specs (`update_system_motd.sh`); and writes bootable ISO images directly to USB storage with safety checks (`dd` / `diskutil`). |
| **35**| **Manager Settings, Themes, Shell CLI & Reboot** | System preferences (`manage_settings_and_system`): switch between 14+ TrueColor terminal themes (including MPlanetarian Dreamworlds, Dreamworlds Ultra, Cosmic Supernova Special Edition, and Old Style Unix Terminal Retro); manage installation paths, snapshot backups, and portable config bundle export/import (`manage_installation_config.sh`); execute interactive Bash CLI commands; automated manager updater (`update_manager.sh`); and cross-platform reboot. |
| **36**| **Exit Manager** | Cleans up temporary session locks and returns cleanly to shell (`q` / `exit`). |

---

## 💻 Command Line Interface & Direct Shortcuts

MP Mix Archive Manager supports dozens of direct CLI arguments, sub-commands, and desktop shortcuts:

```bash
# General Management & Updates
mix-archive-manager --help            # Display full CLI options and flag reference
mix-archive-manager --version         # Print version and build number
mix-archive-manager update            # Check for updates and pull latest git revisions

# Audio Playback & Web Companion
mix-archive-manager p                 # Launch MP Audio Player terminal visualizer
python3 MP_Audio_Player.py -t         # View tracklist for playing mix in dedicated window
python3 MP_Audio_Player.py -e out.m3u # Export entire archive playlist as .m3u file
mix-archive-manager specs             # Inspect technical audio specifications of playing mix
mix-archive-manager top5              # Listen to Top 5 Pre-Selected Tracks
./mix_web_companion.sh                # Launch DJ Booth Mobile Web Companion on port 8888

# Audio & Video Splitting & Output Monitors
mix-archive-manager --split-flac      # Launch interactive lossless FLAC audio splitter
mix-archive-manager --split-video     # Launch interactive YouTube MP4 video splitter
mix-archive-manager --cut-video       # Precision start/end timestamp video cutter
mix-archive-manager --audio-monitor   # Launch live Audio/Video Conversion Output Monitor
mix-archive-manager --wan2gp-monitor  # Launch live WAN2GP AI Video Output Monitor

# Morning Alarm Clock
mix-archive-manager --alarm           # Launch MPlanetarians Alarm Clock menu
mix-archive-manager --alarm brief     # Display morning brief: weather, hardware & Steam games
mix-archive-manager --alarm 07:30     # Schedule morning alarm for 07:30 AM

# AI, Voice Cloning & LLM Servers
mix-archive-manager --harmony         # Manage MP Harmony AI Agent (:11435)
mix-archive-manager --harmony-voice   # Launch Matrix/Hawking Voice Chat CLI (local-voice-talk)
mix-archive-manager --open-webui      # Launch Open WebUI v0.12.2 web chat harness (:42004 / :8080)
mix-archive-manager --ollama-serve    # Start Ollama 32K CUDA server in background (:11434)
mix-archive-manager --ollama-chat     # Open interactive terminal/voice chat with local LLM
mix-archive-manager --dsh-mobile      # Launch DeepSeek Harness mobile web server (:3080)
mix-archive-manager --wan2gp-start-4.5# Launch WAN2GP AI Video & Infinite Talker server
mix-archive-manager --tts             # Launch WAN2GP XTTS-v2 & Neural TTS batch suite
mix-archive-manager --beszel-start    # Launch Beszel monitoring hub & agent (:8090)

# Remote Control & Backups
mix-archive-manager --congen          # Launch Congen v1.1 KDE Connect mobile remote generator
mix-archive-manager --backup          # Run automated multi-cloud backup to Google Drive/iCloud
```

---

## 📂 Repository & Codebase Layout

```
MP_Mix_Manager_v0.3/
├── Mix_Archive_Manager.sh       # Master zero-fork interactive console (37 operations, 1,978 lines)
├── .probe_mgr.sh                # Ultra-compact zero-fork telemetry & probe engine (264 lines)
├── manager.sh                   # Linux Bash execution wrapper
├── manager_macos.command        # macOS double-clickable Finder launcher
├── manager_freebsd.sh           # FreeBSD Bourne shell launcher
├── manager.bat                  # Windows native Command Prompt / Batch launcher
├── manager.ps1                  # Windows native PowerShell launcher
│
├── MP_Audio_Player.py           # Terminal audio player (Mini/Micro modes, Spek G, Inspector I, 31K SMB tracks)
├── MP_Audio_Player.sh           # Shell launcher for MP Audio Player
├── monitor_bluetooth_audio.py   # Real-time PipeWire/PulseAudio Bluetooth headphone auto-router
├── mix_web_companion.py         # Zero-dependency DJ Booth Mobile Web Companion server (port 8888)
├── mix_web_companion.sh         # Shell launcher for Mobile Web Companion
│
├── mp_report_generator.py       # Daily/Weekly/Monthly/Yearly intelligence & AI Brain Logs report engine
├── mp_scheduled_reporter.sh     # Automated multi-period report scheduler & Hawking TTS/Video dispatcher
├── manage_mp_reporter.sh        # Interactive MP Reporter management console
├── mp_email_manager.sh          # Automated SMTP intelligence report email delivery engine
│
├── Make_SOF_FLAC_CONVERSION.sh  # Master 32-bit FLAC conversion, multi-archive routing & split prompt
├── convert_audio_format.sh      # Universal format converter (FLAC, MP3, OGG, WAV bit depths)
├── MP_Mix_Manager_Audio_File_Output_Monitor.py # Real-time audio/video conversion output monitor
├── MOVE_NOT_CONVERTED_WAVS.sh   # Unconverted WAV retrieval and quarantine engine
├── search_and_import_mixes.py   # Universal mix search & importer across local disks and SMB shares
├── search_and_import_mixes.sh   # Shell launcher for mix search & import
├── find_duplicate_mixes.py      # Deterministic O(1) partial-hash + SHA-256 audio deduplicator
├── remove_duplicate_images.py   # Byte-for-byte duplicate image cleaner
│
├── master_audio_loudness.py     # EBU R128 loudness analyzer & 2-pass transparent normalizer
├── master_audio_loudness.sh     # Shell launcher for loudness mastering
├── verify_audio_mastering.py    # Mastering quality audit: True Peak ISP, mono phase, silence
├── verify_audio_mastering.sh    # Shell launcher for mastering audit
├── verify_lossless_spectral.py  # Multi-segment FFT spectral cutoff inspector (detects fake FLACs)
├── verify_lossless_spectral.sh  # Shell launcher for spectral analysis
├── scrub_mix_archive.sh         # Automated background bit-rot scrubber with systemd timer
├── manage_checksums.sh          # SHA-256 audio integrity manifest generator & validator
├── Verify_FLAC_Files.sh         # Multi-threaded FLAC bitstream corruption scanner
├── tag_audio_metadata.py        # Lossless ReplayGain (EBU R128) & front cover art tagger
├── tag_audio_metadata.sh        # Shell launcher for metadata tagging
│
├── generate_cue_sheet.py        # Red Book standard CUE sheet generator & track splitter
├── Check_Find_Tracklists.sh     # Traktor Pro history XML parser & tracklist generator
├── generate_master_tracklist.py # Searchable Master Tracklist HTML index generator
├── Generate_Master_Tracklist.sh # Shell launcher for master tracklist index
├── generate_tracklist_docs.py   # Styled HTML & printable vector PDF tracklist exporter
├── export_chapters.py           # YouTube & SoundCloud chapter / timestamp exporter
├── export_chapters.sh           # Shell launcher for chapter exporter
├── identify_mix_tracks.py       # AcoustID / Chromaprint audio fingerprint track recognizer
├── identify_mix_tracks.sh       # Shell launcher for audio fingerprinting
├── export_rekordbox_playlist.py # Traktor/CUE/M3U to Pioneer Rekordbox XML playlist exporter
├── export_rekordbox_playlist.sh # Shell launcher for Rekordbox exporter
├── generate_traktor_playlist_from_history.py # Traktor history harmonic key sorter (1A-12B macOS)
├── generate_traktor_playlist_from_history.sh # Shell launcher for Traktor harmonic playlist generator
│
├── manage_playlists.py          # Custom playlist suite (.m3u8 / .xspf creator & dispatcher)
├── manage_playlists.sh          # Shell launcher for custom playlists
├── generate_archive_folder_playlists.py # Folder playlist generator (PLAYLISTS_GENERATED)
├── generate_archive_folder_playlists.sh # Shell launcher for folder playlist generator
├── merge_playlist_flac.sh       # Concat M3U playlist tracks to single FLAC master
├── top_5_tracks_manager.py      # Top 5 Pre-Selected Tracks listening manager
├── manage_top_5_tracks.sh       # Shell launcher for Top 5 tracks manager
│
├── generate_spek.sh             # Acoustic spectrogram suite (Spek, SoX, Praat, Sonic Visualiser)
├── generate_youtube_video.sh    # Hardware-accelerated 4K/1080p/720p YouTube video creator
├── generate_screencast_youtube_video.py # Screencast 1080p NVENC YouTube video & transition generator
├── generate_youtube_short_promo.py # Vertical 1080x1920 YouTube Shorts promo synthesizer
├── generate_youtube_short_promo.sh # Shell launcher for YouTube Shorts promo generator
├── MP_YouTube_Channel_Downloader.sh # Full 1080p YouTube video & dedicated Shorts channel downloader
├── Make_SOF_Episode_From_PNG_FLAC_Output_MP4_4K_Video.sh # 4K NVENC YouTube video creator
├── Make_SOF_Episode_From_PNG_FLAC_Output_MP4_1080p_Video.sh # 1080p Full HD video creator
├── Make_SOF_Episode_From_PNG_FLAC_Output_MP4_720p_Video.sh # 720p HD video creator
├── Make_SOF_Episode_From_MP4_Audio_Output_MP4_1080p_Video.sh # Looping MP4 video creator
├── Cut_Video.sh                 # Precision start/end timestamp video cutter
├── Split_Video_File.sh          # Precision YouTube MP4 video splitter
├── Split_FLAC_File.sh           # Sample-accurate lossless FLAC audio splitter
├── split_audio_file.sh          # Symlink to Split_FLAC_File.sh
│
├── convert_cover_art.py         # Artwork format converter & <=1MB podcast byte targeter
├── generate_ppm_cover.py        # Procedural Netpbm P6 binary PPM gradient cover art generator
├── generate_ppm_cover.sh        # Shell launcher for PPM cover art generator
├── sync_video_companion.py      # Synchronized mix-video companion playback daemon
├── sync_video_companion.sh      # Shell launcher for video companion daemon
├── align_mix_windows.py         # KDE KWin DBus & X11 desktop window geometry aligner
│
├── inspect_audio_studio.py      # Studio hardware (PipeWire/ALSA/MIDI) & DAW diagnostic inspector
├── inspect_audio_studio.sh      # Shell launcher for studio inspector
├── inspect_playing_audio.py     # Technical audio stream specifications & codec inspector
├── inspect_playing_audio.sh     # Shell launcher for audio specification inspector
├── get_audio_interface.py       # Active default audio output device & buffer latency calculator
├── view_tracklist_console.sh    # Borderless console tracklist viewer
├── traktor_monitor.py           # Cross-platform Traktor live monitor & audio recording controller
├── traktor_monitor.sh           # Shell launcher for Traktor monitor
├── SOF_Live_Tracker.sh          # Live tracklist monitor (connecting to Strawberry & cliamp)
├── SOF_Archive_Stats.sh         # Archive duration accumulator & statistics scanner
├── MP_Monitor_Bash.sh           # Real-time system vitals & Bash command monitor
│
├── publish_calendar_scheduler.py# Mix publishing calendar & syndication schedule engine
├── publish_calendar_scheduler.sh# Shell launcher for publishing calendar
├── send_promo_email.py          # Promotional & publisher outreach email system
├── send_notification.sh         # Unified notification dispatcher (Desktop, Discord, Telegram, Pushover)
├── shop_music.sh                # Parallel music store quick-launcher (Beatport, Apple, Bandcamp)
│
├── manage_harmony_agent.sh      # MP Harmony AI Agent manager, Speech Archive & Voice Chat CLI (:11435)
├── manage_ollama.sh             # Ollama 32K CUDA server, models manager & Matrix voice chat (:11434)
├── dsh_mobile.sh                # DeepSeek Harness mobile web server & token manager (:3080)
├── wan2gp.sh                    # WAN2GP AI Video & Infinite Talker server runner (Profiles 2 & 4.5)
├── wan2gp_tts_batch.py          # XTTS-v2 & Edge-TTS batch voice cloner & player (.txt -> .wav)
├── wan2gp_flux_batch.py         # Flux Klein 9B AI video batch generator
├── wan2gp_ltx_batch.py          # LTX Video 2B/13B AI video batch generator
├── clear-wan2gp-logs.sh         # WAN2GP AI generation log cleaner
├── beszel.sh                    # Beszel server monitoring hub & hardware agent runner (:8090)
│
├── Get_All_Drive_Space.sh       # Comprehensive drive space analyzer (mounted & unmounted)
├── switch-to-plasma-wayland.sh  # Desktop session switcher to Plasma Wayland
├── switch-to-plasma-x11.sh      # Desktop session switcher to Plasma X11
├── close_allapps.sh             # Graceful desktop application closer (protects manager)
├── manage_motd.py               # Dynamic System MOTD generator (live kernel, mixes & technical specs)
├── update_system_motd.sh        # Shell launcher for dynamic system MOTD
├── manage_installation_config.sh# Migration wizard & configuration backup/export/import suite
├── update_manager.sh            # System updater & version checker (`mix-archive-manager update`)
├── install.sh                   # Cross-platform automated environment installer
│
├── bin/                         # Compiled binaries & CLI helpers (symlinked to ~/.local/bin)
│   ├── cliamp                   # Custom retro terminal music player (v2.0.1)
│   ├── mix-archive-manager      # Desktop / background launch wrapper
│   ├── launch-manager           # Terminal wrapper
│   ├── launch-manager-fullscreen# Dedicated full-screen terminal wrapper
│   ├── traktor-monitor          # Traktor Pro Live Monitor CLI
│   ├── view-mix-specs           # Audio specification & stream properties inspector CLI
│   ├── view-tracklist           # Borderless console tracklist viewer
│   ├── split-flac               # Lossless FLAC audio splitter CLI
│   ├── split-video              # YouTube MP4 video splitter CLI
│   ├── cut-video                # Precision video cutter CLI
│   ├── alarm                    # MPlanetarians Alarm Clock CLI
│   ├── beszel                   # Beszel monitoring hub & agent controller CLI
│   ├── manage-ollama            # Ollama server controller CLI
│   ├── dsh-mobile               # DeepSeek Harness mobile web server CLI
│   ├── congen                   # Congen v1.1 KDE Connect remote control CLI
│   ├── transfer-monitor         # Live file write & transfer inspector
│   ├── chrome-upload-monitor    # Real-time web upload monitor
│   ├── list-midi-devices        # USB MIDI hardware inspector
│   ├── block-internet           # Isolated LAN-only firewall toggle
│   └── unblock-internet         # Firewall restore toggle
│
├── scripts/                     # Synchronized canonical script repository
├── tests/
│   └── run_tests.sh             # Automated verification test suite (243+ tests)
├── themes/                      # Terminal & BTOP color palettes (Dreamworlds, Cosmic Supernova...)
├── mplanetarians-alarm-clock/   # Standalone morning alarm clock package
├── Congen/                      # Congen v1.1 - KDE Connect commands generator & 18-theme workstation bridge
├── assets/                      # Artwork templates, promo contact book, publishing calendars
├── config.env                   # Active user configuration overrides
├── config.env.example           # Configuration template
├── VERSION                      # Semantic version file (0.3.6 Beta)
├── README.md                    # System documentation & feature matrix
└── CHANGELOG.md                 # Complete release history and audit log
```

---

## ⚙️ Configuration Guide (`config.env`)

MP Mix Archive Manager automatically reads `config.env` from the project directory or `~/.config/mix-manager/config.env`. Copy `config.env.example` to `config.env` to customize settings:

```bash
# Target storage path for music and mix archives
# Auto-detected across platforms:
#   Linux:   /run/media/$USER/WD BLACK B/MIX_ARCHIVE
#   macOS:   /Volumes/WD BLACK B/MIX_ARCHIVE
#   Windows: D:/MIX_ARCHIVE
MIX_ARCHIVE_CONFIGURED="true"
MIX_ARCHIVE_DIR="/run/media/$USER/WD BLACK B/MIX_ARCHIVE"

# Additional / Multiple Mix Archive Storage Locations (semicolon, comma, or newline separated; semicolon recommended for Windows drive paths)
EXTRA_MIX_ARCHIVE_DIRS="/run/media/$USER/DATA/MIX_ARCHIVE2"
# Windows example: EXTRA_MIX_ARCHIVE_DIRS="G:\My Drive\MIX_ARCHIVE;D:\Mixes\FLAC_CONVERTED_OUTPUTS"

# Output directories (relative to MIX_ARCHIVE_DIR or absolute)
OUTPUT_DIR="FLAC_CONVERTED_OUTPUTS"
ARCHIVE_DIR="CONVERTED_WAV_FILES"
SPEK_DIR="SPEK_OUTPUTS"

# Traktor History folder containing session collection.nml files
TRAKTOR_HISTORY_DIR="/run/media/$USER/WD BLACK B/MIX_ARCHIVE/Traktor 3.11.1/History"

# Cloud & Remote Backup Endpoints
GDRIVE_REMOTE="gdrive:MIX_ARCHIVE/FLAC_CONVERTED_OUTPUTS"
ICLOUD_PATH="${HOME}/Library/Mobile Documents/com~apple~CloudDocs/MIX_ARCHIVE"
DROPBOX_PATH="${HOME}/Dropbox/MIX_ARCHIVE"

# Default Audio Player for playback and startup autoplay
# Options: mp_audio_player, cliamp, strawberry, vlc, haruna, kodi, audacious
DEFAULT_AUDIO_PLAYER="mp_audio_player"
AUTO_PLAY_ON_STARTUP="true"
AUTO_SHOW_TRACKLIST_ON_STARTUP="true"
TRACKLIST_VIEWER="console"

# Promotional Outreach & SMTP Settings
PROMO_SENDER_NAME="MPlanetarian"
PROMO_SENDER_EMAIL="artist@example.com"
SMTP_HOST="smtp.gmail.com"
SMTP_PORT="587"
SMTP_USER="artist@example.com"
SMTP_USE_TLS="true"

# Weather & Planetary Ephemeris (Banner Display)
WEATHER_ENABLED="true"
WEATHER_LOCATION="Swansea, UK"
PLANETS_ENABLED="true"
```

---

## 🧪 Automated Test Suite & Quality Assurance

MP Mix Archive Manager includes an automated test harness ensuring shell script validity, Python syntax compilation, configuration integrity, and root/scripts directory synchronization:

```bash
# Run the complete test suite
./tests/run_tests.sh
```

**Verification Coverage (243+ Automated Checks):**
- ✅ Shell Script Syntax (`bash -n` on all `.sh` executables).
- ✅ Python Compilation (`py_compile` on all `.py` modules).
- ✅ Configuration Defaults (`config.env` key validation).
- ✅ Codebase Synchronization (`cmp` verification between root and `scripts/`).
- ✅ Executable Permissions Check (`chmod +x` enforcement).

---

## 📜 License

MP Mix Archive Manager is licensed under the **[MIT License](LICENSE)**.

---
*Created with ❤️ by **MPlanetarian** for audio producers, DJs, and media creators worldwide.*

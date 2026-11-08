#!/usr/bin/env python3

import os
import shutil
import subprocess
from math import ceil

def run_cmd(cmd, desc):
    print(f"[Running] {desc}", flush=True)
    subprocess.run(cmd, check=True)

def get_duration(file):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file]
    return float(subprocess.check_output(cmd).decode().strip())

def main():
    TEMP_DIR = "/tmp/yt_video_render"
    INPUT_DIR = "/path/to/input"
    OUTPUT_FILE = "/path/to/output/final_video.mp4"
    VIDEO_FILE = os.path.join(INPUT_DIR, "input_video.mp4")
    AUDIO_FILE = os.path.join(INPUT_DIR, "looped_audio.wav")
    INTRO_IMAGE_NAME = "Sensorium_Interface.png"
    OUTRO_IMAGE_NAME = "Cover_v3.png"
    CYCLE_IMAGES = ["artwork1.png", "artwork2.png", "artwork3.png"]
    IMAGE_DUR = 5.0
    INTERVAL_SEC = 300.0
    FADE_DUR = 1.0
    FPS = 24.0

    os.makedirs(TEMP_DIR, exist_ok=True)
    scaled_images = {img: os.path.join(TEMP_DIR, f"{img}_scaled.png") for img in [INTRO_IMAGE_NAME, OUTRO_IMAGE_NAME] + CYCLE_IMAGES}

    for img in scaled_images:
        run_cmd(["ffmpeg", "-y", "-i", os.path.join(INPUT_DIR, img), "-vf", "scale=1728:1080", scaled_images[img]], f"Scaling {img}")

    video_dur = get_duration(VIDEO_FILE)
    segments_dir = os.path.join(TEMP_DIR, "segments")
    os.makedirs(segments_dir, exist_ok=True)

    enc_args = [
        "-c:v", "h264_nvenc",
        "-preset", "p3",
        "-cq", "20",
        "-g", "60",
        "-pix_fmt", "yuv420p",
        "-video_track_timescale", "90000"
    ]

    concat_entries = []

    # Intro segment
    intro_seg = os.path.join(segments_dir, "seg_00_intro.mp4")
    if not os.path.exists(intro_seg):
        run_cmd([
            "ffmpeg", "-y",
            "-loop", "1", "-i", scaled_images[INTRO_IMAGE_NAME], "-t", f"{IMAGE_DUR:.6f}",
            "-vf", f"fps={FPS},setsar=1,fade=t=in:st=0:d=5:color=black,fade=t=out:st={IMAGE_DUR-FADE_DUR:.6f}:d={FADE_DUR:.6f}:color=black,format=yuv420p",
            *enc_args,
            intro_seg
        ], "Rendering Intro card")
    concat_entries.append(intro_seg)

    # Body segments
    curr_pos = 0.0
    seg_idx = 0

    while curr_pos < video_dur:
        chunk_dur = min(INTERVAL_SEC, video_dur - curr_pos)
        is_first = (curr_pos == 0.0)
        is_last = (curr_pos + chunk_dur >= video_dur)

        fade_in = min(FADE_DUR, chunk_dur / 2.0)
        fade_out = min(FADE_DUR, chunk_dur / 2.0)

        filters = [
            f"fps={FPS}",
            "scale=1728:1080",
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black",
            "setsar=1",
            f"fade=t=in:st=0:d={fade_in:.6f}:color=black",
            f"fade=t=out:st={max(0.0, chunk_dur - fade_out):.6f}:d={fade_out:.6f}:color=black",
            "format=yuv420p"
        ]
        vf_str = ",".join(filters)

        body_seg = os.path.join(segments_dir, f"seg_body_{seg_idx:02d}.mp4")
        if not os.path.exists(body_seg):
            run_cmd([
                "ffmpeg", "-y",
                "-ss", f"{curr_pos:.6f}", "-i", VIDEO_FILE, "-t", f"{chunk_dur:.6f}",
                "-vf", vf_str,
                *enc_args,
                body_seg
            ], f"Rendering Screencast Chunk {seg_idx+1}")
        concat_entries.append(body_seg)

        curr_pos += chunk_dur

        if curr_pos < video_dur:
            img_name = CYCLE_IMAGES[seg_idx % len(CYCLE_IMAGES)]
            art_seg = os.path.join(segments_dir, f"seg_art_{seg_idx:02d}.mp4")
            if not os.path.exists(art_seg):
                run_cmd([
                    "ffmpeg", "-y",
                    "-loop", "1", "-i", scaled_images[img_name], "-t", f"{IMAGE_DUR:.6f}",
                    "-vf", f"fps={FPS},setsar=1,fade=t=in:st=0:d={FADE_DUR:.6f}:color=black,fade=t=out:st={IMAGE_DUR-FADE_DUR:.6f}:d={FADE_DUR:.6f}:color=black,format=yuv420p",
                    *enc_args,
                    art_seg
                ], f"Rendering Art Card {seg_idx+1}")
            concat_entries.append(art_seg)

        seg_idx += 1

    # Outro segment
    outro_seg = os.path.join(segments_dir, "seg_outro.mp4")
    if not os.path.exists(outro_seg):
        run_cmd([
            "ffmpeg", "-y",
            "-loop", "1", "-i", scaled_images[OUTRO_IMAGE_NAME], "-t", f"{IMAGE_DUR:.6f}",
            "-vf", f"fps={FPS},setsar=1,fade=t=in:st=0:d={FADE_DUR:.6f}:color=black,fade=t=out:st=0:d=5:color=black,format=yuv420p",
            *enc_args,
            outro_seg
        ], "Rendering Outro card")
    concat_entries.append(outro_seg)

    # Concatenate segments
    concat_list_file = os.path.join(TEMP_DIR, "concat_list.txt")
    with open(concat_list_file, "w") as f:
        for seg in concat_entries:
            f.write(f"file '{seg}'\n")

    concat_video_file = os.path.join(TEMP_DIR, "video_stitched.mp4")
    run_cmd([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_list_file,
        "-c", "copy",
        "-video_track_timescale", "90000",
        concat_video_file
    ], "Stitching video segments")

    total_video_dur = get_duration(concat_video_file)
    print(f"Stitched Video Duration: {total_video_dur:.2f}s ({total_video_dur/60:.2f} mins)", flush=True)

    # Mux with audio
    audio_fade_out_start = max(0.0, total_video_dur - 5.0)
    run_cmd([
        "ffmpeg", "-y",
        "-i", concat_video_file,
        "-stream_loop", "-1", "-i", AUDIO_FILE,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-video_track_timescale", "90000",
        "-af", f"afade=t=in:st=0:d=5,afade=t=out:st={audio_fade_out_start:.6f}:d=5",
        "-c:a", "aac",
        "-b:a", "320k",
        "-t", f"{total_video_dur:.6f}",
        "-movflags", "+faststart",
        OUTPUT_FILE
    ], "Muxing final video with audio")

    # Verify final file
    final_dur = get_duration(OUTPUT_FILE)
    size_bytes = os.path.getsize(OUTPUT_FILE)
    size_mb = size_bytes / (1024 * 1024)

    print("\n" + "=" * 70, flush=True)
    print("SUCCESS: Final YouTube Video Created Successfully!", flush=True)
    print(f"File Path: {OUTPUT_FILE}", flush=True)
    print(f"Total Duration: {final_dur:.2f}s ({final_dur/60:.2f} mins)", flush=True)
    print(f"File Size: {size_mb:.2f} MB ({size_mb/1024:.2f} GB)", flush=True)
    print("=" * 70, flush=True)

    # Clean up
    print("\nCleaning up temporary files...", flush=True)
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    print("Cleanup complete.", flush=True)

if __name__ == "__main__":
    main()
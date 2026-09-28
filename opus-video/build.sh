#!/usr/bin/env bash
# Full pipeline: timeline -> frames -> sound -> final MP4.
# Requirements: node + playwright (Chromium), python3 + numpy/scipy, ffmpeg with libx264.
set -euo pipefail
cd "$(dirname "$0")"
FFMPEG="${FFMPEG:-$(command -v ffmpeg || python3 -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')}"

node timeline.mjs
node render.mjs --workers "${WORKERS:-4}"
python3 audio.py

# two-pass at ~17.5 Mb/s: keeps the film grain intact while staying under 100 MB
V=(-vf "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p"
   -c:v libx264 -preset slow -b:v 17500k -maxrate 30M -bufsize 35M -profile:v high -level 4.2
   -x264-params "keyint=120:min-keyint=60"
   -colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv)
(cd build &&
  "$FFMPEG" -y -hide_banner -loglevel error -framerate 60 -i ../frames/f_%05d.png "${V[@]}" -pass 1 -an -t 35 -f mp4 /dev/null &&
  "$FFMPEG" -y -hide_banner -loglevel error -framerate 60 -i ../frames/f_%05d.png -i sound.wav -map 0:v -map 1:a \
    "${V[@]}" -pass 2 -c:a aac -b:a 320k -ar 48000 -t 35 -movflags +faststart ../opus-5.5.mp4)
echo "done -> opus-5.5.mp4"

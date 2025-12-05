#!/bin/bash
set -e

echo "Starting Popcorn..."

# Add /data/ffmpeg/bin to PATH if it exists (for on-demand FFmpeg installations)
if [ -d "/data/ffmpeg/bin" ]; then
    export PATH="/data/ffmpeg/bin:$PATH"
    echo "Added /data/ffmpeg/bin to PATH"
fi

# Check if FFmpeg is available (system, /data/ffmpeg/bin, or mapped from host)
if command -v ffmpeg &> /dev/null; then
    FFMPEG_LOCATION=$(which ffmpeg)
    echo "FFmpeg detected at: $FFMPEG_LOCATION"
    echo "Version: $(ffmpeg -version | head -n 1)"
else
    echo "FFmpeg not detected. Live TV features will be unavailable."
    echo "You can install FFmpeg via the Settings page (Admin → Live TV → Install FFmpeg button)"
fi

# Execute the main application
exec "$@"

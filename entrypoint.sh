#!/bin/bash
set -e

echo "Starting Popcorn..."

# Normalize INSTALL_FFMPEG to lowercase for case-insensitive comparison
INSTALL_FFMPEG_LOWER=$(echo "$INSTALL_FFMPEG" | tr '[:upper:]' '[:lower:]')

# Check if INSTALL_FFMPEG environment variable is set to a truthy value
if [ "$INSTALL_FFMPEG_LOWER" = "true" ] || [ "$INSTALL_FFMPEG_LOWER" = "yes" ] || [ "$INSTALL_FFMPEG" = "1" ]; then
    echo "INSTALL_FFMPEG is enabled. Checking for FFmpeg..."
    
    if ! command -v ffmpeg &> /dev/null; then
        echo "FFmpeg not found. Installing FFmpeg..."
        apt-get update -qq
        apt-get install -y -qq ffmpeg
        echo "FFmpeg installed successfully."
    else
        echo "FFmpeg is already installed."
    fi
else
    echo "INSTALL_FFMPEG not enabled. Skipping FFmpeg installation."
    echo "To enable Live TV streaming, set INSTALL_FFMPEG=true or map FFmpeg from host."
fi

# Check if FFmpeg is available (either installed or mapped from host)
if command -v ffmpeg &> /dev/null; then
    echo "FFmpeg detected: $(ffmpeg -version | head -n 1)"
else
    echo "FFmpeg not detected. Live TV features will be unavailable."
fi

# Execute the main application
exec "$@"

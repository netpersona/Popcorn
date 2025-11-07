"""
Utility functions for Popcorn
"""
import shutil
import logging

logger = logging.getLogger(__name__)


def check_ffmpeg_available():
    """
    Check if FFmpeg is available on the system.
    
    Returns:
        tuple: (is_available: bool, message: str)
    """
    ffmpeg_path = shutil.which('ffmpeg')
    
    if ffmpeg_path:
        logger.info(f"FFmpeg found at: {ffmpeg_path}")
        return True, f"FFmpeg detected at {ffmpeg_path}"
    else:
        logger.warning("FFmpeg not found on system")
        return False, "FFmpeg not installed"


def get_ffmpeg_install_instructions():
    """
    Get installation instructions for FFmpeg based on deployment type.
    
    Returns:
        dict: Installation instructions for different scenarios
    """
    return {
        'docker_env': {
            'title': 'Auto-install in Docker',
            'description': 'Add environment variable to your Docker container',
            'steps': [
                'Add to docker-compose.yml:',
                '  environment:',
                '    - INSTALL_FFMPEG=true',
                'Or add to docker run command:',
                '  -e INSTALL_FFMPEG=true'
            ]
        },
        'docker_map': {
            'title': 'Map from Unraid/Host',
            'description': 'Use FFmpeg already installed on your host system',
            'steps': [
                'Add to docker-compose.yml:',
                '  volumes:',
                '    - /usr/bin/ffmpeg:/usr/bin/ffmpeg:ro',
                'Or add to docker run command:',
                '  -v /usr/bin/ffmpeg:/usr/bin/ffmpeg:ro'
            ]
        },
        'manual': {
            'title': 'Manual Installation',
            'description': 'Install FFmpeg on your system',
            'steps': [
                'Ubuntu/Debian: sudo apt-get install ffmpeg',
                'CentOS/RHEL: sudo yum install ffmpeg',
                'macOS: brew install ffmpeg',
                'Windows: Download from ffmpeg.org'
            ]
        }
    }

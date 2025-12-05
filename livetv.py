import logging
from flask import request
from models import get_session, Settings, Schedule, Movie
from channel_numbers import get_channel_number
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


def get_server_info():
    """Get server information for HDHomeRun emulation"""
    # Get the base URL from request to preserve scheme (http/https) and port
    base_url = request.url_root.rstrip('/')
    host = request.host
    
    return {
        'base_url': base_url,
        'host': host
    }


def is_live_tv_enabled():
    """Check if Live TV integration is enabled in settings"""
    try:
        db_session = get_session()
        settings = db_session.query(Settings).first()
        if settings and settings.live_tv_enabled == True:
            return True
        return False
    except Exception as e:
        logger.error(f"Error checking Live TV status: {e}")
        return False


def get_discover_data():
    """
    Returns HDHomeRun device discovery information.
    This endpoint allows Plex to auto-detect Popcorn as a network tuner.
    """
    server_info = get_server_info()
    
    return {
        "FriendlyName": "Popcorn TV",
        "Manufacturer": "Popcorn",
        "ModelNumber": "HDHR-Popcorn",
        "FirmwareName": "hdhomerun_popcorn",
        "TunerCount": 10,
        "FirmwareVersion": "1.0.0",
        "DeviceID": "POPCORN01",
        "DeviceAuth": "popcorn",
        "BaseURL": server_info['base_url'],
        "LineupURL": f"{server_info['base_url']}/lineup.json"
    }


def get_lineup_status():
    """
    Returns the lineup scan status.
    Plex checks this to see if the channel scan is complete.
    """
    return {
        "ScanInProgress": 0,
        "ScanPossible": 1,
        "Source": "Cable",
        "SourceList": ["Cable"]
    }


def get_lineup(scheduler):
    """
    Returns the channel lineup in HDHomeRun format.
    This is what Plex uses to display available channels.
    
    Args:
        scheduler: ScheduleGenerator instance to get channel list
    """
    server_info = get_server_info()
    lineup = []
    
    # Get all available channels from scheduler
    channels = scheduler.get_all_channels()
    
    # Use existing channel number mapping
    for channel_name in channels:
        channel_num = get_channel_number(channel_name)
        lineup.append({
            "GuideNumber": str(channel_num),
            "GuideName": channel_name,
            "URL": f"{server_info['base_url']}/livetv/stream/{channel_num}"
        })
    
    logger.info(f"Generated lineup with {len(lineup)} channels")
    return lineup


def generate_m3u_playlist(scheduler):
    """
    Generate M3U playlist for IPTV clients.
    This is an alternative to the lineup.json format.
    
    Args:
        scheduler: ScheduleGenerator instance to get channel list
        
    Returns:
        str: M3U formatted playlist content
    """
    server_info = get_server_info()
    channels = scheduler.get_all_channels()
    
    # Start M3U playlist
    m3u_content = "#EXTM3U\n"
    
    # Add each channel using existing channel number mapping
    for channel_name in channels:
        channel_num = get_channel_number(channel_name)
        # EXTINF format: duration (always -1 for live TV), tvg attributes, channel name
        m3u_content += f'#EXTINF:-1 tvg-id="{channel_num}" tvg-name="{channel_name}" tvg-chno="{channel_num}",{channel_name}\n'
        m3u_content += f'{server_info["base_url"]}/livetv/stream/{channel_num}\n'
    
    logger.info(f"Generated M3U playlist with {len(channels)} channels")
    return m3u_content


def generate_xmltv_epg(scheduler):
    """
    Generate XMLTV format EPG (Electronic Program Guide) data.
    This provides Plex with program schedule information.
    
    Args:
        scheduler: ScheduleGenerator instance to get schedule data
        
    Returns:
        str: XMLTV formatted XML content
    """
    # Create root element
    tv = ET.Element('tv')
    tv.set('generator-info-name', 'Popcorn')
    tv.set('generator-info-url', 'https://github.com/netpersona/Popcorn')
    
    # Get all channels
    channels = scheduler.get_all_channels()
    
    # Add channel definitions
    for channel_name in channels:
        channel_num = get_channel_number(channel_name)
        channel_elem = ET.SubElement(tv, 'channel')
        channel_elem.set('id', str(channel_num))
        
        display_name = ET.SubElement(channel_elem, 'display-name')
        display_name.text = channel_name
        
        # Add channel number as alternate display name
        display_number = ET.SubElement(channel_elem, 'display-name')
        display_number.text = str(channel_num)
    
    # Get schedule data for the next 7 days
    db_session = get_session()
    # Use timezone-aware UTC datetime
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # For each day in the next week
    for day_offset in range(7):
        current_date = today + timedelta(days=day_offset)
        day_of_week = current_date.weekday()  # 0 = Monday, 6 = Sunday
        
        # Get schedules for this day of week
        schedules = db_session.query(Schedule).filter_by(day=day_of_week).all()
        
        for schedule in schedules:
            channel_num = get_channel_number(schedule.channel)
            
            # Parse start and end times (format: "HH:MM")
            start_hour, start_min = map(int, schedule.start_time.split(':'))
            end_hour, end_min = map(int, schedule.end_time.split(':'))
            
            # Handle times >= 24 (representing next day)
            start_day_offset = 0
            end_day_offset = 0
            
            if start_hour >= 24:
                start_day_offset = start_hour // 24
                start_hour = start_hour % 24
            
            if end_hour >= 24:
                end_day_offset = end_hour // 24
                end_hour = end_hour % 24
            
            # Create timezone-aware datetime objects for this specific day
            # Use timedelta to add time components to maintain timezone
            start_dt = current_date + timedelta(
                days=start_day_offset,
                hours=start_hour,
                minutes=start_min
            )
            end_dt = current_date + timedelta(
                days=end_day_offset,
                hours=end_hour,
                minutes=end_min
            )
            
            # Handle programs that cross midnight (if end is still before start after adjustments)
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)
            
            # Get movie details
            movie = schedule.movie
            if not movie:
                continue
            
            # Create programme element
            programme = ET.SubElement(tv, 'programme')
            # Use XMLTV format: YYYYMMDDHHmmss +HHMM (space before timezone required by Plex)
            # Format: 20241106221000 +0000
            programme.set('start', start_dt.strftime('%Y%m%d%H%M%S +0000'))
            programme.set('stop', end_dt.strftime('%Y%m%d%H%M%S +0000'))
            programme.set('channel', str(channel_num))
            
            # Add movie title
            title = ET.SubElement(programme, 'title')
            title.set('lang', 'en')
            title.text = movie.title
            
            # Add description if available
            if movie.summary:
                desc = ET.SubElement(programme, 'desc')
                desc.set('lang', 'en')
                desc.text = movie.summary
            
            # Add category (genre)
            category = ET.SubElement(programme, 'category')
            category.set('lang', 'en')
            category.text = movie.genre
            
            # Add year if available
            if movie.year:
                date_elem = ET.SubElement(programme, 'date')
                date_elem.text = str(movie.year)
            
            # Add rating if available
            if movie.rating:
                rating = ET.SubElement(programme, 'rating')
                value = ET.SubElement(rating, 'value')
                value.text = movie.rating
            
            # Add content rating if available
            if movie.content_rating:
                rating = ET.SubElement(programme, 'rating')
                rating.set('system', 'MPAA')
                value = ET.SubElement(rating, 'value')
                value.text = movie.content_rating
            
            # Add poster as icon if available
            if movie.poster_url:
                icon = ET.SubElement(programme, 'icon')
                icon.set('src', movie.poster_url)
            
            # Add length (duration in minutes)
            if movie.duration:
                length = ET.SubElement(programme, 'length')
                length.set('units', 'minutes')
                length.text = str(movie.duration)
    
    # Convert to string with proper XML declaration
    xml_str = ET.tostring(tv, encoding='unicode', method='xml')
    xmltv_content = f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}'
    
    # Count total programmes generated
    programme_count = len(tv.findall('programme'))
    logger.info(f"Generated XMLTV EPG with {len(channels)} channels and {programme_count} programmes for 7 days")
    
    # Log first programme as sample for debugging
    first_programme = tv.find('programme')
    if first_programme is not None:
        logger.debug(f"Sample programme: channel={first_programme.get('channel')}, "
                    f"start={first_programme.get('start')}, stop={first_programme.get('stop')}, "
                    f"title={first_programme.find('title').text if first_programme.find('title') is not None else 'N/A'}")
    
    return xmltv_content


def get_current_program(channel_num):
    """
    Determine what movie should be playing on a channel right now.
    
    Args:
        channel_num: The channel number
        
    Returns:
        tuple: (movie, offset_seconds) or (None, 0) if nothing is scheduled
    """
    from channel_numbers import CHANNEL_NUMBERS
    
    # Find channel name from number
    channel_name = None
    for name, num in CHANNEL_NUMBERS.items():
        if num == channel_num:
            channel_name = name
            break
    
    if not channel_name:
        logger.warning(f"No channel found for number {channel_num}")
        return None, 0
    
    # Get current time in UTC
    now = datetime.now(timezone.utc)
    current_time = now.time()
    day_of_week = now.weekday()
    
    # Get schedules for this channel and day
    db_session = get_session()
    schedules = db_session.query(Schedule).filter_by(
        channel=channel_name,
        day=day_of_week
    ).all()
    
    if not schedules:
        logger.warning(f"No schedules found for channel {channel_name} on day {day_of_week}")
        return None, 0
    
    # Find the current program
    for schedule in schedules:
        start_hour, start_min = map(int, schedule.start_time.split(':'))
        end_hour, end_min = map(int, schedule.end_time.split(':'))
        
        start_time = now.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
        end_time = now.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)
        
        # Handle programs that cross midnight
        if end_time <= start_time:
            end_time += timedelta(days=1)
        
        # Check if current time is within this program's time slot
        if start_time <= now < end_time:
            # Calculate offset in seconds from the start
            offset = (now - start_time).total_seconds()
            
            logger.info(f"Channel {channel_num} ({channel_name}): Playing {schedule.movie.title} at offset {offset}s")
            return schedule.movie, int(offset)
    
    logger.warning(f"No current program found for channel {channel_num} ({channel_name})")
    return None, 0


def stream_channel(channel_num, plex_api):
    """
    Stream a channel using FFmpeg to transcode to MPEG-TS format.
    This is a generator function that yields chunks of video data.
    
    Args:
        channel_num: The channel number to stream
        plex_api: PlexAPI instance to get stream URLs
        
    Yields:
        bytes: Chunks of MPEG-TS video data
    """
    import subprocess
    import shutil
    
    # Check if FFmpeg is available
    if not shutil.which('ffmpeg'):
        logger.error("FFmpeg not found on system!")
        raise RuntimeError("FFmpeg is required for Live TV streaming")
    
    # Get the current program
    movie, offset_seconds = get_current_program(channel_num)
    
    if not movie:
        logger.error(f"No program currently scheduled for channel {channel_num}")
        raise ValueError(f"No program scheduled for channel {channel_num}")
    
    # Get the Plex stream URL for the movie
    try:
        # Use Plex's direct play URL
        plex_movie = plex_api.plex.fetchItem(int(movie.plex_id))
        stream_url = plex_movie.getStreamURL()
        
        logger.info(f"Streaming {movie.title} from Plex at offset {offset_seconds}s")
        
        # FFmpeg command to remux to MPEG-TS
        # Start playback from the calculated offset
        # Note: Using copy codecs means no transcoding, just remuxing
        ffmpeg_cmd = [
            'ffmpeg',
            '-ss', str(offset_seconds),  # Seek to offset
            '-i', stream_url,  # Input from Plex
            '-c:v', 'copy',  # Copy video codec (no transcoding)
            '-c:a', 'copy',  # Copy audio codec (no transcoding)
            '-f', 'mpegts',  # Output format: MPEG-TS
            '-'  # Output to stdout
        ]
        
        # Start FFmpeg process
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=4096
        )
        
        # Log FFmpeg command for debugging
        logger.debug(f"FFmpeg command: {' '.join(ffmpeg_cmd)}")
        
        # Stream the output
        try:
            while True:
                chunk = process.stdout.read(4096)
                if not chunk:
                    break
                yield chunk
        finally:
            # Clean up the process
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            
            # Log any errors from FFmpeg
            if process.stderr:
                stderr = process.stderr.read()
                if stderr:
                    logger.debug(f"FFmpeg stderr: {stderr.decode('utf-8', errors='ignore')}")
            
            # Log exit code
            if process.returncode and process.returncode != 0:
                logger.warning(f"FFmpeg exited with code {process.returncode}")
    
    except Exception as e:
        logger.error(f"Error streaming channel {channel_num}: {e}")
        raise

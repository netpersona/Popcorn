import re
import logging
from unidecode import unidecode

logger = logging.getLogger(__name__)

CHANNEL_NUMBERS = {
    # Action & Thriller (200-299)
    'Action': 201,
    'Adventure': 202,
    'Thriller': 203,
    'Crime': 204,
    'War': 205,
    'Western': 206,
    
    # Comedy & Family (300-399)
    'Comedy': 301,
    'Animation': 302,
    'Family': 303,
    'Kids': 304,
    'Romance': 305,
    
    # Drama & Documentary (400-499)
    'Drama': 401,
    'Documentary': 402,
    'Biography': 403,
    'History': 404,
    'Sport': 405,
    'Music': 406,
    
    # Horror & Mystery (600-699)
    'Horror': 666,
    'Mystery': 601,
    'Scary Halloween': 613,
    
    # Sci-Fi & Fantasy (700-799)
    'Sci-Fi': 701,
    'Fantasy': 702,
    
    # Holiday Channels (800-899)
    'Cozy Halloween': 810,
    'Christmas': 812,
    'Valentines': 802,
    'Thanksgiving': 811,
    'New Years': 801,
    'Summer': 807
}

GENRE_KEYWORDS = {
    'action': ['action', 'aventura', 'aventure', 'azione'],
    'adventure': ['adventure', 'aventura', 'aventure', 'avventura'],
    'thriller': ['thriller', 'suspense'],
    'crime': ['crime', 'criminal', 'noir'],
    'war': ['war', 'guerre', 'guerra', 'battaglia'],
    'western': ['western', 'oeste'],
    'comedy': ['comedy', 'comedie', 'comedia', 'commedia', 'humor', 'humour'],
    'animation': ['animation', 'animacion', 'anime', 'cartoon'],
    'family': ['family', 'famille', 'familia', 'famiglia'],
    'kids': ['kids', 'children', 'enfant', 'ninos'],
    'romance': ['romance', 'romantic', 'romantique', 'romantico', 'love'],
    'drama': ['drama', 'drame'],
    'documentary': ['documentary', 'documentaire', 'documental', 'documentario'],
    'biography': ['biography', 'biographie', 'biografia', 'biopic'],
    'history': ['history', 'histoire', 'historia', 'historical'],
    'sport': ['sport', 'sports', 'deportes'],
    'music': ['music', 'musical', 'musique', 'musica'],
    'horror': ['horror', 'horreur', 'terror', 'scary', 'spooky'],
    'mystery': ['mystery', 'mystere', 'misterio', 'detective'],
    'sci-fi': ['sci-fi', 'science fiction', 'ciencia ficcion', 'sf', 'scifi'],
    'fantasy': ['fantasy', 'fantasia', 'fantastique', 'magical']
}

ICON_KEYWORDS = {
    'action': 'fa-bolt',
    'adventure': 'fa-compass',
    'thriller': 'fa-user-secret',
    'crime': 'fa-handcuffs',
    'war': 'fa-explosion',
    'western': 'fa-horse',
    'comedy': 'fa-face-laugh',
    'animation': 'fa-paintbrush',
    'family': 'fa-people-roof',
    'kids': 'fa-child',
    'romance': 'fa-heart',
    'drama': 'fa-masks-theater',
    'documentary': 'fa-video',
    'biography': 'fa-user',
    'history': 'fa-landmark',
    'sport': 'fa-futbol',
    'music': 'fa-music',
    'horror': 'fa-skull',
    'mystery': 'fa-magnifying-glass',
    'sci-fi': 'fa-rocket',
    'fantasy': 'fa-wand-magic-sparkles'
}

AVAILABLE_NUMBER_RANGES = [
    (207, 299),
    (306, 399),
    (407, 499),
    (500, 599),
    (602, 665),
    (667, 699),
    (703, 799)
]


def normalize_text(text):
    """
    Normalize text for comparison by:
    - Converting to lowercase
    - Removing accents/diacritics
    - Removing special characters
    - Replacing hyphens and spaces with nothing
    """
    text = text.lower()
    text = unidecode(text)
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r'\s+', '', text)
    return text


def find_genre_match(channel_name):
    """
    Try to find a matching genre from CHANNEL_NUMBERS using keyword detection.
    
    Args:
        channel_name: The channel name to match (e.g., "Horreur", "Film-Noir")
        
    Returns:
        tuple: (matched_genre, base_number) or (None, None) if no match
    """
    normalized_name = normalize_text(channel_name)
    
    for genre, keywords in GENRE_KEYWORDS.items():
        for keyword in keywords:
            normalized_keyword = normalize_text(keyword)
            if normalized_keyword in normalized_name or normalized_name in normalized_keyword:
                if genre.capitalize() in CHANNEL_NUMBERS:
                    base_genre = genre.capitalize()
                elif genre == 'sci-fi' and 'Sci-Fi' in CHANNEL_NUMBERS:
                    base_genre = 'Sci-Fi'
                else:
                    continue
                    
                base_number = CHANNEL_NUMBERS[base_genre]
                logger.info(f"Matched '{channel_name}' to genre '{base_genre}' (keyword: {keyword})")
                return base_genre, base_number
    
    return None, None


def get_icon_for_channel(channel_name):
    """
    Get appropriate Font Awesome icon for a channel based on keywords.
    
    Args:
        channel_name: The channel name
        
    Returns:
        str: Font Awesome icon class (e.g., 'fa-skull')
    """
    normalized_name = normalize_text(channel_name)
    
    for genre, keywords in GENRE_KEYWORDS.items():
        for keyword in keywords:
            normalized_keyword = normalize_text(keyword)
            if normalized_keyword in normalized_name or normalized_name in normalized_keyword:
                icon = ICON_KEYWORDS.get(genre, 'fa-film')
                logger.info(f"Assigned icon '{icon}' to '{channel_name}' (matched: {genre})")
                return icon
    
    return 'fa-film'


def get_alphabetical_position_number(channel_name, unmapped_channels, used_numbers):
    """
    Calculate channel number based on alphabetical position among unmapped channels.
    Distributes channels evenly across available number ranges.
    
    Args:
        channel_name: The channel to assign a number to
        unmapped_channels: List of all channels that don't have hardcoded numbers
        used_numbers: Set of already used channel numbers
        
    Returns:
        int: Alphabetically distributed channel number
    """
    sorted_channels = sorted(unmapped_channels)
    
    try:
        position = sorted_channels.index(channel_name)
    except ValueError:
        position = len(sorted_channels)
    
    total_available = sum(end - start + 1 for start, end in AVAILABLE_NUMBER_RANGES)
    total_available -= len([n for n in used_numbers if any(start <= n <= end for start, end in AVAILABLE_NUMBER_RANGES)])
    
    if total_available <= 0:
        return 999
    
    step = max(1, total_available // max(1, len(sorted_channels)))
    
    current_slot = 0
    for start, end in AVAILABLE_NUMBER_RANGES:
        range_size = end - start + 1
        if current_slot + range_size > position * step:
            offset = (position * step) - current_slot
            candidate = start + offset
            
            while candidate in used_numbers and candidate <= end:
                candidate += 1
            
            if candidate <= end:
                return candidate
        
        current_slot += range_size
    
    for start, end in AVAILABLE_NUMBER_RANGES:
        for num in range(start, end + 1):
            if num not in used_numbers:
                return num
    
    return 999


def get_next_available_number(base_number=None, used_numbers=None, channel_name=None, unmapped_channels=None):
    """
    Get the next available channel number.
    
    If base_number is provided, try to find a number near it (smart match).
    Otherwise, distribute alphabetically across available ranges.
    
    Args:
        base_number: Preferred base number to be near (e.g., 666 for horror-related)
        used_numbers: Set of already used channel numbers
        channel_name: Name of channel (required for alphabetical distribution)
        unmapped_channels: List of all unmapped channel names for alphabetical sorting
        
    Returns:
        int: Next available channel number
    """
    if used_numbers is None:
        used_numbers = set()
    
    if base_number:
        for offset in range(1, 100):
            candidate = base_number + offset
            if candidate not in used_numbers and any(start <= candidate <= end for start, end in AVAILABLE_NUMBER_RANGES):
                return candidate
    
    if channel_name and unmapped_channels:
        return get_alphabetical_position_number(channel_name, unmapped_channels, used_numbers)
    
    for start, end in AVAILABLE_NUMBER_RANGES:
        for num in range(start, end + 1):
            if num not in used_numbers:
                return num
    
    return 999


def get_all_unmapped_channels():
    """
    Get list of all channels that don't have hardcoded numbers.
    Used for alphabetical distribution.
    
    Returns:
        list: Channel names that need dynamic assignment
    """
    try:
        from models import get_session, Movie
        
        session = get_session()
        all_genres = session.query(Movie.genre).distinct().all()
        
        unmapped = []
        for genre_tuple in all_genres:
            genre = genre_tuple[0]
            if genre not in CHANNEL_NUMBERS:
                unmapped.append(genre)
        
        return unmapped
        
    except Exception as e:
        logger.error(f"Error getting unmapped channels: {e}")
        return []


def get_channel_number(channel_name, create_if_missing=True):
    """
    Get the channel number for a given channel name.
    
    First checks hardcoded CHANNEL_NUMBERS, then checks database for dynamic assignments.
    If not found and create_if_missing is True, creates a new mapping using smart matching.
    
    Args:
        channel_name: The channel name
        create_if_missing: If True, create a new mapping for unknown channels
        
    Returns:
        int: Channel number
    """
    if channel_name in CHANNEL_NUMBERS:
        return CHANNEL_NUMBERS[channel_name]
    
    try:
        from models import get_session, ChannelMapping
        
        session = get_session()
        mapping = session.query(ChannelMapping).filter_by(channel_name=channel_name).first()
        
        if mapping:
            return mapping.channel_number
        
        if not create_if_missing:
            return 999
        
        matched_genre, base_number = find_genre_match(channel_name)
        
        used_numbers = set(CHANNEL_NUMBERS.values())
        existing_mappings = session.query(ChannelMapping).all()
        for m in existing_mappings:
            used_numbers.add(m.channel_number)
        
        unmapped_channels = get_all_unmapped_channels()
        
        new_number = get_next_available_number(
            base_number=base_number, 
            used_numbers=used_numbers,
            channel_name=channel_name,
            unmapped_channels=unmapped_channels
        )
        
        icon = get_icon_for_channel(channel_name)
        
        new_mapping = ChannelMapping(
            channel_name=channel_name,
            channel_number=new_number,
            icon=icon
        )
        session.add(new_mapping)
        session.commit()
        
        logger.info(f"Created dynamic channel mapping: '{channel_name}' -> {new_number} (icon: {icon})")
        
        return new_number
        
    except Exception as e:
        logger.error(f"Error getting channel number for '{channel_name}': {e}")
        return 999


def get_channel_icon(channel_name):
    """
    Get the icon for a channel.
    
    Args:
        channel_name: The channel name
        
    Returns:
        str: Font Awesome icon class
    """
    try:
        from models import get_session, ChannelMapping
        
        session = get_session()
        mapping = session.query(ChannelMapping).filter_by(channel_name=channel_name).first()
        
        if mapping and mapping.icon:
            return mapping.icon
        
        return get_icon_for_channel(channel_name)
        
    except Exception as e:
        logger.error(f"Error getting icon for '{channel_name}': {e}")
        return 'fa-film'


def format_channel_display(channel_name):
    number = get_channel_number(channel_name)
    return f"{number} {channel_name}"

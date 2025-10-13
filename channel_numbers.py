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

def get_channel_number(channel_name):
    return CHANNEL_NUMBERS.get(channel_name, 999)

def format_channel_display(channel_name):
    number = get_channel_number(channel_name)
    return f"{number} {channel_name}"

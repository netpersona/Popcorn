# Popcorn - Cable-Style Movie Scheduler

## Overview

Popcorn is a Flask-based web application that creates cable TV-style movie channels from a Plex media library. It automatically generates schedules for different genre-based channels (including seasonal holiday channels) and presents them in a nostalgic cable TV guide interface. Users can browse channels, view what's currently playing, see daily schedules, and play movies directly through Plex.

## System Architecture

### Frontend Architecture
- **Template Engine**: Jinja2 templates with Bootstrap 5 for responsive UI
- **Styling**: Custom CSS with gradient backgrounds and card-based layouts
- **JavaScript**: Minimal client-side scripting for interactive elements (play buttons, navigation)
- **Design Pattern**: Traditional server-side rendering with full page loads

**Rationale**: Server-side rendering provides simplicity and doesn't require a complex frontend build process. Bootstrap ensures mobile responsiveness out of the box.

### Backend Architecture
- **Framework**: Flask (Python) for lightweight web serving
- **ORM**: SQLAlchemy for database abstraction and model management
- **Session Management**: Flask sessions with secret key configuration
- **Logging**: Python's built-in logging module for application monitoring

**Design Decision**: Flask was chosen for its simplicity and ease of integration with Python libraries for media management. SQLAlchemy provides database flexibility without being tied to a specific database engine.

### Data Storage
- **Database**: SQLAlchemy-based (default SQLite via `popcorn.db`)
- **Schema Design**:
  - `movies` table: Stores movie metadata from Plex (title, genre, duration, plex_id, year, rating, summary)
  - `schedules` table: Stores generated TV schedules (channel, movie_id, start_time, end_time, day)
  - `holiday_channels` table: Defines seasonal channels (name, date ranges, keywords, rating filters)
  - `settings` table: Application configuration (shuffle frequency, etc.)

**Unique Constraint**: Movies have a composite unique constraint on `plex_id` and `genre` to handle movies with multiple genres

**Rationale**: SQLite provides zero-configuration persistence suitable for personal media servers. The schema supports many-to-many relationships between movies and schedules while maintaining referential integrity.

### Core Components

#### Plex Integration (`plex_api.py`)
- Uses `plexapi` library to connect to Plex Media Server
- Fetches movie metadata including genres, duration, ratings, and summaries
- Requires `PLEX_URL` and `PLEX_TOKEN` environment variables
- Gracefully handles connection failures with logging

**Design Decision**: Direct integration with Plex API ensures real-time access to the user's actual media library without manual data entry.

#### Schedule Generator (`scheduler.py`)
- Generates cable TV-style schedules for genre-based channels
- Supports seasonal "holiday channels" with date-based activation
- Uses keyword matching and rating filters for channel content
- Implements automatic reshuffling based on configured frequency (daily/weekly/monthly)

**Features**:
- Random movie selection within channel constraints
- Time slot allocation based on movie duration
- Multi-genre support (same movie can appear on multiple channels)
- Pre-configured holiday channels (Cozy Halloween, Scary Halloween, Christmas)

**Rationale**: Automated scheduling recreates the serendipitous discovery experience of cable TV while respecting content appropriateness through rating filters.

#### Application Initialization
- Database initialization on startup
- Automatic Plex library sync on first run
- Schedule generation for all channels
- Graceful degradation if Plex is unavailable

### Routing Structure
- `/` - Channel list homepage
- `/channel/<name>` - Individual channel view with schedule
- `/settings` - Configuration and manual reshuffle
- `/sync` - Manual Plex library sync trigger

### Error Handling
- Dedicated error template for user-friendly error messages
- Comprehensive logging throughout the application
- Fallback behaviors when Plex is unavailable

## External Dependencies

### Third-Party Services
- **Plex Media Server**: Primary media source
  - Requires network access to Plex server
  - Authentication via API token
  - Used for: Movie metadata retrieval and playback

### Python Libraries
- **Flask**: Web framework
- **SQLAlchemy**: ORM and database toolkit
- **plexapi**: Official Plex API wrapper
- **python-dotenv**: Environment variable management
- **Bootstrap 5** (CDN): Frontend CSS framework
- **Font Awesome 6** (CDN): Icon library

### Environment Configuration
Required environment variables:
- `PLEX_URL`: Plex server base URL
- `PLEX_TOKEN`: Plex authentication token
- `PLEX_CLIENT`: Client identifier (optional)
- `SESSION_SECRET`: Flask session secret (defaults to dev key)

### Database
- SQLite (default, file-based at `popcorn.db`)
- Configurable to other SQLAlchemy-supported databases
- No external database server required for basic operation

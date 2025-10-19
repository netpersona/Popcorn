# Popcorn - Cable-Style Movie Scheduler

## Overview

Popcorn is a Flask-based web application that transforms a Plex media library into an interactive, nostalgic cable TV experience. The application automatically generates genre-based and seasonal movie schedules, presenting them in a TV guide interface that mimics traditional cable television. Users can browse channels, view schedules, and launch movies directly on their Plex devices.

Key features include:
- Automatic channel generation based on movie genres (Action, Comedy, Drama, Horror, etc.)
- Seasonal holiday channels (Halloween, Christmas, etc.)
- TV guide interface with time-based program grid
- Multi-device playback management for Plex clients
- User authentication with Plex OAuth integration
- Customizable themes and retro TV aesthetic options
- Watch history tracking and viewing statistics
- Admin controls for user management and system settings

---

## Installation

### Docker Compose (Recommended - Everything Pre-Configured!)

The easiest way to run Popcorn is with Docker Compose - all volume mappings are pre-configured:

1. **Download the docker-compose.yml file** from this repo
2. **Edit two values**:
   - Change `SESSION_SECRET` to a random string (generate with `openssl rand -hex 32`)
   - Optionally add your Plex URL and token
3. **Run it**:

```bash
docker-compose up -d
```

That's it! Your data automatically persists in `./popcorn-data` and survives updates.

**To update:** `docker-compose pull && docker-compose up -d`

---

### Unraid (Also Pre-Configured!)

Install from **Community Applications**:
1. Search for "Popcorn" in Community Applications
2. The template has all volume mappings pre-configured
3. Just fill in your SESSION_SECRET and optionally Plex settings
4. Click Apply!

See [UNRAID_SETUP.md](UNRAID_SETUP.md) for details.

---

### Manual Docker Run

If you prefer the command line (requires manual volume configuration):

```bash
docker run -d \
  --name Popcorn \
  -p 5000:5000 \
  -v ./popcorn-data:/data \
  -e SESSION_SECRET="$(openssl rand -hex 32)" \
  -e PLEX_URL="http://192.168.1.100:32400" \
  -e PLEX_TOKEN="your-plex-token" \
  --restart unless-stopped \
  netpersona/popcorn:latest
```

**⚠️ Critical:** The `-v ./popcorn-data:/data` flag maps your database to a local directory. Without it, you'll lose all data when updating the container.

---

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SESSION_SECRET` | Yes | Secret key for session encryption (generate with `openssl rand -hex 32`) |
| `PLEX_URL` | No* | Your Plex server URL (e.g., `http://192.168.1.100:32400`) |
| `PLEX_TOKEN` | No* | Your Plex authentication token |
| `DATA_DIR` | No | Data directory path (default: `/data` in Docker, `./` for local dev) |

*Can be configured through the web interface after first login

**Note for Advanced Users:** If you set `DATA_DIR` to a custom path in your Docker image, the volume detection will show a warning unless that path is a proper mount point. This is intentional to prevent data loss. To disable the warning, ensure your custom path is mounted, or use the default `/data` location.

---

### Finding Your Plex Token

1. Open Plex Web App and play any item
2. Click the ⓘ icon → "View XML"
3. Look for `X-Plex-Token=` in the URL
4. Copy the token value

See [Plex Support](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/) for details.

---

### First-Time Setup

1. Access the web interface at `http://your-server-ip:5000`
2. Log in with default credentials:
   - **Username:** `admin`
   - **Password:** `admin`
3. **Change the default password immediately** (you'll see a warning banner)
4. Configure Plex settings in Admin → Settings if not set via environment variables
5. Generate your first schedule from the home page

---

### Local Development

```bash
# Clone the repository
git clone https://github.com/netpersona/Popcorn.git
cd Popcorn

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export SESSION_SECRET="$(openssl rand -hex 32)"
export PLEX_URL="http://192.168.1.100:32400"
export PLEX_TOKEN="your-token-here"

# Run the application
python app.py
```

Access at `http://localhost:5000`

---

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture

**Server-Side Rendering (SSR)**: The application uses Jinja2 templates with Bootstrap 5 for UI rendering. All pages are generated server-side, reducing client-side JavaScript complexity.

**Dynamic Theme System**: Themes are managed through CSS custom properties (CSS variables), allowing users to switch between predefined themes (Plex, Halloween, etc.) or create custom themes. Theme colors are injected into templates at render time, ensuring consistent styling across all pages.

**Mobile-Responsive Design**: The UI implements responsive breakpoints for Mobile (<600px), Tablet (600-1023px), and Desktop (≥1024px). The TV guide adapts from a horizontal scrolling grid on desktop to vertical channel stacking with horizontally scrollable movie tiles on mobile devices.

**Interactive Elements**: JavaScript is used minimally for specific interactions like device discovery modals, poster hover effects, and the hamburger navigation menu. Touch-friendly interactions support tap-to-show-info and tap-to-play workflows on mobile devices.

**Retro TV Aesthetic**: Admin-toggleable visual features include CRT monitor effects, film grain overlay, and classic cable channel numbering system (e.g., Horror = Channel 666).

### Backend Architecture

**Web Framework**: Flask serves as the core web framework, handling routing, session management, and request/response cycles.

**Authentication System**: Multi-strategy authentication supporting both Plex OAuth and local username/password accounts. Flask-Login manages user sessions. Default demo accounts (`admin`/`admin`, `demo`/`demo`) are created on first startup for immediate access.

**Schedule Generation**: The `ScheduleGenerator` class creates 24-hour movie schedules by:
1. Fetching movies from Plex and categorizing by genre
2. Generating time slots based on movie duration
3. Creating holiday channels with keyword and genre filtering
4. Storing schedules in the database for quick retrieval

**Multi-Device Playback**: Users can save multiple Plex client devices (TVs, streaming sticks, etc.) with platform-specific identification. The system supports device discovery via Plex API and manages playback initiation to the selected device.

**Image Caching**: A bounded LRU cache (max 300 items, ~150MB) stores movie posters to reduce repeated requests to Plex servers. The cache evicts oldest items when limit is reached.

**Security Features**: CSRF protection on all forms, password hashing with Werkzeug, session secret key management, and security warnings for users with default passwords.

### Data Storage

**SQLAlchemy ORM**: Database abstraction layer supporting SQLite by default (can be configured for other databases via Drizzle adapter if needed).

**Core Data Models**:
- `User`: Authentication, preferences (theme, default device), admin flags
- `Movie`: Plex movie metadata (title, genre, duration, ratings, poster URLs)
- `Schedule`: Time-slot assignments for movies on channels
- `HolidayChannel`: Configuration for seasonal channels (date ranges, keyword filters)
- `WatchHistory`: User viewing records for statistics and "watched" badges
- `Invitation`: Admin-generated invite codes for user registration
- `CustomTheme`: User-created color themes
- `SavedDevice`: User's saved Plex playback devices

**Database Migrations**: Idempotent migration system ensures safe schema updates during application upgrades.

### External Dependencies

**Plex Media Server Integration**:
- **PlexAPI Library**: Python library for interacting with Plex servers
- **Required Credentials**: Plex server URL and authentication token (configured via environment variables or database settings)
- **Functionality**: Fetches movie libraries, retrieves metadata, initiates playback on client devices, discovers available Plex clients
- **Client Discovery**: Real-time device discovery showing platform-specific icons (Roku, Android, iOS, Xbox, etc.)

**Plex OAuth Service**:
- **Purpose**: Allow users to authenticate using their Plex.tv accounts
- **Flow**: PIN-based OAuth flow generates auth URLs, polls for authorization, retrieves user tokens
- **Endpoints**: `https://plex.tv/api/v2/pins` for PIN generation, `https://plex.tv/users/account.json` for user profile

**Session Management**:
- **Flask-Login**: Handles user session persistence and authentication state
- **Session Secret**: Requires `SESSION_SECRET` environment variable for secure session encryption

**Form Security**:
- **Flask-WTF**: Provides CSRF protection for all forms
- **CSRFProtect**: Global CSRF token validation on POST requests

**Image Proxying**:
- **Requests Library**: Fetches movie posters from Plex servers and proxies them through the application
- **Purpose**: Avoids CORS issues and enables caching

**Update System** (Optional):
- **GitHub Integration**: `UpdateManager` class can check for new releases from GitHub repository
- **Docker Detection**: Automatically detects if running in Docker container to adjust update behavior

**Frontend Assets**:
- **Bootstrap 5**: CDN-hosted CSS framework
- **Font Awesome 6**: CDN-hosted icon library
- **Custom CSS**: Inline styles in templates for theme-specific styling
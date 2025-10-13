# Popcorn - Cable-Style Movie Scheduler

## Overview
Popcorn is a Flask-based web application that transforms a Plex media library into an interactive, nostalgic cable TV experience. It automatically generates genre-based and seasonal movie schedules, presented in a TV guide interface with movie posters. The application enables users to browse channels, view schedules, and play movies directly through Plex, optionally with time-based seeking to simulate live broadcasts. Its core purpose is to offer a unique, serendipitous content discovery experience reminiscent of traditional cable television.

The dashboard:

<img width="1915" height="890" alt="Dashboard" src="https://github.com/user-attachments/assets/983e5807-5517-425b-9aaa-0fbc0e593133" />


The user profile page has a metric tracking system to promote user engagement as well as a custom themeing system which any user or the community may edit to allow sharing of themes:

<img width="1191" height="847" alt="image" src="https://github.com/user-attachments/assets/21b40b5b-3757-4a83-b0a6-7a4cee67385b" />

Users are also allowed to change their viewing preferences:

<img width="1173" height="596" alt="Viewing" src="https://github.com/user-attachments/assets/e1a19559-7e2b-4e53-b669-9a8330bb4242" />

Users can choose which channels show up on their dashboard:

<img width="1183" height="603" alt="Visibility" src="https://github.com/user-attachments/assets/ea51de63-613e-4390-81b2-82d3bafa8e61" />


**Latest Updates (v2.0.0):**
- Default demo accounts for instant access (`admin`/`admin`, `demo`/`demo`)
- Security warning system for default passwords
- Self-service password change functionality
- Enhanced deployment readiness for public demo environments

## User Preferences
I prefer detailed explanations.
Do not make changes to the folder `Z`.
Do not make changes to the file `Y`.

## System Architecture

### Frontend Architecture
-   **Template Engine**: Jinja2 with Bootstrap 5.
-   **Styling**: Custom CSS with a dynamic theme system using CSS custom properties.
-   **JavaScript**: Minimal, focused on interactive elements.
-   **Design Pattern**: Server-Side Rendering (SSR).
-   **UI/UX**: Mimics a nostalgic cable TV guide, featuring a modern hamburger navigation, circular Plex avatars, and movie posters. The UI includes interactive elements like poster hover effects, quick info overlays, skeleton loading, fade-in animations, pulsing "Now Playing" indicators, dynamic progress bars, smooth scrolling, toast notifications, keyboard shortcuts, and `localStorage` persistence for scroll position.
-   **Retro TV Aesthetic**: Admin-toggleable features such as CRT monitor effects, film grain overlay, and classic cable channel numbers. "Watched" badges indicate previously viewed content.
-   **Navigation Design**: Consistent hamburger menu across all pages, with a scroll-synchronized channel rail and program grid.
-   **Visual Enhancements**: Vertical dividers in time headers, current time slot highlighting, genre-specific icons for channels, glassmorphism header with animated logo glow, pulsing LIVE indicator, and custom scrollbar styling.
-   **Movie Tile Layout**: Uses landscape artwork for movie tiles with smart positioning for badges (rating, watched, favorite) and intelligent hover overlay positioning to prevent clipping.

### Backend Architecture
-   **Framework**: Flask (Python).
-   **Template Folder**: `pages/` directory (renamed from `templates/` for clarity).
-   **ORM**: SQLAlchemy.
-   **Session Management**: Flask sessions.
-   **Logging**: Python's built-in logging module.

### Data Storage
-   **Database**: SQLite (default), configurable for other SQLAlchemy-supported databases.
-   **Schema Design**: Tables for movies, schedules, holiday channels, application settings, watch history, user favorites, and channel favorites.
-   **Automatic Migrations**: Idempotent schema upgrades executed on startup for safe column additions and table creation.

### Core Components
-   **Plex Integration**: Uses `plexapi` for metadata fetching and direct playback with `seekTo` functionality.
-   **Image Caching System**: Server-side LRU cache for Plex movie posters via a `/api/poster/<plex_id>` endpoint with browser caching. Landscape artwork is prioritized with a fallback to portrait posters.
-   **Schedule Generator**: Creates genre-based and seasonal "holiday channels" with automatic reshuffling and content filtering.
-   **Playback Settings**: Per-user configuration for playback preferences, including "Web Player" or "Client Playback" (requiring a Plex Client ID) and "Live TV Mode" for time offset and automatic seeking.
-   **Theme System**: 15 default themes and support for custom JSON theme uploads.
-   **Auto-Update System**: Checks GitHub for updates, offering one-click updates with database backups for native environments and notifications for Docker.
-   **Security Features**: 
    -   Plex OAuth (PIN-based) and local login
    -   Role-based access (admin/user)
    -   User management with invitation codes
    -   CSRF protection and secure cookie handling
    -   **Default demo accounts** (`admin`/`admin`, `demo`/`demo`) for instant access
    -   **Security warning banners** for users with default passwords
    -   **Self-service password management** with validation and secure hashing
    -   Password security flags (`using_default_password`) for tracking default credentials
-   **Favorites System**: Allows users to mark movies as favorites, stored in the database, and indicated in the UI.
-   **Glow Brightness Controls**: Admin-set global maximum glow brightness, with per-user adjustment within that limit, impacting visual effects like "Now Playing" indicators.
-   **Watch History**: Tracks user playback for personalized viewing statistics and "watched" badges.

### Routing Structure
-   Core routes for channels, playback, settings, user management, and authentication.
-   API endpoints for theme management, updates, and user interactions (e.g., favoriting).

## External Dependencies

### Third-Party Services
-   **Plex Media Server**: Primary media source and playback engine.

### Python Libraries
-   **Flask**: Web framework.
-   **SQLAlchemy**: Object Relational Mapper.
-   **plexapi**: Python wrapper for the Plex API.
-   **python-dotenv**: For managing environment variables.

### Frontend Libraries
-   **Bootstrap 5**: CSS framework (via CDN).
-   **Font Awesome 6**: Icon library (via CDN).

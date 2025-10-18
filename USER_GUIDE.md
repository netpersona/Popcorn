# Popcorn - User Guide

Welcome to Popcorn! This guide will help you get started with your cable-style movie scheduling system for Plex.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Getting Your Plex Credentials](#getting-your-plex-credentials)
4. [Installation Methods](#installation-methods)
   - [Docker Installation (Recommended)](#docker-installation-recommended)
   - [Direct Python Installation](#direct-python-installation)
5. [Configuration](#configuration)
6. [Using Popcorn](#using-popcorn)
7. [Troubleshooting](#troubleshooting)

---

## Overview

Popcorn creates cable TV-style movie channels from your Plex media library. It automatically generates:
- **Genre-based channels** (Action, Comedy, Drama, etc.) based on your movies
- **Seasonal holiday channels** (Cozy Halloween, Scary Halloween, Christmas)
- **24-hour schedules** with movies playing back-to-back
- **TV guide interface** for browsing what's "on air"

---

## Prerequisites

Before installing Popcorn, you'll need:

1. **A Plex Media Server** running with a movie library
2. **Docker** (for Docker installation) - [Install Docker](https://docs.docker.com/get-docker/)
   - OR **Python 3.11+** (for direct installation)
3. **Network access** to your Plex server
4. **Plex authentication token** (instructions below)

---

## Getting Your Plex Credentials

### Step 1: Get Your Plex URL

Your Plex URL is typically:
- **Local network**: `http://192.168.1.100:32400` (replace with your server's IP)
- **Remote access**: `https://YOUR-SERVER-ID.plex.direct:32400`

To find your server IP:
1. Open Plex Web App
2. Go to Settings → Network
3. Note the IP address shown

### Step 2: Get Your Plex Token

#### Method 1: Using Plex Web App (Easiest)
1. Open a movie in Plex Web App
2. Click the three dots (⋮) → "Get Info"
3. Click "View XML"
4. Look in the URL bar for `X-Plex-Token=XXXXX`
5. Copy everything after the equals sign

#### Method 2: Using Browser Developer Tools
1. Open Plex Web App in your browser
2. Press `F12` to open Developer Tools
3. Go to the Console tab
4. Type: `localStorage.getItem('myPlexAccessToken')`
5. Press Enter and copy the token (without quotes)

#### Method 3: Using Plex API
1. Sign in at https://www.plex.tv/sign-in
2. Navigate to: https://plex.tv/devices.xml
3. Find your server in the XML and look for `token="YOUR_TOKEN"`

### Step 3: Get Your Plex Client Name (Optional, for Roku playback)

To play movies directly on a Plex client (like Roku):
1. Make sure your Plex client is running and connected to your server
2. The client name is usually the device name (e.g., "Roku Living Room")
3. You can see available clients in Popcorn at: Settings → View Available Clients

---

## Installation Methods

### Unraid Installation

If you're running Unraid, see the dedicated **[UNRAID_SETUP.md](UNRAID_SETUP.md)** guide for:
- Installing from Community Applications
- Manual template installation
- Unraid-specific configuration
- Troubleshooting on Unraid

### Docker Installation (Recommended)

Docker is the easiest way to run Popcorn. It handles all dependencies automatically.

#### Step 1: Build the Docker Image

```bash
# Navigate to the Popcorn directory
cd /path/to/popcorn

# Build the Docker image
docker build -t popcorn .
```

This will take a few minutes to download dependencies and build the image.

#### Step 2: Run the Container

**Basic setup (without Plex):**
```bash
docker run -d \
  --name popcorn \
  -p 5000:5000 \
  -e SESSION_SECRET="your-random-secret-key-change-this" \
  popcorn
```

**Full setup (with Plex connection):**
```bash
docker run -d \
  --name popcorn \
  -p 5000:5000 \
  -e SESSION_SECRET="your-random-secret-key-change-this" \
  -e PLEX_URL="http://192.168.1.100:32400" \
  -e PLEX_TOKEN="your-plex-token-here" \
  -e PLEX_CLIENT="Roku Living Room" \
  -v popcorn-data:/app \
  --restart unless-stopped \
  popcorn
```

**Environment Variables Explained:**
- `SESSION_SECRET` - Random string for session security (required)
- `PLEX_URL` - Your Plex server URL (required for Plex features)
- `PLEX_TOKEN` - Your Plex authentication token (required for Plex features)
- `PLEX_CLIENT` - Name of your Plex playback device (optional, for direct playback)

#### Step 3: Access Popcorn

Open your browser and go to:
```
http://localhost:5000
```

Or from another device on your network:
```
http://YOUR-SERVER-IP:5000
```

#### Docker Management Commands

```bash
# Stop Popcorn
docker stop popcorn

# Start Popcorn
docker start popcorn

# View logs
docker logs popcorn

# Remove container
docker rm -f popcorn
```

#### Updating Popcorn (Docker)

When running in Docker, Popcorn will automatically detect updates but won't apply them automatically (Docker best practice). To update:

**Step 1: Check for Updates**
1. Go to Settings (admin only)
2. Click "Check for Updates"
3. If an update is available, you'll see: "Running in Docker: Please pull the latest image to update"

**Step 2: Pull and Restart**
```bash
# Pull the latest image
docker pull netpersona/popcorn:latest

# Stop and remove the old container
docker stop popcorn
docker rm popcorn

# Start with the new image (use your original docker run command)
docker run -d \
  --name popcorn \
  -p 5000:5000 \
  -e SESSION_SECRET="your-secret-here" \
  -e PLEX_URL="http://192.168.1.100:32400" \
  -e PLEX_TOKEN="your-token" \
  -v popcorn-data:/app \
  --restart unless-stopped \
  netpersona/popcorn:latest
```

**Note:** Your database and settings are preserved in the volume, so you won't lose any data.

---

### Direct Python Installation

If you prefer not to use Docker:

#### Step 1: Install Python Dependencies

```bash
# Make sure you have Python 3.11+ installed
python --version

# Install dependencies
pip install -r requirements.txt
```

#### Step 2: Set Environment Variables

**Linux/Mac:**
```bash
export SESSION_SECRET="your-random-secret-key"
export PLEX_URL="http://192.168.1.100:32400"
export PLEX_TOKEN="your-plex-token"
export PLEX_CLIENT="Roku Living Room"
```

**Windows (PowerShell):**
```powershell
$env:SESSION_SECRET="your-random-secret-key"
$env:PLEX_URL="http://192.168.1.100:32400"
$env:PLEX_TOKEN="your-plex-token"
$env:PLEX_CLIENT="Roku Living Room"
```

Or create a `.env` file:
```
SESSION_SECRET=your-random-secret-key
PLEX_URL=http://192.168.1.100:32400
PLEX_TOKEN=your-plex-token
PLEX_CLIENT=Roku Living Room
```

#### Step 3: Run the Application

```bash
python app.py
```

Access at `http://localhost:5000`

---

## Configuration

### First Time Setup

#### Default Demo Accounts

For quick evaluation and demo purposes, Popcorn automatically creates two default accounts on first startup:

| Username | Password | Role | Purpose |
|----------|----------|------|---------|
| `admin` | `admin` | Administrator | Full access to all features and settings |
| `demo` | `demo` | User | Standard user access for demonstration |

**⚠️ Security Warning**: These accounts use weak default passwords and should **only be used for initial testing**. You will see a prominent security warning banner until you change these passwords.

#### First Login & Security

1. **Access Popcorn** in your browser (e.g., `http://localhost:5000`)
2. **Log in** with either:
   - Admin account: `admin` / `admin`
   - Demo account: `demo` / `demo`
3. **Security Warning Appears**: You'll see a red pulsing banner at the top:
   ```
   ⚠️ SECURITY WARNING: You are using a default password!
   Change your password immediately in your profile settings.
   ```
4. **Change Password Immediately**:
   - Click the warning banner or navigate to Profile
   - Scroll to "Change Password" section
   - Enter current password, new password, and confirm
   - Click "Change Password"
   - Security warning disappears automatically

#### Plex Connection Setup

1. **Start Popcorn** with your Plex credentials configured (see environment variables)
2. **Automatic sync** will begin - Popcorn scans your Plex library
3. **Channels are generated** automatically based on movie genres
4. **Schedules are created** with 24-hour programming

### Settings Page

Access settings at: `http://localhost:5000/settings`

**Reshuffle Frequency:**
- **Daily** - New schedule every day at midnight
- **Weekly** - New schedule every 7 days
- **Monthly** - New schedule every 30 days

**Manual Actions:**
- **Reshuffle Now** - Generate new schedules immediately
- **View Available Clients** - See connected Plex devices

### Holiday Channels

Holiday channels are automatically activated during their seasons:

| Channel | Active Period | Content | Rating Filter |
|---------|--------------|---------|---------------|
| Cozy Halloween 👻 | September - November | Family-friendly Halloween movies | G, PG, PG-13 |
| Scary Halloween 💀 | September - November | Horror and scary movies | PG-13, R |
| Christmas 🎄 | November - January | Christmas and holiday movies | All ratings |

---

## Using Popcorn

### TV Guide View

The main interface shows a grid-style TV guide:

1. **Channel list** on the left shows all available channels
2. **Time grid** across the top (24 hours in 30-minute increments)
3. **Program tiles** show what's playing at each time
4. **Current time indicator** (orange line) shows "now"
5. **Jump to Now** button scrolls to current time

**Interacting with the Guide:**
- Scroll horizontally to see different times
- Scroll vertically to browse channels
- Click any program tile to open it in Plex

### Channels View

Browse channels individually:

1. See all channels in a card layout
2. Shows what's currently playing on each channel
3. Click a channel to see its full 24-hour schedule

### Playing Movies

**On Desktop/Mobile:**
1. Click any movie in the guide or schedule
2. A new tab opens attempting to launch Plex
3. If Plex app is installed, it opens the movie
4. Otherwise, you're redirected to Plex Web to cast/play

**On TV/Roku:**
1. Browse Popcorn on your phone/tablet/computer
2. Click a movie to open it in Plex
3. From Plex app/web, cast to your Roku or TV
4. Movie plays on your TV through Plex

### Syncing Your Library

To update Popcorn with new movies:

1. Go to the menu and click **Sync**
2. Or manually visit: `http://localhost:5000/sync`
3. Popcorn scans your Plex library for new movies
4. New movies are added to appropriate channels
5. Schedules are regenerated automatically

### Theme Customization

Popcorn includes 11 built-in themes plus support for custom themes:

**Built-in Themes:**
- **Plex** - Classic Plex dark theme (default)
- **Halloween** - Orange and black with coral accents
- **Hell-o-ween** - Dark and fiery with orange/red accents
- **Pastel Dream** - Soft pastel colors
- **Plastic** - Modern gradient design
- **Popcorn** - Warm theater-inspired colors
- **Midnight Harmony** - Deep blues and purples
- **Ichor Wine** - Rich burgundy tones
- **Vampirism** - Dark purple vampire aesthetic
- **Lavender** - Soft purple theme
- **Starry Night** - Dark blue night sky theme

**Changing Your Theme:**
1. Navigate to Profile page (via hamburger menu)
2. Find the "Theme Selection" section
3. Choose from the dropdown
4. Click "Save Theme"
5. Theme applies instantly across all pages

**Creating Custom Themes:**

You can upload your own custom theme JSON files:

1. Go to Profile page
2. Click "Upload Theme" button
3. Select your JSON theme file (max 50KB)
4. Theme appears with a ⭐ star icon
5. Select and save to apply

**Custom Theme Format:**

Create a JSON file with the following structure:

```json
{
  "name": "My Custom Theme",
  "description": "A unique theme I created",
  "bg-primary": "#1a1a1a",
  "bg-secondary": "#2d2d2d",
  "bg-tertiary": "#3d3d3d",
  "accent": "#ff6b6b",
  "accent-hover": "#ff5252",
  "text-primary": "#ffffff",
  "text-secondary": "#cccccc",
  "text-muted": "#888888",
  "border": "#444444",
  "shadow": "rgba(0, 0, 0, 0.3)"
}
```

**Requirements:**
- All 10 color properties are required
- Must be valid JSON format
- File size under 50KB
- Use valid CSS color values (hex, rgb, rgba)

**Managing Custom Themes:**
- Your custom themes show with a ⭐ star icon
- Click the trash icon to delete themes you own
- Admins can mark custom themes as public for all users

### Playback Settings

Configure how movies play when you click them:

**Playback Mode:**
- **Web Player** (default) - Opens in browser
- **Client Playback** - Sends to configured Plex device (Roku, Apple TV, etc.)

**Time Offset:**
- **Enabled** (default) - Movies start at their current "live" position
- **Disabled** - Movies always start from the beginning

Access these settings from your Profile page.

### User Profile

Your profile page shows:
- **Username and email** - Account information
- **Theme selection** - Choose or upload themes
- **Playback settings** - Configure movie playback
- **Avatar** - Circular profile picture
- **Password management** - Change your password

#### Changing Your Password

To update your password:

1. **Navigate to Profile** (via hamburger menu → Profile)
2. **Scroll to Account Information** section
3. **Find "Change Password"** section
4. **Fill in the form**:
   - Current Password: Your existing password
   - New Password: Your new password (minimum 4 characters)
   - Confirm New Password: Re-enter new password
5. **Click "Change Password"**
6. **Success**: Password updated, security warning removed (if applicable)

**Password Requirements:**
- Minimum 4 characters
- Must match confirmation field
- Current password must be correct

**Common Errors:**
- "Current password is incorrect" - Check your existing password
- "New passwords do not match" - Ensure both new password fields match
- "Password must be at least 4 characters" - Use a longer password

**Security Tips:**
- Use a unique password not used elsewhere
- Change default passwords immediately after first login
- Choose a memorable but secure password
- Avoid common words or patterns

---

## Troubleshooting

### Problem: "Plex API not available" Error

**Symptoms:** App works but shows no movies, channels are empty

**Solutions:**
1. Verify `PLEX_URL` is correct:
   ```bash
   curl http://YOUR-PLEX-URL:32400/identity
   ```
   Should return XML with server info

2. Verify `PLEX_TOKEN` is correct:
   ```bash
   curl "http://YOUR-PLEX-URL:32400/library/sections?X-Plex-Token=YOUR-TOKEN"
   ```
   Should return your libraries

3. Check network connectivity:
   - Make sure Popcorn can reach your Plex server
   - If using Docker, ensure containers can communicate
   - Check firewall rules

4. Restart with correct environment variables:
   ```bash
   docker restart popcorn
   # Check logs
   docker logs popcorn
   ```

### Problem: "No Plex Clients Found" / Client Playback Not Working

**Symptoms:** 
- Error: "No Plex clients found. Make sure a Plex player is running..."
- Error: "Client not found. Available: []"
- Playback fails even though device is visible in Plex web interface

**Root Cause:** Popcorn cannot discover your Plex playback devices via the local network API.

#### Solution 1: Use Correct Local PLEX_URL ⭐ MOST COMMON FIX

**The Problem:** Using a public/remote Plex URL prevents local client discovery.

```bash
# ✅ CORRECT - Local network IP
PLEX_URL=http://192.168.1.100:32400
PLEX_URL=http://10.0.0.25:32400

# ❌ WRONG - Public IP, domain, or remote URL
PLEX_URL=http://66.241.174.242:19019
PLEX_URL=https://plex.mydomain.com:32400
```

**Why:** The Plex `/clients` API endpoint only discovers devices on the same local network. Remote/public URLs use Plex's cloud relay which doesn't expose local client information.

**How to Find Your Local Plex IP:**
1. On your Plex server machine, run: `ip addr` (Linux) or `ipconfig` (Windows)
2. Look for your local IP (usually starts with `192.168.x.x` or `10.0.x.x`)
3. Plex default port is `32400`

**Verify it works:**
```bash
# Should return XML listing your clients (while Plex app is open on device)
curl "http://YOUR_LOCAL_IP:32400/clients?X-Plex-Token=YOUR_TOKEN"
```

If you get `<MediaContainer size="0">` (empty), you're using the wrong URL or have other issues below.

#### Solution 2: Enable Host Network Mode (Docker/Unraid)

**The Problem:** Bridge network mode blocks GDM (Good Day Mate) discovery protocol.

**For Docker:**
```bash
docker run -d --name popcorn \
  --network host \  # Add this line
  -e PLEX_URL="http://192.168.1.100:32400" \
  -e PLEX_TOKEN="your-token" \
  popcorn
```

**For Docker Compose:**
```yaml
services:
  popcorn:
    network_mode: host  # Add this line
```

**For Unraid:**
1. Edit Popcorn container
2. Change **Network Type** from `Bridge` to `Host`
3. Remove port mappings (not needed in host mode)
4. Save and restart

**Why:** Bridge mode isolates containers from multicast network broadcasts that Plex uses to discover local devices.

**Important:** Your Plex server container may also need host mode if it's in bridge mode.

#### Solution 3: Whitelist Plex Domain (Pi-hole / DNS Ad-Blockers)

**The Problem:** DNS ad-blockers may block Plex's companion app service.

**If using Pi-hole, AdGuard Home, or similar DNS ad-blockers:**

1. **Whitelist this domain:**
   ```
   config.claspws.tv
   ```

2. **In Pi-hole:**
   - Go to Whitelist
   - Add exact domain: `config.claspws.tv`
   - Save changes

3. **Restart Plex app** on your playback device

**Why:** `config.claspws.tv` is Plex's companion app service used for device authentication and discovery. Blocking it prevents proper client advertisement.

#### Solution 4: Ensure Plex App is Running on Target Device

**The Problem:** Devices only advertise themselves when the Plex app is actively running.

**Requirements:**
- ✅ Plex app **must be open** on your Roku/TV/device
- ✅ Can be on home screen (doesn't need to be playing)
- ❌ Won't work if app is closed/background

**Test:**
1. Open Plex app on your Roku/device
2. Leave it on the home screen
3. Check if it appears in API:
   ```bash
   curl "http://YOUR_LOCAL_IP:32400/clients?X-Plex-Token=YOUR_TOKEN"
   ```
4. Device should appear in XML output

#### Solution 5: Use Device UUID Instead of Name

**The Problem:** Multiple devices may have the same name, causing ambiguity.

**Get Your Device's Unique UUID:**

Visit: `https://plex.tv/api/resources.xml?X-Plex-Token=YOUR_TOKEN`

Find your device and copy its `clientIdentifier`:
```xml
<Device name="Roku Streaming Stick 4K" 
        clientIdentifier="6d89441adccb7d3506b90954cddc17cf"
        product="Plex for Roku" />
```

**In Popcorn:**
1. Go to **Profile** → **Playback Settings**
2. Set **Plex Client ID** to the UUID:
   ```
   6d89441adccb7d3506b90954cddc17cf
   ```
3. Save changes

**Why UUID is better:**
- Guarantees targeting the exact device
- Works even if you rename the device
- Prevents conflicts with same-named devices

#### Solution 6: Cloud vs Local Deployment

**IMPORTANT:** Client playback ONLY works on your **local network**.

**This WORKS:**
- ✅ Popcorn running on Unraid (local server)
- ✅ Popcorn in Docker on home PC/NAS
- ✅ Popcorn running natively on local machine

**This DOES NOT WORK:**
- ❌ Popcorn hosted in cloud (Replit, Heroku, DigitalOcean, etc.)
- ❌ Accessing Popcorn over VPN from outside network

**Why:** Cloud-hosted apps cannot reach your home network's private IP addresses where your Roku/clients live. They can connect to your Plex server (if public), but not to local playback devices.

**Alternative:** Use **Web Player mode** instead:
1. Go to **Profile** → **Playback Settings**
2. Change **Playback Mode** to **"Web Player"**
3. Movies will open in browser instead of pushing to device
4. Works from anywhere (cloud or local)

#### Quick Diagnostic Checklist

Run through this checklist:

- [ ] **PLEX_URL** uses local IP (`http://192.168.x.x:32400` or `http://10.0.x.x:32400`)
- [ ] Docker network mode is **Host** (not Bridge) for both Plex and Popcorn
- [ ] Whitelisted `config.claspws.tv` if using Pi-hole/ad-blocker
- [ ] **Plex app is open** on target device right now
- [ ] Target device signed into **same Plex account** as server
- [ ] Popcorn running on **local network** (not cloud)
- [ ] Using device **UUID** (not just name) in Profile settings

**Test your setup:**
```bash
# This should return XML with your devices listed
curl "http://YOUR_LOCAL_PLEX_IP:32400/clients?X-Plex-Token=YOUR_TOKEN"
```

If still empty, check Plex server logs for GDM/discovery errors.

#### Still Not Working? Use Web Player Mode

If client discovery continues to fail:

1. **Profile** → **Playback Settings**
2. Change to **"Web Player"** mode
3. Movies open in browser (works everywhere)
4. No client discovery needed

### Problem: Movies Not Playing (Deep Link Issues)

**Symptoms:** Clicking movies doesn't open Plex

**Solutions:**
1. **On mobile devices:**
   - Install the official Plex app
   - Sign in with your Plex account
   - Grant browser permission to open apps

2. **On desktop:**
   - Install Plex Desktop app or Plex Media Player
   - Sign in with your Plex account
   - Use the web fallback link if app doesn't open

3. **On Roku/TV:**
   - Use second-screen control (browse on phone, cast to TV)
   - Open movie in Plex app/web
   - Select your Roku/TV as the playback device

### Problem: No Channels Showing

**Symptoms:** "No Channels Available" message

**Solutions:**
1. Check if Plex library has movies:
   - Open Plex and verify movies exist
   - Movies must have genre tags

2. Trigger a sync:
   - Visit: `http://localhost:5000/sync`
   - Wait for sync to complete (check logs)

3. Check application logs:
   ```bash
   docker logs popcorn
   ```
   Look for errors during movie sync

### Problem: Movies Missing Genre Tags

**Symptoms:** Movies don't appear in genre channels

**Solutions:**
1. In Plex, edit the movie metadata
2. Add appropriate genre tags
3. Sync Popcorn: `http://localhost:5000/sync`
4. Movies will appear in matching genre channels

### Problem: Port 5000 Already in Use

**Symptoms:** "Address already in use" error

**Solutions:**
1. Use a different port:
   ```bash
   docker run -p 8080:5000 ... popcorn
   ```
   Access at `http://localhost:8080`

2. Or stop the conflicting service:
   ```bash
   # Find what's using port 5000
   lsof -i :5000
   # Stop that process
   ```

### Problem: Container Won't Start

**Symptoms:** Docker container exits immediately

**Solutions:**
1. Check logs:
   ```bash
   docker logs popcorn
   ```

2. Common issues:
   - Missing required environment variables
   - Invalid Plex credentials
   - Port conflicts

3. Run interactively to debug:
   ```bash
   docker run -it --rm -p 5000:5000 \
     -e SESSION_SECRET="test" \
     popcorn
   ```

### Problem: Schedule Not Updating

**Symptoms:** Same movies showing repeatedly

**Solutions:**
1. Check reshuffle frequency in Settings
2. Manually trigger reshuffle:
   - Go to Settings
   - Click "Reshuffle Now"
3. Or restart the application:
   ```bash
   docker restart popcorn
   ```

### Problem: Database Issues

**Symptoms:** Errors about database or SQLite

**Solutions:**
1. Stop the container:
   ```bash
   docker stop popcorn
   ```

2. Delete the database (will resync from Plex):
   ```bash
   docker exec popcorn rm -f popcorn.db
   ```

3. Restart and let it rebuild:
   ```bash
   docker start popcorn
   ```

### Getting More Help

If you're still experiencing issues:

1. **Check application logs:**
   ```bash
   docker logs -f popcorn
   ```

2. **Verify configuration:**
   ```bash
   docker exec popcorn env | grep PLEX
   ```

3. **Test Plex connection manually:**
   ```bash
   curl "http://YOUR-PLEX-URL:32400/library/sections?X-Plex-Token=YOUR-TOKEN"
   ```

4. **Restart everything:**
   ```bash
   docker restart popcorn
   ```

---

## Tips for Best Experience

1. **Keep Plex metadata accurate** - Proper genres and ratings help channel organization
2. **Sync regularly** - Run sync after adding new movies to your library
3. **Use reshuffle** - Change schedules weekly for variety
4. **Bookmark the guide** - Set as your homepage for quick access
5. **Use on multiple devices** - Browse on phone, cast to TV

---

## Advanced Configuration

### Using Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'
services:
  popcorn:
    build: .
    container_name: popcorn
    ports:
      - "5000:5000"
    environment:
      - SESSION_SECRET=your-secret-key-here
      - PLEX_URL=http://192.168.1.100:32400
      - PLEX_TOKEN=your-plex-token
      - PLEX_CLIENT=Roku Living Room
    volumes:
      - popcorn-data:/app
    restart: unless-stopped

volumes:
  popcorn-data:
```

Run with:
```bash
docker-compose up -d
```

### Reverse Proxy Setup (Nginx)

```nginx
location /popcorn/ {
    proxy_pass http://localhost:5000/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

---

## Admin Guide

This section covers features available only to administrator accounts.

### User Management

Admins can manage user accounts and create invitation codes.

**Accessing User Management:**
1. Open the hamburger menu
2. Click "Settings" (admin only)
3. Navigate to "User Management" section

**Creating Invitation Codes:**
1. Go to Settings → User Management
2. Click "Create Invitation Code"
3. Optionally set an email and expiration date
4. Share the code with new users
5. Users register at `/register?code=YOUR_CODE`

**Managing Users:**
- View all registered users
- Toggle admin privileges
- Activate/deactivate accounts
- View registration and login history

**User Roles:**
- **Admin** - Full access to settings, user management, and updates
- **User** - Access to guide, channels, profile, and theme customization

### Auto-Update System

**For Native Installations (Non-Docker):**

Popcorn includes an intelligent auto-update system that checks GitHub for new releases:

**Checking for Updates:**
1. Go to Settings
2. Scroll to "Updates" section
3. Click "Check for Updates"
4. System shows current version and available updates

**Applying Updates:**
1. When update is available, click "Update Now"
2. Watch real-time progress:
   - Database backup created automatically
   - Latest code downloaded from GitHub
   - Dependencies updated
   - Database migrations applied
3. On success: Restart the application
4. On failure: Automatic rollback to backup

**Update Features:**
- Automatic database backup before updates
- Real-time progress streaming
- Migration tracking (no duplicate migrations)
- Automatic rollback on failure
- Version history tracking

**For Docker Installations:**

Docker containers are updated differently:

1. Go to Settings → Updates
2. Click "Check for Updates"
3. If available, message shows: "Running in Docker: Please pull the latest image to update"
4. Follow Docker update instructions (see Docker section above)

**Update Source:**
- Updates are checked from: `https://github.com/netpersona/Popcorn`
- Configurable in database settings
- Checks `/releases/latest` for new versions

### Settings Configuration

**Plex Connection:**
- Configure Plex URL and token
- Test connection to verify credentials
- View available Plex clients for playback

**Schedule Management:**
- Set reshuffle frequency (daily, weekly, monthly)
- Manually trigger schedule regeneration
- View last reshuffle date

**System Information:**
- View current version and commit
- Check for updates
- Review deployment environment (Docker/Native)

### Managing Custom Themes

**Theme Permissions:**
- All users can upload and use custom themes
- Admins can mark custom themes as "public"
- Public themes are available to all users

**Making Themes Public:**
1. Navigate to Profile
2. Find the custom theme
3. (Admin only) Click "Make Public"
4. Theme now appears for all users

**Theme Management:**
- Monitor uploaded custom themes
- Delete inappropriate themes
- Set default theme for new users

### Security Best Practices

1. **Change default passwords immediately** - Update `admin` and `demo` accounts on first login
2. **Keep SESSION_SECRET secure** - Never share this value
3. **Protect ADMIN_SETUP_TOKEN** - Used for first admin registration only
4. **Regularly update** - Apply security patches when available
5. **Monitor user activity** - Review login history
6. **Use strong passwords** - Enforce for local auth users (minimum 4 characters)
7. **Limit admin access** - Only trusted users should have admin privileges
8. **Review security warnings** - Address any security banners immediately

**Default Account Security:**
- Default accounts (`admin`/`admin`, `demo`/`demo`) are created automatically for quick setup
- These accounts display security warnings until passwords are changed
- **Production deployments**: Change or disable default accounts before public access
- **Demo deployments**: Acceptable for temporary testing, but still change passwords
- Security warnings persist across sessions until passwords are updated

### Backup and Maintenance

**Database Backups:**
- Auto-update system creates backups before updates
- Located in `/backups` directory
- Timestamped format: `popcorn_YYYYMMDD_HHMMSS.db`

**Manual Backup:**
```bash
# Docker
docker cp popcorn:/app/popcorn.db ./backup-$(date +%Y%m%d).db

# Direct Installation
cp popcorn.db backup-$(date +%Y%m%d).db
```

**Restore from Backup:**
```bash
# Docker
docker stop popcorn
docker cp ./backup.db popcorn:/app/popcorn.db
docker start popcorn

# Direct Installation
cp backup.db popcorn.db
python app.py
```

### Migration Management

Popcorn automatically tracks and applies database migrations:

**Migration System:**
- Migrations stored in `/migrations` directory
- Tracked in `migration_history` table
- Only new migrations are applied
- Prevents duplicate execution

**Viewing Migrations:**
```bash
# Docker
docker exec popcorn ls -l /app/migrations

# Direct Installation
ls -l migrations/
```

**Migration History:**
All applied migrations are recorded with timestamps to prevent re-execution.

### Troubleshooting Admin Issues

**Problem: Can't Access Admin Features**

**Solutions:**
1. Verify your account has admin privileges
2. Check User Management to see your role
3. Contact the original admin to grant permissions

**Problem: Update Failed**

**Solutions:**
1. Check application logs for errors
2. Database backup is automatically restored
3. Verify GitHub connectivity
4. Check available disk space
5. Try manual update via git pull

**Problem: Users Can't Register**

**Solutions:**
1. Verify invitation code is valid and not expired
2. Check code is active in User Management
3. Ensure ADMIN_SETUP_TOKEN is secure (first admin only)
4. Check application logs for registration errors

---

Enjoy your cable TV experience with Popcorn! 🍿📺

# 🍿 Popcorn - User Guide

Welcome to Popcorn! This comprehensive guide will help you set up and enjoy your cable-style movie scheduling system for Plex.

---

## 📖 Table of Contents

- [Overview](#-overview)
- [Prerequisites](#-prerequisites)
- [Getting Your Plex Credentials](#-getting-your-plex-credentials)
- [Installation](#-installation)
  - [Unraid](#unraid)
  - [Docker](#docker-recommended)
  - [Direct Python](#direct-python-installation)
- [First-Time Setup](#-first-time-setup)
- [Using Popcorn](#-using-popcorn)
- [User Features](#-user-features)
- [Admin Guide](#-admin-guide)
- [Troubleshooting](#-troubleshooting)

---

## 🎬 Overview

Popcorn transforms your Plex media library into a nostalgic cable TV experience with:

- **📺 Genre-Based Channels** – Action, Comedy, Drama, Horror, and more
- **🎃 Seasonal Channels** – Halloween Horror, Christmas Classics, holiday programming
- **⏰ 24-Hour Schedules** – Movies playing back-to-back around the clock
- **📱 TV Guide Interface** – Browse what's "on air" like traditional cable

---

## ✅ Prerequisites

Before installing Popcorn, ensure you have:

- ✅ **Plex Media Server** running with a movie library
- ✅ **Docker** ([Install Docker](https://docs.docker.com/get-docker/)) OR **Python 3.11+**
- ✅ **Network access** to your Plex server
- ✅ **Plex authentication token** (instructions below)

---

## 🔑 Getting Your Plex Credentials

### Step 1: Find Your Plex URL

Your Plex URL is typically:

```bash
# Local network (recommended)
http://192.168.1.100:32400

# Remote access (for cloud deployments)
https://YOUR-SERVER-ID.plex.direct:32400
```

**To find your server IP:**
1. Open Plex Web App
2. Go to **Settings → Network**
3. Note the IP address shown

### Step 2: Get Your Plex Token

#### Method 1: Plex Web App (Easiest)

1. Open any movie in Plex Web App
2. Click **three dots (⋮)** → **"Get Info"**
3. Click **"View XML"**
4. Look in the URL bar for `X-Plex-Token=XXXXX`
5. Copy everything after the equals sign

#### Method 2: Browser Developer Tools

1. Open Plex Web App in your browser
2. Press **F12** to open Developer Tools
3. Go to **Console** tab
4. Type: `localStorage.getItem('myPlexAccessToken')`
5. Press Enter and copy the token (without quotes)

#### Method 3: Plex API

1. Sign in at [plex.tv/sign-in](https://www.plex.tv/sign-in)
2. Navigate to: [plex.tv/devices.xml](https://plex.tv/devices.xml)
3. Find your server and look for `token="YOUR_TOKEN"`

📖 [Official Plex Documentation](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)

---

## 🚀 Installation

### Unraid

For detailed Unraid installation, see **[UNRAID_SETUP.md](UNRAID_SETUP.md)** which covers:
- Installing from Community Applications
- Manual template installation
- Unraid-specific configuration
- Troubleshooting on Unraid

### Docker (Recommended)

Docker handles all dependencies automatically and ensures consistent deployment.

#### Quick Start with Docker Compose

1. **Download** `docker-compose.yml` from the repository
2. **Edit** environment variables:
   ```yaml
   SESSION_SECRET: "your-random-secret-here"  # Generate with: openssl rand -hex 32
   PLEX_URL: "http://192.168.1.100:32400"
   PLEX_TOKEN: "your-plex-token"
   ```
3. **Launch**:
   ```bash
   docker-compose up -d
   ```

#### Manual Docker Run

```bash
docker run -d \
  --name popcorn \
  -p 5000:5000 \
  -v ./popcorn-data:/data \
  -e SESSION_SECRET="$(openssl rand -hex 32)" \
  -e PLEX_URL="http://192.168.1.100:32400" \
  -e PLEX_TOKEN="your-plex-token" \
  --restart unless-stopped \
  netpersona/popcorn:latest
```

#### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SESSION_SECRET` | **Yes** | Random string for session encryption |
| `PLEX_URL` | **Yes** | Your Plex server URL |
| `PLEX_TOKEN` | **Yes** | Plex authentication token |
| `DATA_DIR` | No | Data directory (default: `/data` in Docker) |

#### Access Popcorn

```bash
# Locally
http://localhost:5000

# From another device
http://YOUR-SERVER-IP:5000
```

#### Docker Management

```bash
# View logs
docker logs popcorn

# Stop/Start
docker stop popcorn
docker start popcorn

# Restart
docker restart popcorn
```

#### Updating Docker Installation

```bash
# Pull latest image
docker-compose pull

# Restart with new image
docker-compose up -d

# Or manually
docker pull netpersona/popcorn:latest
docker stop popcorn
docker rm popcorn
# Run with same docker run command but :latest tag
```

> **Note:** Your database and settings persist in the volume, so updates are safe.

---

### Direct Python Installation

For non-Docker deployments:

#### Step 1: Install Dependencies

```bash
# Verify Python version
python --version  # Should be 3.11+

# Install requirements
pip install -r requirements.txt
```

#### Step 2: Configure Environment

**Linux/Mac:**
```bash
export SESSION_SECRET="your-random-secret-key"
export PLEX_URL="http://192.168.1.100:32400"
export PLEX_TOKEN="your-plex-token"
```

**Windows (PowerShell):**
```powershell
$env:SESSION_SECRET="your-random-secret-key"
$env:PLEX_URL="http://192.168.1.100:32400"
$env:PLEX_TOKEN="your-plex-token"
```

**Or create a `.env` file:**
```env
SESSION_SECRET=your-random-secret-key
PLEX_URL=http://192.168.1.100:32400
PLEX_TOKEN=your-plex-token
```

#### Step 3: Run the Application

```bash
python app.py
```

Access at `http://localhost:5000`

---

## 🎯 First-Time Setup

### Default Demo Accounts

Popcorn creates two accounts on first startup for quick evaluation:

| Username | Password | Role | Purpose |
|----------|----------|------|---------|
| `admin` | `admin` | Administrator | Full access to settings and management |
| `demo` | `demo` | User | Standard user access for demonstration |

> **⚠️ Security Warning:** These accounts use default passwords. You'll see a security warning banner until changed.

### Initial Login

1. **Access Popcorn** at `http://localhost:5000`
2. **Login** with:
   - Admin: `admin` / `admin`
   - Demo: `demo` / `demo`
3. **Security Warning Appears:**
   ```
   ⚠️ SECURITY WARNING: You are using a default password!
   Change your password immediately in your profile settings.
   ```

### Change Your Password

1. Click the warning banner or navigate to **Profile**
2. Scroll to **"Change Password"** section
3. Fill in the form:
   - Current Password
   - New Password (minimum 4 characters)
   - Confirm New Password
4. Click **"Change Password"**
5. Security warning disappears automatically

### Automatic Plex Sync

Once configured, Popcorn automatically:
1. Connects to your Plex server
2. Scans your movie library
3. Generates genre-based channels
4. Creates 24-hour schedules

---

## 📺 Using Popcorn

### TV Guide View

The main interface mimics traditional cable TV guides:

**Features:**
- **Channel List** (left) – All available channels
- **Time Grid** (top) – 24 hours in 30-minute increments
- **Program Tiles** – Movies playing at each time slot
- **Current Time Indicator** – Orange line showing "now"
- **Jump to Now** – Button to scroll to current time

**Navigation:**
- Scroll horizontally to view different times
- Scroll vertically to browse channels
- Click any program tile to open in Plex

### Channels View

Browse channels individually:

1. See all channels in card layout
2. View what's currently playing
3. Click a channel for full 24-hour schedule

### Playing Movies

**Desktop/Mobile:**
1. Click any movie in the guide
2. New tab opens launching Plex
3. If Plex app installed, movie opens
4. Otherwise, redirects to Plex Web for casting

**TV/Streaming Devices:**
1. Browse Popcorn on phone/tablet/computer
2. Click a movie to open in Plex
3. Cast from Plex to your Roku/TV
4. Movie plays through Plex

### Syncing Your Library

Update Popcorn with new movies:

1. Click **menu icon** → **"Sync"**
2. Or visit: `http://localhost:5000/sync`
3. Popcorn scans Plex for new movies
4. New movies added to appropriate channels
5. Schedules regenerate automatically

---

## 🎨 User Features

### Theme Customization

Popcorn includes 11 built-in themes plus custom theme support:

**Built-in Themes:**
- **Plex** – Classic dark theme (default)
- **Halloween** – Orange and black with coral accents
- **Hell-o-ween** – Dark and fiery with red accents
- **Pastel Dream** – Soft pastel colors
- **Plastic** – Modern gradient design
- **Popcorn** – Warm theater-inspired colors
- **Midnight Harmony** – Deep blues and purples
- **Ichor Wine** – Rich burgundy tones
- **Vampirism** – Dark purple vampire aesthetic
- **Lavender** – Soft purple theme
- **Starry Night** – Dark blue night sky theme

**Change Your Theme:**
1. Navigate to **Profile** page
2. Find **"Theme Selection"** section
3. Choose from dropdown
4. Click **"Save Theme"**
5. Theme applies instantly

### Creating Custom Themes

Upload your own themes in JSON format:

1. Go to **Profile** page
2. Click **"Upload Theme"** button
3. Select JSON file (max 50KB)
4. Theme appears with ⭐ star icon
5. Select and save to apply

**Theme Format:**
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
- All 10 color properties required
- Valid JSON format
- File size under 50KB
- Valid CSS color values (hex, rgb, rgba)

**Managing Themes:**
- Custom themes show with ⭐ star icon
- Click trash icon to delete your themes
- Admins can mark themes public for all users

### Playback Settings

Configure how movies play:

**Playback Mode:**
- **Web Player** (default) – Opens in browser
- **Client Playback** – Sends to Plex device (Roku, Apple TV, etc.)

**Time Offset:**
- **Enabled** (default) – Start at current "live" position
- **Disabled** – Always start from beginning

Access via **Profile** page.

### User Profile

Your profile includes:

- **Account Information** – Username, email, avatar
- **Theme Selection** – Choose or upload themes
- **Playback Settings** – Configure movie playback
- **Password Management** – Change your password

#### Changing Your Password

1. Navigate to **Profile** (via menu)
2. Scroll to **"Account Information"**
3. Find **"Change Password"** section
4. Fill in the form:
   - Current Password
   - New Password (minimum 4 characters)
   - Confirm New Password
5. Click **"Change Password"**

**Password Requirements:**
- Minimum 4 characters
- Must match confirmation
- Current password must be correct

**Common Errors:**
- "Current password is incorrect" – Verify existing password
- "New passwords do not match" – Ensure both fields match
- "Password must be at least 4 characters" – Use longer password

---

## 👑 Admin Guide

Features available only to administrator accounts.

### User Management

**Accessing User Management:**
1. Open hamburger menu
2. Click **"Settings"** (admin only)
3. Navigate to **"User Management"** section

**Creating Invitation Codes:**
1. Go to **Settings → User Management**
2. Click **"Create Invitation Code"**
3. Optionally set email and expiration
4. Share code with new users
5. Users register at `/register?code=YOUR_CODE`

**Managing Users:**
- View all registered users
- Toggle admin privileges
- Activate/deactivate accounts
- View registration and login history

**User Roles:**
- **Admin** – Full access to settings, management, updates
- **User** – Access to guide, channels, profile, themes

### Settings Configuration

**Plex Connection:**
- Configure Plex URL and token
- Test connection to verify credentials
- View available Plex clients

**Schedule Management:**
- Set reshuffle frequency (daily/weekly/monthly)
- Manually trigger schedule regeneration
- View last reshuffle date

**Holiday Channels:**

Automatically activated during their seasons:

| Channel | Active Period | Content | Rating |
|---------|--------------|---------|--------|
| Cozy Halloween 👻 | Sep-Nov | Family Halloween | G, PG, PG-13 |
| Scary Halloween 💀 | Sep-Nov | Horror movies | PG-13, R |
| Christmas 🎄 | Nov-Jan | Holiday movies | All |

**System Information:**
- View current version and commit
- Check for updates
- Review deployment environment

### Auto-Update System

**For Native Installations:**

Popcorn includes intelligent auto-updates via GitHub:

**Checking for Updates:**
1. Go to **Settings**
2. Scroll to **"Updates"** section
3. Click **"Check for Updates"**
4. View current vs. available versions

**Applying Updates:**
1. When available, click **"Update Now"**
2. Watch real-time progress:
   - Database backup created automatically
   - Latest code downloaded from GitHub
   - Dependencies updated
   - Database migrations applied
3. On success: Restart application
4. On failure: Automatic rollback to backup

**For Docker Installations:**
1. **Settings → Updates → "Check for Updates"**
2. Message shows: "Running in Docker: Please pull the latest image"
3. Follow Docker update instructions

### Managing Custom Themes

**Theme Permissions:**
- All users can upload custom themes
- Admins can mark themes as "public"
- Public themes available to all users

**Making Themes Public:**
1. Navigate to **Profile**
2. Find custom theme
3. (Admin only) Click **"Make Public"**
4. Theme now available for all users

### Security Best Practices

1. **Change default passwords** – Update `admin` and `demo` accounts immediately
2. **Secure SESSION_SECRET** – Never share this value
3. **Protect ADMIN_SETUP_TOKEN** – First admin registration only
4. **Regular updates** – Apply security patches when available
5. **Monitor user activity** – Review login history
6. **Strong passwords** – Enforce minimum 4 characters
7. **Limit admin access** – Only trusted users
8. **Address security warnings** – Don't ignore warning banners

### Backup and Maintenance

**Database Backups:**
- Auto-update creates backups before updates
- Located in `/backups` directory
- Format: `popcorn_YYYYMMDD_HHMMSS.db`

**Manual Backup:**
```bash
# Docker
docker cp popcorn:/data/popcorn.db ./backup-$(date +%Y%m%d).db

# Direct Installation
cp popcorn.db backup-$(date +%Y%m%d).db
```

**Restore from Backup:**
```bash
# Docker
docker stop popcorn
docker cp ./backup.db popcorn:/data/popcorn.db
docker start popcorn

# Direct Installation
cp backup.db popcorn.db
python app.py
```

---

## 🔧 Troubleshooting

### "Plex API not available" Error

**Symptoms:** App works but no movies, empty channels

**Solutions:**

1. **Verify PLEX_URL:**
   ```bash
   curl http://YOUR-PLEX-URL:32400/identity
   ```
   Should return XML with server info

2. **Verify PLEX_TOKEN:**
   ```bash
   curl "http://YOUR-PLEX-URL:32400/library/sections?X-Plex-Token=YOUR-TOKEN"
   ```
   Should return your libraries

3. **Check network connectivity:**
   - Ensure Popcorn can reach Plex server
   - Docker: Verify container communication
   - Check firewall rules

4. **Restart with correct variables:**
   ```bash
   docker restart popcorn
   docker logs popcorn
   ```

---

### "No Plex Clients Found" / Client Playback Not Working

**Symptoms:**
- Error: "No Plex clients found. Make sure a Plex player is running..."
- Error: "Client not found. Available: []"
- Playback fails despite device visible in Plex

**Root Cause:** Popcorn cannot discover your Plex playback devices.

#### Solution 1: Use Local PLEX_URL ⭐ Most Common Fix

**The Problem:** Public/remote URLs prevent local client discovery.

```bash
# ✅ CORRECT - Local IP
PLEX_URL=http://192.168.1.100:32400
PLEX_URL=http://10.0.0.25:32400

# ❌ WRONG - Public/remote URLs
PLEX_URL=http://66.241.174.242:19019
PLEX_URL=https://plex.mydomain.com:32400
```

**Why:** Plex `/clients` endpoint only discovers local network devices.

**Find Your Local IP:**
```bash
# Linux
ip addr

# Windows
ipconfig

# Look for 192.168.x.x or 10.0.x.x
```

**Test Discovery:**
```bash
curl "http://YOUR_LOCAL_IP:32400/clients?X-Plex-Token=YOUR_TOKEN"
```

If returns `<MediaContainer size="0">`, your URL is wrong.

#### Solution 2: Enable Host Network Mode

**The Problem:** Bridge mode blocks GDM discovery protocol.

**For Docker:**
```bash
docker run -d --name popcorn \
  --network host \
  -e PLEX_URL="http://192.168.1.100:32400" \
  -e PLEX_TOKEN="your-token" \
  netpersona/popcorn:latest
```

**For Docker Compose:**
```yaml
services:
  popcorn:
    network_mode: host
```

**For Unraid:**
1. Edit container
2. Change **Network Type** from `Bridge` → `Host`
3. Remove port mappings
4. Save and restart

**Why:** Bridge mode isolates containers from multicast broadcasts.

#### Solution 3: Whitelist Plex Domain (Pi-hole Users)

**If using Pi-hole or DNS ad-blockers:**

Whitelist: `config.claspws.tv`

**In Pi-hole:**
1. Go to **Whitelist**
2. Add: `config.claspws.tv`
3. Save
4. Restart Plex app on device

**Why:** This domain is Plex's companion app service for device discovery.

#### Solution 4: Plex App Must Be Open

**Requirements:**
- ✅ Plex app **must be open** on device
- ✅ Can be on home screen (doesn't need to play)
- ❌ Won't work if app is closed

**Test:**
```bash
# With Plex app open on device, this should show devices
curl "http://YOUR_LOCAL_IP:32400/clients?X-Plex-Token=YOUR_TOKEN"
```

#### Solution 5: Use Device UUID

**Get Device UUID:**

Visit: `https://plex.tv/api/resources.xml?X-Plex-Token=YOUR_TOKEN`

Find your device:
```xml
<Device name="Roku Streaming Stick 4K" 
        clientIdentifier="6d89441adccb7d3506b90954cddc17cf" />
```

**In Popcorn:**
1. **Profile → Playback Settings**
2. Set **Plex Client ID** to UUID:
   ```
   6d89441adccb7d3506b90954cddc17cf
   ```
3. Save

**Why:** UUID guarantees targeting exact device.

#### Solution 6: Local Network Only

**Client playback ONLY works locally:**

✅ **Works:**
- Unraid/Docker on home server
- PC/NAS on local network
- Native installation at home

❌ **Doesn't Work:**
- Cloud hosting (Heroku, DigitalOcean)
- Accessing over VPN from outside

**Why:** Cloud apps can't reach private home network IPs.

**Alternative:** Use **Web Player mode** instead:
1. **Profile → Playback Settings**
2. Change to **"Web Player"**
3. Works everywhere (cloud or local)

#### Quick Checklist

- [ ] `PLEX_URL` uses local IP (`http://192.168.x.x:32400`)
- [ ] Docker network mode is **Host** (both Plex and Popcorn)
- [ ] Whitelisted `config.claspws.tv` (if using Pi-hole)
- [ ] Plex app is **open** on device right now
- [ ] Device signed into **same Plex account**
- [ ] Running on **local network** (not cloud)
- [ ] Using device **UUID** (not just name)

**Test Command:**
```bash
curl "http://YOUR_LOCAL_IP:32400/clients?X-Plex-Token=YOUR_TOKEN"
```

**Still Not Working?**
Switch to **Web Player mode** (works everywhere).

---

### No Channels Showing

**Symptoms:** "No Channels Available" message

**Solutions:**

1. **Verify Plex has movies:**
   - Open Plex and confirm movies exist
   - Movies must have genre tags

2. **Trigger sync:**
   - Visit: `http://localhost:5000/sync`
   - Wait for completion (check logs)

3. **Check logs:**
   ```bash
   docker logs popcorn
   ```
   Look for sync errors

### Movies Missing Genre Tags

**Symptoms:** Movies don't appear in channels

**Solutions:**
1. Edit movie metadata in Plex
2. Add appropriate genre tags
3. Sync Popcorn: `http://localhost:5000/sync`
4. Movies appear in matching channels

### Port 5000 Already in Use

**Symptoms:** "Address already in use" error

**Solutions:**

1. **Use different port:**
   ```bash
   docker run -p 8080:5000 ... netpersona/popcorn:latest
   ```
   Access at `http://localhost:8080`

2. **Find conflicting service:**
   ```bash
   lsof -i :5000
   ```

### Container Won't Start

**Symptoms:** Docker container exits immediately

**Solutions:**

1. **Check logs:**
   ```bash
   docker logs popcorn
   ```

2. **Common issues:**
   - Missing environment variables
   - Invalid Plex credentials
   - Port conflicts

3. **Debug interactively:**
   ```bash
   docker run -it --rm -p 5000:5000 \
     -e SESSION_SECRET="test" \
     netpersona/popcorn:latest
   ```

### Schedule Not Updating

**Symptoms:** Same movies showing repeatedly

**Solutions:**

1. Check reshuffle frequency in **Settings**
2. Manually trigger: **Settings → "Reshuffle Now"**
3. Restart application:
   ```bash
   docker restart popcorn
   ```

---

## 💡 Tips for Best Experience

1. **Accurate Plex metadata** – Proper genres help channel organization
2. **Regular syncing** – Run sync after adding new movies
3. **Weekly reshuffles** – Change schedules for variety
4. **Bookmark the guide** – Quick access to your channels
5. **Multi-device usage** – Browse on phone, cast to TV

---

## 🆘 Getting More Help

Still experiencing issues?

1. **Check logs:**
   ```bash
   docker logs -f popcorn
   ```

2. **Verify configuration:**
   ```bash
   docker exec popcorn env | grep PLEX
   ```

3. **Test Plex connection:**
   ```bash
   curl "http://YOUR-PLEX-URL:32400/library/sections?X-Plex-Token=YOUR-TOKEN"
   ```

4. **Restart everything:**
   ```bash
   docker restart popcorn
   ```

5. **Community Support:**
   - [GitHub Issues](https://github.com/netpersona/Popcorn/issues)
   - [GitHub Discussions](https://github.com/netpersona/Popcorn/discussions)

---

**Enjoy your cable TV experience! 🍿📺**

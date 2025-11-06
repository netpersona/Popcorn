<div align="center">

<img width="150" height="150" alt="Popcorn Logo" src="https://github.com/user-attachments/assets/fd24f2e3-0c8f-4171-8c99-85a6f99691bd" />

# Popcorn

**Transform your Plex library into a nostalgic cable TV experience**

An old-school TV guide for discovering, scheduling, and sharing movies with friends and family.

![License](https://img.shields.io/github/license/netpersona/Popcorn)
![Docker Pulls](https://img.shields.io/docker/pulls/netpersona/popcorn)
![GitHub Stars](https://img.shields.io/github/stars/netpersona/Popcorn)

</div>

---

## 📺 Screenshots

<img width="2770" alt="TV Guide Interface" src="https://github.com/user-attachments/assets/4d32401c-18fb-4b32-9462-a8a7ebe5d863" />

*Browse channels with a time-based program grid—just like traditional cable television*

<img width="1331" alt="Movie Details" src="https://github.com/user-attachments/assets/b032a261-fe29-4161-bad7-ef70ce9188be" />

*Each movie has its own information pop-up to help you decide what to watch*

<img width="1362" alt="Custom Themes" src="https://github.com/user-attachments/assets/4bbe4acc-b29e-4687-8cfc-a682a40bf85a" />

*Create and share your own custom themes for a personalized experience*

---

## ✨ What is Popcorn?

Popcorn brings back the magic of flipping through cable TV channels, but with your own Plex movie collection. Instead of browsing endless lists, you get a real TV guide showing what's "on" right now across different genre channels.

**Perfect for:**
- Movie nights when you can't decide what to watch
- Recreating the nostalgia of old-school cable TV
- Discovering forgotten movies in your collection
- Family viewing with kid-friendly scheduled content

---

## 🎯 Key Features

### 📺 Automatic Channel Generation
- **Genre Channels**: Action, Comedy, Drama, Horror, Sci-Fi, and more
- **Holiday Channels**: Halloween spooky movies, Christmas classics, seasonal favorites
- **Smart Scheduling**: 24-hour programming based on movie lengths

### 🕹️ Classic TV Guide Interface
- Time-based program grid just like old cable boxes
- Browse what's playing "now" across all channels
- Mobile-responsive design that works on phones, tablets, and TVs

### 🎮 Multi-Device Playback
- Play movies on any Plex device (Roku, Apple TV, smart TVs, etc.)
- Save favorite devices for quick access
- Automatic device discovery

### 🎨 Customizable Experience
- Multiple themes (Plex-style, Halloween, Christmas, custom)
- Optional retro effects (CRT monitor look, film grain)
- Classic cable channel numbers (Horror = Channel 666)

### 📊 Watch History & Stats
- Track what you've watched
- See viewing statistics
- "Watched" badges on movies you've seen

### 🔐 User Management
- Plex account integration (OAuth)
- Local username/password accounts
- Admin controls for managing users
- Invite code system for new users

---

## 🚀 Quick Start

### Option 1: Docker Compose (Easiest - Recommended!)

Everything is pre-configured. Just two steps:

1. **Download the `docker-compose.yml` file**

2. **Edit these two lines:**
   ```yaml
   SESSION_SECRET: "change-this-to-random-string"  # Generate with: openssl rand -hex 32
   PLEX_URL: "http://192.168.1.100:32400"         # Optional: Your Plex server
   PLEX_TOKEN: "your-plex-token"                   # Optional: Your Plex token
   ```

3. **Run it:**
   ```bash
   docker-compose up -d
   ```

That's it! Access at `http://your-server-ip:5000`

Your data automatically saves in `./popcorn-data` and survives updates.

**Updating:** `docker-compose pull && docker-compose up -d`

---

### Option 2: Unraid Users

1. Open **Community Applications**
2. Search for **"Popcorn"**
3. Fill in your `SESSION_SECRET` and Plex settings
4. Click **Apply**

All volume mappings are pre-configured. See [UNRAID_SETUP.md](UNRAID_SETUP.md) for details.

---

### Option 3: Manual Docker Run

For command-line enthusiasts:

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

⚠️ **Critical:** The `-v ./popcorn-data:/data` line saves your database. Without it, you'll lose everything when updating!

---

## ⚙️ Configuration

### Required Settings

| Setting | Required? | What It Does |
|---------|-----------|--------------|
| `SESSION_SECRET` | **Yes** | Encrypts your login sessions (keep this secret!) |
| `PLEX_URL` | Optional* | Where your Plex server lives (e.g., `http://192.168.1.100:32400`) |
| `PLEX_TOKEN` | Optional* | Your Plex authentication token |

*You can set these in the web interface after logging in if you prefer.

### Finding Your Plex Token

1. Open Plex Web App and play any movie
2. Click the **ⓘ** (info) icon
3. Click **"View XML"**
4. Look for `X-Plex-Token=` in the browser URL
5. Copy everything after the `=` sign

[Official Plex guide](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)

---

## 🎬 First-Time Setup

1. **Open your browser** to `http://your-server-ip:5000`

2. **Login with default credentials:**
   - Username: `admin`
   - Password: `admin`

3. **⚠️ CHANGE THE PASSWORD IMMEDIATELY!**
   - You'll see a warning banner
   - Go to your profile settings

4. **Connect to Plex** (if you didn't set environment variables):
   - Click **Admin** → **Settings**
   - Enter your Plex URL and Token
   - Click **Save**

5. **Generate your first schedule:**
   - Go to the home page
   - Click **"Generate Schedule"**
   - Wait a few moments while Popcorn analyzes your movies

6. **Enjoy!** Browse channels and start watching.

---

## 🖥️ Local Development

Want to contribute or run it without Docker?

```bash
# Clone the repository
git clone https://github.com/netpersona/Popcorn.git
cd Popcorn

# Install Python dependencies
pip install -r requirements.txt

# Set up environment
export SESSION_SECRET="$(openssl rand -hex 32)"
export PLEX_URL="http://192.168.1.100:32400"
export PLEX_TOKEN="your-token-here"

# Run the app
python app.py
```

Access at `http://localhost:5000`

---

## 🏗️ How It Works (Technical Overview)

### The Magic Behind the Scenes

**Schedule Generation:**
1. Popcorn connects to your Plex server and fetches all movies
2. Movies are automatically sorted into genre channels (Action, Comedy, etc.)
3. A 24-hour schedule is built by filling time slots based on movie lengths
4. Holiday channels use smart keyword matching (e.g., "Christmas" titles for holiday channel)

**TV Guide Interface:**
- Server-side rendering with Jinja2 templates keeps things fast
- Responsive design adapts to your screen size
- Desktop: Full grid layout like a real TV guide
- Mobile: Vertical channel list with horizontal movie scrolling

**Playback Management:**
- When you click "Watch Now", Popcorn talks to the Plex API
- It finds your selected device (TV, streaming stick, etc.)
- Sends a command to start playing the movie
- All playback happens through Plex—Popcorn is just the remote control

**Data Storage:**
- SQLite database stores everything (schedules, watch history, user preferences)
- Volume mounting in Docker ensures your data persists between updates
- Automatic database migrations handle upgrades smoothly

### Technology Stack

**Frontend:**
- Bootstrap 5 for responsive layouts
- Minimal JavaScript for smooth interactions
- CSS custom properties for theme switching
- Font Awesome icons

**Backend:**
- Flask web framework (Python)
- SQLAlchemy for database operations
- PlexAPI library for Plex integration
- Flask-Login for user sessions

**Security:**
- Password hashing with Werkzeug
- CSRF protection on all forms
- Secure session management
- OAuth integration with Plex accounts

---

## 🎨 Themes & Customization

Popcorn comes with several built-in themes:
- **Plex**: Clean, modern look matching Plex's style
- **Halloween**: Spooky orange and black
- **Christmas**: Festive red and green
- **Custom**: Create your own color scheme

**Retro Options** (Admin Settings):
- CRT monitor effect with scanlines
- Film grain overlay
- Classic cable channel numbers

---

## 📱 Mobile Experience

The TV guide automatically adapts for phones and tablets:
- Channels stack vertically
- Movies scroll horizontally within each channel
- Tap movie posters to see details
- Tap again to play

Works great for browsing on the couch!

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

---

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/netpersona/Popcorn/issues)
- **Discussions**: [GitHub Discussions](https://github.com/netpersona/Popcorn/discussions)

---

## 🙏 Acknowledgments

**Made with 🍿 for Plex enthusiasts who miss the golden age of channel surfing**

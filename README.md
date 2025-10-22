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


## ✨ Features

- **🎬 Auto-Generated Channels** – Action, Comedy, Drama, Horror, and more—organized from your Plex library
- **🎃 Seasonal Channels** – Halloween Horror, Christmas Classics, and holiday-themed programming
- **📺 Retro TV Guide** – Time-based program grid with optional CRT effects and film grain
- **📱 Multi-Device Playback** – Save your Roku, Apple TV, Fire Stick, and other Plex clients
- **🔐 Secure Authentication** – Plex OAuth or local accounts with admin controls
- **🎨 Customizable Themes** – Plex dark mode, seasonal themes, or create your own
- **📊 Watch History** – Track what you've watched with viewing statistics
- **👥 User Management** – Admin dashboard with invite codes and access controls

---

## 🚀 Quick Start

### Docker Compose (Recommended)

The easiest installation method with automatic persistence:

1. **Download** `docker-compose.yml` from this repository
2. **Edit** the file:
   ```yaml
   SESSION_SECRET: "your-random-secret-here"  # Generate with: openssl rand -hex 32
   PLEX_URL: "http://192.168.1.100:32400"     # Optional
   PLEX_TOKEN: "your-plex-token"              # Optional
   ```
3. **Launch**:
   ```bash
   docker-compose up -d
   ```

Your data automatically persists in `./popcorn-data` and survives container updates.

**Update anytime:** 
```bash
docker-compose pull && docker-compose up -d
```

---

### Unraid

Install from **Community Applications**:

1. Search for "Popcorn" in Community Apps
2. Fill in `SESSION_SECRET` (and optionally Plex settings)
3. Click **Apply**

All volume mappings are pre-configured. See [UNRAID_SETUP.md](UNRAID_SETUP.md) for details.

---

### Manual Docker

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

> ⚠️ **Critical:** The `-v ./popcorn-data:/data` volume mapping is required to persist your database between updates.

---

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SESSION_SECRET` | **Yes** | — | Session encryption key (generate with `openssl rand -hex 32`) |
| `PLEX_URL` | No | — | Plex server URL (e.g., `http://192.168.1.100:32400`) |
| `PLEX_TOKEN` | No | — | Plex authentication token |
| `DATA_DIR` | No | `/data` | Data directory path (Docker) or `./` (local dev) |

> **Note:** `PLEX_URL` and `PLEX_TOKEN` can be configured through the web interface after first login.

### Finding Your Plex Token

1. Open Plex Web App and play any item
2. Click the **ⓘ** icon → **View XML**
3. Look for `X-Plex-Token=` in the URL
4. Copy the token value

📖 [Official Plex Documentation](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)

---

## 🎯 First-Time Setup

1. **Access** the web interface at `http://your-server-ip:5000`
2. **Login** with default credentials:
   - Username: `admin`
   - Password: `admin`
3. **⚠️ Change the default password immediately** (you'll see a warning banner)
4. **Configure Plex** in **Admin → Settings** (if not set via environment variables)
5. **Generate** your first schedule from the home page

---

## 🛠️ Local Development

```bash
# Clone the repository
git clone https://github.com/netpersona/Popcorn.git
cd Popcorn

# Install dependencies
pip install -r requirements.txt

# Configure environment
export SESSION_SECRET="$(openssl rand -hex 32)"
export PLEX_URL="http://192.168.1.100:32400"
export PLEX_TOKEN="your-token-here"

# Run the application
python app.py
```

Access at `http://localhost:5000`

---

## 🏗️ Architecture

### Frontend
- **Server-Side Rendering** with Jinja2 templates and Bootstrap 5
- **Dynamic Theme System** using CSS custom properties
- **Responsive Design** with mobile (<600px), tablet (600-1023px), and desktop (≥1024px) breakpoints
- **Optional Retro Effects** including CRT monitor simulation and film grain overlay

### Backend
- **Flask** web framework with SQLAlchemy ORM
- **Multi-Strategy Authentication** supporting Plex OAuth and local accounts
- **Automated Schedule Generation** with genre-based and seasonal channels
- **Image Caching** using bounded LRU cache (300 items, ~150MB)
- **Multi-Device Playback** with platform-specific client management

### Integrations
- **Plex Media Server** via PlexAPI library for metadata and playback control
- **Plex OAuth** for seamless user authentication
- **GitHub** for automatic update detection (Docker-aware)

---

## 📊 Data Models

- **User** – Authentication, preferences, admin flags
- **Movie** – Plex metadata (title, genre, duration, posters)
- **Schedule** – Time-slot assignments for channels
- **HolidayChannel** – Seasonal channel configurations
- **WatchHistory** – Viewing records and statistics
- **SavedDevice** – User's Plex playback devices
- **CustomTheme** – User-created color schemes

Database migrations are idempotent and safe for upgrades.

---

## 🔐 Security

- **CSRF Protection** on all forms
- **Password Hashing** with Werkzeug
- **Session Encryption** via Flask secret keys
- **Default Password Warnings** for new installations

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 💬 Support

- **Issues:** [GitHub Issues](https://github.com/netpersona/Popcorn/issues)
- **Documentation:** [Wiki](https://github.com/netpersona/Popcorn/wiki)

---

**Made with ❤️ for Plex enthusiasts who miss the golden age of channel surfing**
- **Custom CSS**: Inline styles in templates for theme-specific styling

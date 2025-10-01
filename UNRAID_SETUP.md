# Popcorn - Unraid Setup Guide

This guide explains how to install and configure Popcorn on Unraid.

## Quick Installation

### Option 1: Community Applications (Coming Soon)

Once Popcorn is added to Community Applications:

1. Open Unraid web interface
2. Go to **Apps** tab
3. Search for "**Popcorn**"
4. Click **Install**
5. Configure the required settings (see below)
6. Click **Apply**

### Option 2: Manual Installation (Available Now)

You can install Popcorn manually while waiting for Community Apps approval:

1. **Download the template:**
   - Save `popcorn-unraid-template.xml` from the Popcorn repository
   - Or create it manually (template provided below)

2. **Upload to Unraid:**
   - Copy the XML file to: `/boot/config/plugins/dockerMan/templates-user/`
   - Or use the Unraid web interface: Docker → Add Container → Template dropdown

3. **Install from your template:**
   - Go to Docker tab
   - Click **Add Container**
   - Select your uploaded template
   - Configure settings
   - Click **Apply**

## Required Configuration

When installing Popcorn on Unraid, you **must** configure these settings:

### 1. Session Secret (Required)
- **Field:** `SESSION_SECRET`
- **Description:** Random secret key for session security
- **Value:** Generate a random string (32+ characters recommended)
- **Example:** `mysupersecretkey12345678901234567890`
- **Security:** This field is masked (hidden) in the UI

### 2. Plex Server URL (Required)
- **Field:** `PLEX_URL`
- **Description:** URL of your Plex Media Server
- **Format:** `http://IP_ADDRESS:32400`
- **Examples:**
  - `http://192.168.1.100:32400` (local network)
  - `http://tower.local:32400` (if using Unraid hostname)
- **Note:** Use your Unraid server's IP if Plex is on the same machine

### 3. Plex Authentication Token (Required)
- **Field:** `PLEX_TOKEN`
- **Description:** Your Plex authentication token
- **How to get:** See "Getting Your Plex Token" section below
- **Security:** This field is masked (hidden) in the UI

### 4. Plex Client Name (Optional)
- **Field:** `PLEX_CLIENT`
- **Description:** Name of your Plex playback device
- **Examples:** `Roku Living Room`, `Plex for Android`
- **Note:** Leave blank if you don't need direct playback to a specific client
- **Purpose:** Allows playing movies directly on a Plex client (Roku, TV, etc.)

### 5. Web UI Port (Customizable)
- **Field:** `WebUI Port`
- **Description:** Port for accessing Popcorn web interface
- **Default:** `5000`
- **Custom:** Change to any available port (e.g., `8080`, `7000`)
- **Access:** `http://UNRAID_IP:PORT`

### 6. AppData Path (Optional)
- **Field:** `AppData`
- **Description:** Where Popcorn stores its database and files
- **Default:** `/mnt/user/appdata/popcorn`
- **Note:** Usually doesn't need to be changed

## Getting Your Plex Token

### Method 1: Using Plex Web App (Easiest)
1. Open a movie in Plex Web App
2. Click the three dots (⋮) → "Get Info"
3. Click "View XML"
4. Look in the URL bar for `X-Plex-Token=XXXXX`
5. Copy everything after the equals sign

### Method 2: Using Browser Console
1. Open Plex Web App in your browser
2. Press `F12` to open Developer Tools
3. Go to Console tab
4. Type: `localStorage.getItem('myPlexAccessToken')`
5. Press Enter and copy the token (without quotes)

### Method 3: Using Plex Devices Page
1. Sign in at https://www.plex.tv/sign-in
2. Navigate to: https://plex.tv/devices.xml
3. Find your server in the XML
4. Look for `token="YOUR_TOKEN"`

## Installation Example

Here's a complete installation example with all settings:

```
Container Name: Popcorn
Repository: your-dockerhub-username/popcorn:latest
Network Type: Bridge

Port Mappings:
- Container Port: 5000 → Host Port: 5000 (or your custom port)

Environment Variables:
- SESSION_SECRET = myverylongrandomsecretkey12345678
- PLEX_URL = http://192.168.1.100:32400
- PLEX_TOKEN = AbCdEfGhIjKlMnOpQrStUvWxYz123456
- PLEX_CLIENT = Roku Living Room (optional)

Path Mappings:
- Container Path: /app → Host Path: /mnt/user/appdata/popcorn
```

## After Installation

### First Run
1. Wait for the container to start (may take a minute)
2. Access Popcorn at: `http://UNRAID_IP:5000`
3. Popcorn will automatically:
   - Connect to your Plex server
   - Scan your movie library
   - Generate channels based on genres
   - Create 24-hour schedules

### Verify Installation
1. Check container logs in Unraid Docker tab
2. Should see: "Connected to Plex server" and "Schedules generated"
3. Open the web interface and verify channels appear

### If Something Goes Wrong
- Check Docker logs for error messages
- Verify Plex credentials are correct
- Make sure Plex server is running and accessible
- See Troubleshooting section below

## Using Popcorn on Unraid

### Accessing the Interface
- **Local network:** `http://UNRAID_IP:5000`
- **From any device:** Browse to the URL on phone, tablet, or computer
- **Bookmark it:** Add to your favorites for quick access

### Syncing New Movies
When you add new movies to your Plex library:
1. Open Popcorn web interface
2. Click the menu icon
3. Select "Sync"
4. Wait for sync to complete
5. New movies will appear in appropriate channels

### Changing Settings
1. Go to Settings page
2. Change reshuffle frequency (Daily/Weekly/Monthly)
3. Click "Save Settings"
4. Use "Reshuffle Now" to regenerate schedules immediately

## Unraid-Specific Tips

### Using Unraid as Plex Server
If Plex is running on the same Unraid server:
- Use `http://UNRAID_IP:32400` for PLEX_URL
- Or use `http://localhost:32400` if both are on the same Docker network
- Or use `http://172.17.0.1:32400` to access host from container

### Network Configuration
- **Bridge Mode** (default) - Standard Docker networking
- **Host Mode** - Use if having connection issues (advanced)
- **Custom Bridge** - If using custom Docker networks

### Reverse Proxy (Advanced)
If using nginx or Swag for reverse proxy:
1. Add Popcorn to your proxy configuration
2. Set up subdomain: `popcorn.yourdomain.com`
3. Configure SSL certificate
4. Access from anywhere securely

### Backup Configuration
Your Popcorn data is stored in `/mnt/user/appdata/popcorn`

To backup:
1. Stop the Popcorn container
2. Copy the entire `/mnt/user/appdata/popcorn` folder
3. Store backup safely
4. Restart container

To restore:
1. Stop the Popcorn container
2. Replace `/mnt/user/appdata/popcorn` with backup
3. Restart container

## Troubleshooting

### Container Won't Start
**Check:**
1. Docker logs in Unraid interface
2. Port conflicts (is port 5000 already used?)
3. AppData path is accessible
4. Required environment variables are set

**Solution:**
```bash
# From Unraid terminal:
docker logs Popcorn

# Check if port is in use:
netstat -tlnp | grep 5000
```

### "Plex API not available" Error
**Check:**
1. PLEX_URL is correct and Plex is running
2. PLEX_TOKEN is valid (not expired)
3. Popcorn container can reach Plex (network)
4. Firewall not blocking connection

**Test Connection:**
```bash
# From Unraid terminal:
curl http://YOUR_PLEX_IP:32400/identity
```
Should return XML with server info.

### No Channels Showing
**Check:**
1. Plex library actually has movies
2. Movies have genre tags
3. Sync completed successfully (check logs)

**Solution:**
1. Go to: `http://UNRAID_IP:5000/sync`
2. Wait for sync to complete
3. Check container logs for errors

### Can't Play Movies
**Check:**
1. Plex client is powered on and connected
2. PLEX_CLIENT name matches exactly
3. Plex app is installed on playback device

**Solution:**
- Use second-screen control: browse on phone, cast to TV
- Or leave PLEX_CLIENT blank and use Plex app directly

### Performance Issues
**Check:**
1. Unraid server has enough resources
2. Not running too many Docker containers
3. AppData is on cache drive (SSD) for better performance

## Updating Popcorn

### Manual Update
1. Go to Docker tab in Unraid
2. Click "Check for Updates"
3. If update available, click "Update"
4. Container will restart automatically

### Auto-Update (Optional)
Enable auto-updates in Docker settings:
1. Edit Popcorn container
2. Enable "Auto Update" toggle
3. Set update schedule
4. Save changes

## Advanced Configuration

### Custom Docker Network
```bash
# Create custom network
docker network create popcorn-net

# Edit container to use custom network
# In Unraid Docker settings, change Network Type to: popcorn-net
```

### Resource Limits
In Unraid Docker settings, you can limit:
- CPU cores
- Memory (RAM)
- Disk space

Recommended minimums:
- CPU: 1 core
- RAM: 512 MB
- Disk: 1 GB

## Support

If you need help:

1. **Check logs first:**
   - Unraid Docker tab → Popcorn → Logs
   
2. **Search documentation:**
   - USER_GUIDE.md has comprehensive troubleshooting
   
3. **Community support:**
   - Unraid forums
   - GitHub issues

---

## Publishing to Community Applications

### For Developers

To add Popcorn to Unraid Community Applications:

1. **Create GitHub repository** with Popcorn code
2. **Upload template** (`popcorn-unraid-template.xml`)
3. **Update template URLs:**
   - Change `your-dockerhub-username` to actual Docker Hub username
   - Change `your-username` to GitHub username
   - Update all GitHub URLs

4. **Publish Docker image:**
   ```bash
   docker build -t your-dockerhub-username/popcorn:latest .
   docker push your-dockerhub-username/popcorn:latest
   ```

5. **Submit to Community Applications:**
   - Fork: https://github.com/Squidly271/AppFeed
   - Add your template XML to appropriate category
   - Submit pull request
   - Wait for approval

6. **Create support thread:**
   - Post on Unraid forums
   - Explain what Popcorn does
   - Link to GitHub repository
   - Provide installation instructions

### Template Checklist
- [ ] All URLs updated with real usernames
- [ ] Docker image published to Docker Hub
- [ ] Icon URL accessible (PNG format)
- [ ] Support forum thread created
- [ ] Template tested on Unraid
- [ ] All required variables documented
- [ ] GitHub repository is public

---

Enjoy Popcorn on Unraid! 🍿📺

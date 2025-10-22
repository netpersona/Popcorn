# 🍿 Popcorn - Unraid Setup Guide

Complete installation and configuration guide for running Popcorn on Unraid.

---

## 📦 Installation

### Community Applications (Recommended)

1. Open Unraid web interface
2. Navigate to **Apps** tab
3. Search for **"Popcorn"**
4. Click **Install**
5. Configure required settings (see below)
6. Click **Apply**

### Manual Installation

If the template isn't available in Community Apps yet:

1. **Download the template:**
   - Save `popcorn-unraid-template.xml` from the [GitHub repository](https://github.com/netpersona/Popcorn)

2. **Upload to Unraid:**
   - Place the XML file in: `/boot/config/plugins/dockerMan/templates-user/`
   - Or via web UI: **Docker → Add Container → Template dropdown**

3. **Install from template:**
   - Go to **Docker** tab
   - Click **Add Container**
   - Select your uploaded template
   - Configure settings and click **Apply**

---

## ⚙️ Required Configuration

### 1. Session Secret ✅ Required

**Generate a secure random string for session encryption:**

```bash
# Generate using OpenSSL (recommended)
openssl rand -hex 32
```

- **Field:** `SESSION_SECRET`
- **Example:** `a3f8d9e2b1c4567890abcdef12345678`
- **Security:** This field is masked in the UI

### 2. Plex Server URL ✅ Required

**The address of your Plex Media Server:**

- **Field:** `PLEX_URL`
- **Format:** `http://IP_ADDRESS:32400`
- **Examples:**
  - `http://192.168.1.100:32400` (local network)
  - `http://tower.local:32400` (using Unraid hostname)
- **Important:** Use local IP for device playback (see troubleshooting)

### 3. Plex Authentication Token ✅ Required

**Your Plex authentication token:**

- **Field:** `PLEX_TOKEN`
- **How to obtain:** See [Finding Your Plex Token](#finding-your-plex-token) section
- **Security:** This field is masked in the UI

### 4. Web UI Port (Optional)

**Port for accessing the Popcorn interface:**

- **Field:** `WebUI Port`
- **Default:** `5000`
- **Custom:** Any available port (e.g., `8080`, `7000`)
- **Access:** `http://UNRAID_IP:PORT`

### 5. AppData Path ⚠️ Critical

**Where Popcorn stores its database and configuration:**

- **Container Path:** `/data` (do NOT change)
- **Host Path:** `/mnt/user/appdata/popcorn` (customizable)
- **Purpose:** Preserves your data across container updates

> **Critical:** Without proper volume mapping, you'll lose all data when updating!

---

## 🔑 Finding Your Plex Token

### Method 1: Plex Web App (Easiest)

1. Open any movie in Plex Web App
2. Click the **three dots (⋮)** → **"Get Info"**
3. Click **"View XML"**
4. Look in the URL bar for `X-Plex-Token=XXXXX`
5. Copy everything after the equals sign

### Method 2: Browser Console

1. Open Plex Web App in your browser
2. Press **F12** to open Developer Tools
3. Go to **Console** tab
4. Type: `localStorage.getItem('myPlexAccessToken')`
5. Press Enter and copy the token (without quotes)

### Method 3: Plex Devices Page

1. Sign in at [plex.tv/sign-in](https://www.plex.tv/sign-in)
2. Navigate to: [plex.tv/devices.xml](https://plex.tv/devices.xml)
3. Find your server in the XML
4. Look for `token="YOUR_TOKEN"`

📖 [Official Plex Documentation](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)

---

## 📋 Complete Installation Example

```
Container Name: Popcorn
Repository: netpersona/popcorn:latest
Network Type: Bridge

Port Mappings:
  5000 (Container) → 5000 (Host)

Environment Variables:
  SESSION_SECRET = a3f8d9e2b1c4567890abcdef12345678
  PLEX_URL = http://192.168.1.100:32400
  PLEX_TOKEN = AbCdEfGhIjKlMnOpQrStUvWxYz123456

Path Mappings:
  /data (Container) → /mnt/user/appdata/popcorn (Host)
```

---

## 🚀 First-Time Setup

### Initial Access

1. Wait for the container to start (may take 30-60 seconds)
2. Access Popcorn at: `http://UNRAID_IP:5000`
3. Login with default credentials:
   - **Username:** `admin`
   - **Password:** `admin`
4. **⚠️ Change the default password immediately**

### Automatic Setup

Popcorn will automatically:
- Connect to your Plex server
- Scan your movie library
- Generate genre-based channels
- Create 24-hour schedules

### Verification

**Check container logs:**
```bash
docker logs Popcorn
```

**Look for:**
- ✅ `Connected to Plex server`
- ✅ `Schedules generated`
- ✅ Channels visible in web interface

---

## 🔄 Regular Usage

### Syncing New Movies

When you add movies to Plex:

1. Open Popcorn web interface
2. Click the **menu icon**
3. Select **"Sync"**
4. Wait for sync completion
5. New movies appear in appropriate channels

### Changing Settings

1. Navigate to **Settings** page
2. Adjust reshuffle frequency (Daily/Weekly/Monthly)
3. Click **"Save Settings"**
4. Use **"Reshuffle Now"** to regenerate schedules immediately

---

## 🔧 Unraid-Specific Tips

### Plex on Same Unraid Server

If Plex runs on the same Unraid server as Popcorn:

```bash
# Option 1: Use Unraid IP
PLEX_URL=http://192.168.1.100:32400

# Option 2: Use localhost (if same Docker network)
PLEX_URL=http://localhost:32400

# Option 3: Docker bridge gateway
PLEX_URL=http://172.17.0.1:32400
```

### Network Modes

- **Bridge Mode** (default) – Standard Docker networking
- **Host Mode** – Required for client discovery (see troubleshooting)
- **Custom Bridge** – For custom Docker networks

### Reverse Proxy Setup (Advanced)

Using nginx or Swag:

1. Add Popcorn to proxy configuration
2. Set up subdomain: `popcorn.yourdomain.com`
3. Configure SSL certificate
4. Access securely from anywhere

### Backup & Restore

**Backup Location:** `/mnt/user/appdata/popcorn`

**What's Stored:**
- `popcorn.db` – Database with settings, users, schedules
- Backup files (if auto-backup enabled)

**To Backup:**
```bash
# Stop container
docker stop Popcorn

# Copy data directory
cp -r /mnt/user/appdata/popcorn /mnt/user/backups/popcorn-backup

# Restart container
docker start Popcorn
```

**To Restore:**
```bash
# Stop container
docker stop Popcorn

# Replace data directory
rm -rf /mnt/user/appdata/popcorn
cp -r /mnt/user/backups/popcorn-backup /mnt/user/appdata/popcorn

# Restart container
docker start Popcorn
```

---

## 🔄 Updating Popcorn

### ⚠️ Critical: Upgrading from Pre-v2.3.1

**If upgrading from versions older than 2.3.1, read this section carefully!**

#### Why Manual Migration is Required

- **Old versions:** Stored data in `/app` (deleted on updates)
- **New versions (2.3.1+):** Store data in `/data` (persists across updates)
- Unraid's "Update" button **does NOT** change volume mappings automatically

#### Migration Steps

**Step 1: Backup Your Data**
```bash
# From Unraid terminal
cp /mnt/user/appdata/popcorn/popcorn.db /mnt/user/appdata/popcorn-backup.db
```

**Step 2: Stop the Container**
1. Go to **Docker** tab
2. Click **Popcorn** container
3. Click **"Stop"**

**Step 3: Update Volume Mapping**
1. Click **Popcorn** container
2. Click **"Edit"**
3. Find **Path Mappings** section
4. Change **Container Path** from `/app` → `/data`
   - Host Path: `/mnt/user/appdata/popcorn` (unchanged)
   - Container Path: `/data` (changed)
5. Click **"Apply"**

**Step 4: Verify**
```bash
# Check logs after container starts
docker logs Popcorn | grep "Using database"

# Should show: INFO:__main__:Using database: /data/popcorn.db
# If shows ./popcorn.db, volume mapping is incorrect
```

### Regular Updates (v2.3.1+)

Once properly configured, updates are automatic:

**Manual Update:**
1. **Docker** tab → **Check for Updates**
2. Click **"Update"** if available
3. Container restarts automatically
4. Data persists ✅

**Auto-Update (Optional):**
1. Edit Popcorn container
2. Enable **"Auto Update"** toggle
3. Set update schedule
4. Save changes

---

## 🔍 Troubleshooting

### Container Won't Start

**Checklist:**
- [ ] Docker logs show errors: `docker logs Popcorn`
- [ ] Port 5000 not already in use: `netstat -tlnp | grep 5000`
- [ ] AppData path accessible
- [ ] Required environment variables set

### "Plex API not available" Error

**Checklist:**
- [ ] `PLEX_URL` is correct and Plex is running
- [ ] `PLEX_TOKEN` is valid (not expired)
- [ ] Network connectivity between containers

**Test Connection:**
```bash
# Should return XML with server info
curl http://YOUR_PLEX_IP:32400/identity
```

### No Channels Showing

**Solutions:**
1. Verify Plex library has movies with genre tags
2. Manually sync: `http://UNRAID_IP:5000/sync`
3. Check container logs for errors

### Can't Play Movies / "No Plex Clients Found"

This is the most common issue. Here's how to fix it:

#### 1. Use Local PLEX_URL ⚠️ Critical

**MUST use your local network IP, not public URLs:**

```bash
# ✅ CORRECT - Local IP
PLEX_URL=http://192.168.1.100:32400

# ❌ WRONG - Public IP or domain
PLEX_URL=http://66.241.174.242:19019
PLEX_URL=https://myplex.mydomain.com
```

**Why:** The Plex `/clients` endpoint only discovers devices on the same local network.

**Test:**
```bash
# Should show your devices in XML (while Plex app is open)
curl "http://YOUR_LOCAL_IP:32400/clients?X-Plex-Token=YOUR_TOKEN"
```

#### 2. Use Host Network Mode ✅ Required

**Both Plex AND Popcorn must use Host network mode for device discovery:**

1. Edit **Popcorn** container
2. Change **Network Type** from `Bridge` → `Host`
3. Remove port mappings (not needed in host mode)
4. Save and restart

**Why:** Bridge mode isolates containers from network broadcasts (GDM protocol) used by Plex for device discovery.

#### 3. Pi-hole / DNS Ad-Blocker Users

**Whitelist this domain:**
```
config.claspws.tv
```

This is Plex's companion app service for device discovery.

**In Pi-hole:**
1. Go to **Whitelist**
2. Add: `config.claspws.tv`
3. Save
4. Restart Plex app on device

#### 4. Plex App Must Be Open

The Plex app must be **running** on your target device:

- ✅ Plex app open on home screen = Device visible
- ❌ Plex app closed = Device hidden

You don't need to play anything—just have the app open.

#### 5. Use Correct Client Identifier

In **Profile → Playback Settings** (or `PLEX_CLIENT` env var):

**Option A - Device UUID (Recommended):**
```
6d89441adccb7d3506b90954cddc17cf
```

Get UUID from: `https://plex.tv/api/resources.xml?X-Plex-Token=YOUR_TOKEN`

**Option B - Device Name:**
```
Roku Living Room
```

**Why UUID:** Ensures correct targeting if you have multiple devices with the same name.

#### 6. Cloud vs Local Deployment

**Client playback ONLY works on local networks:**

- ✅ Unraid/Docker at home = Can push to local devices
- ❌ Cloud hosting = Cannot reach local devices

If cloud-hosted, use **Web Player mode** instead.

#### Quick Checklist

- [ ] `PLEX_URL` uses local IP (e.g., `http://192.168.1.100:32400`)
- [ ] Both Plex and Popcorn use **Host network mode**
- [ ] Whitelisted `config.claspws.tv` (if using Pi-hole)
- [ ] Plex app is **open** on target device
- [ ] Same Plex account on server and client
- [ ] Running on local network (not cloud)

**Still not working?**
- Switch to **Web Player mode** (works everywhere)
- Check Plex server logs for GDM errors

### Performance Issues

**Checklist:**
- [ ] Unraid server has sufficient resources
- [ ] Not running too many containers
- [ ] AppData on cache drive (SSD) for better performance

---

## 🎯 Advanced Configuration

### Custom Docker Network

```bash
# Create custom network
docker network create popcorn-net

# Edit container to use: popcorn-net
```

### Resource Limits

Set limits in Unraid Docker settings:

**Recommended Minimums:**
- **CPU:** 1 core
- **RAM:** 512 MB
- **Disk:** 1 GB

---

## 💬 Support

Need help? Try these resources:

1. **Check logs first:**
   - Unraid: **Docker** tab → **Popcorn** → **Logs**

2. **Documentation:**
   - [User Guide](USER_GUIDE.md) – Comprehensive troubleshooting
   - [GitHub Issues](https://github.com/netpersona/Popcorn/issues)

3. **Community:**
   - Unraid forums
   - GitHub Discussions

**Enjoy Popcorn on Unraid! 🍿📺**

# Docker Volume Fix - Data Persistence

## Problem
Previous versions of Popcorn stored the database (`popcorn.db`) directly in the `/app` directory inside the container. When you updated the Docker image, the entire `/app` directory was replaced with the new version, **deleting your database** and all configurations.

## Solution
**Version 2.3.1+** moves all persistent data to a dedicated `/data` volume that is preserved across updates.

## For New Installations (Easy!)

**If you're installing Popcorn for the first time, you don't need to read this document!** The volume mapping is pre-configured in:

✅ **Docker Compose** - Just download `docker-compose.yml` and run `docker-compose up -d`  
✅ **Unraid** - Install from Community Applications (volume already configured)  
✅ **README examples** - All commands include the correct `-v` flag

**This document is only for users upgrading from old versions that stored data in `/app`.**

---

## If You're Updating from an Older Version

### Step 1: Stop the Container
```bash
docker stop Popcorn
```

### Step 2: Copy Your Existing Database
If you have an existing installation with data you want to keep:

```bash
# Find your container ID
docker ps -a | grep popcorn

# Copy the database out of the old container
docker cp Popcorn:/app/popcorn.db ./popcorn-backup.db
```

### Step 3: Remove Old Container
```bash
docker rm Popcorn
```

### Step 4: Pull New Image
```bash
docker pull netpersona/popcorn:latest
```

### Step 5: Create Volume Directory
```bash
# On Unraid:
mkdir -p /mnt/user/appdata/popcorn

# On other systems:
mkdir -p /path/to/your/data/popcorn
```

### Step 6: Restore Your Database
```bash
# Copy your backup to the new volume location
cp ./popcorn-backup.db /mnt/user/appdata/popcorn/popcorn.db
```

### Step 7: Start Container with Correct Volume Mapping

**Unraid Docker Settings:**
- Change the AppData mapping from:
  - Old: `Container Path: /app` → Host Path: `/mnt/user/appdata/popcorn`
  - New: `Container Path: /data` → Host Path: `/mnt/user/appdata/popcorn`

**Docker Command Line:**
```bash
docker run -d \
  --name Popcorn \
  -p 5000:5000 \
  -v /mnt/user/appdata/popcorn:/data \
  -e SESSION_SECRET="your-secret-key" \
  -e PLEX_URL="http://your-plex-ip:32400" \
  -e PLEX_TOKEN="your-plex-token" \
  --restart unless-stopped \
  netpersona/popcorn:latest
```

**Docker Compose:**
```yaml
version: '3.8'
services:
  popcorn:
    image: netpersona/popcorn:latest
    container_name: Popcorn
    ports:
      - "5000:5000"
    volumes:
      - /mnt/user/appdata/popcorn:/data  # Changed from /app to /data
    environment:
      - SESSION_SECRET=your-secret-key
      - PLEX_URL=http://your-plex-ip:32400
      - PLEX_TOKEN=your-plex-token
    restart: unless-stopped
```

---


---

## Verification

After starting the container, check the logs to verify the database path:

```bash
docker logs Popcorn | grep "Using database"
```

You should see:
```
INFO:__main__:Using database: /data/popcorn.db
```

---

## What's Stored in the /data Volume

- `popcorn.db` - Main SQLite database containing:
  - Users and authentication
  - Saved Plex devices
  - Plex server configuration
  - Custom themes
  - Watch history
  - Invitation codes
  - All settings and preferences
- Backup files (if auto-backup is enabled)

---

## Troubleshooting

### "No users found" after update
Your old database wasn't migrated. Follow the steps above to copy it from the old container.

### Can't log in with old credentials
Database permissions issue. Check:
```bash
ls -la /mnt/user/appdata/popcorn/
```

The `popcorn.db` file should exist and be readable.

### "Using database: ./popcorn.db" in logs
The `/data` volume isn't properly mapped. Stop the container and fix the volume mapping.

---

## Key Points

✅ **Always use `/data` as the container path**  
✅ **Map to a persistent host directory** (like `/mnt/user/appdata/popcorn`)  
✅ **Back up `/data` regularly** to avoid data loss  
✅ **Never map `/app`** - that's the application code, not your data  

With this fix, your configurations will now persist across Docker image updates! 🎉

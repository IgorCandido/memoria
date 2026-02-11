# Docker/Colima Configuration for Memoria

**Created**: 2026-01-31
**Purpose**: Document proper Docker/Colima configuration to prevent split-brain container issues

## The Problem: Split-Brain Containers

When both Docker Desktop and Colima run simultaneously on macOS, they create **separate Docker contexts** that can't see each other's containers. This causes:
- ChromaDB container running in one context but not accessible from the other
- "Connection refused" errors despite container showing as "running"
- Wasted resources running two Docker daemons
- Confusion about which containers are actually available

## Solution: Colima-Only Configuration

**Use Colima exclusively for development.** Docker Desktop should be disabled.

### Why Colima?

- Lightweight (uses Apple Virtualization.framework on Apple Silicon)
- Open-source
- Better performance on Apple Silicon Macs
- Simpler configuration
- Auto-start on boot configuration available

## Setup Instructions

### 1. Check Current State

```bash
# Check Docker contexts
docker context ls
# Should show: colima, default, desktop-linux

# Check active context (look for *)
docker context show
# Should output: colima

# Check if Docker Desktop is running
ps aux | grep -i docker | grep -v grep
```

### 2. Stop Docker Desktop

```bash
# Quit Docker Desktop app completely
# macOS: Docker Desktop menu bar icon → Quit Docker Desktop

# Verify Docker Desktop daemon is stopped
docker context ls  # desktop-linux should not show "ERROR"
```

### 3. Disable Docker Desktop Auto-Start

**Option A: Docker Desktop Settings**
1. Open Docker Desktop
2. Settings → General
3. Uncheck "Start Docker Desktop when you log in"
4. Quit Docker Desktop

**Option B: System Preferences**
1. System Preferences → Users & Groups (or Login Items)
2. Login Items tab
3. Remove Docker Desktop from the list

### 4. Install/Configure Colima

```bash
# Install Colima (if not already installed)
brew install colima

# Start Colima with appropriate resources
colima start --cpu 4 --memory 8

# Verify Colima is running
colima status
# Should output: "colima is running"

# Set Colima as active Docker context
docker context use colima

# Verify context switch
docker context show
# Should output: "colima"
```

### 5. Configure Colima Auto-Start

Colima doesn't auto-start by default. To enable auto-start on macOS boot:

**Create LaunchAgent**:

```bash
# Create LaunchAgent file
cat > ~/Library/LaunchAgents/com.colima.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.colima</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/colima</string>
        <string>start</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/colima-startup.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/colima-startup-error.log</string>
</dict>
</plist>
EOF

# Load LaunchAgent (will start on next boot)
launchctl load ~/Library/LaunchAgents/com.colima.plist
```

**Alternative: Use Colima's built-in auto-start** (if available in your version):

```bash
colima start --foreground=false
```

### 6. Verify ChromaDB Container Access

```bash
# Check if ChromaDB container is running
docker ps --filter "name=memoria-chromadb"

# Test ChromaDB API
curl -s http://localhost:8001/api/v2/heartbeat

# Should return: {"nanosecond heartbeat": <timestamp>}
```

## Verification Steps

After setup, verify the configuration:

1. **Only Colima Running**:
   ```bash
   ps aux | grep -i docker | grep -v grep
   # Should show only Colima processes, NOT Docker Desktop
   ```

2. **Correct Context**:
   ```bash
   docker context show
   # Output: colima
   ```

3. **ChromaDB Accessible**:
   ```bash
   docker ps | grep chroma
   # Should show running memoria-chromadb container

   curl http://localhost:8001/api/v2/heartbeat
   # Should return heartbeat response
   ```

4. **No Split-Brain**:
   ```bash
   docker context ls
   # desktop-linux should be present but NOT active (no *)
   # OR show "ERROR" if Docker Desktop is not running
   ```

## Troubleshooting

### Colima Won't Start

**Error**: "failed to run attach disk, in use by instance"

**Solution**: Delete and recreate Colima instance
```bash
colima delete -f
colima start --cpu 4 --memory 8
```

### ChromaDB Container Not Found

**Symptom**: `docker ps` doesn't show memoria-chromadb

**Solution**: Container exists in different context
```bash
# Switch to Colima context
docker context use colima

# Verify container is in this context
docker ps -a | grep chroma

# If container doesn't exist, start ChromaDB
docker run -d --name memoria-chromadb \
  -p 8001:8000 \
  -v chroma_data:/data \
  chromadb/chroma:latest
```

### Connection Refused to ChromaDB

**Symptom**: Python error "Connection refused" to localhost:8001

**Causes**:
1. ChromaDB container is "unhealthy" - wait 30 seconds for health check
2. Wrong Docker context - switch to Colima context
3. Port mapping incorrect - verify with `docker ps`

**Solution**:
```bash
# Check container status
docker ps --filter "name=memoria-chromadb" --format "{{.Status}}"

# If "unhealthy", check logs
docker logs memoria-chromadb --tail 50

# If container missing, start it
docker run -d --name memoria-chromadb \
  -p 8001:8000 \
  -v chroma_data:/data \
  chromadb/chroma:latest
```

### Docker Desktop Starts Automatically

**Solution**: Remove from Login Items
1. System Preferences → Users & Groups
2. Login Items tab
3. Select Docker Desktop
4. Click "-" to remove

## Maintenance

### Starting Colima After Reboot

If LaunchAgent not configured:
```bash
colima start
```

### Stopping Colima

```bash
colima stop
```

### Checking Colima Status

```bash
colima status
docker context show
docker ps
```

### Updating Colima

```bash
brew upgrade colima
# May need to recreate instance after upgrade
colima delete -f
colima start --cpu 4 --memory 8
```

## Performance Characteristics

**Colima Resource Usage**:
- CPU: 4 cores allocated
- Memory: 8GB allocated
- Disk: 20GB default (expandable)
- Startup time: ~15-30 seconds (cold start)

**ChromaDB Container**:
- Memory: ~200MB idle, up to 1GB under load
- CPU: Minimal when idle, spikes during indexing
- Disk: Depends on data volume (2837 docs = ~500MB)

## Integration with Memoria

Memoria expects:
- ChromaDB on **localhost:8001** (HTTP mode)
- Docker context: **colima**
- Container name: **memoria-chromadb**
- Volume: **chroma_data** (persistent storage)

**Configuration in code** (memoria/skill_helpers.py):
```python
_vector_store = ChromaDBAdapter(
    collection_name="memoria",
    use_http=True,
    http_host="localhost",
    http_port=8001,  # Maps to container port 8000
)
```

## Summary

✅ **DO**:
- Use Colima exclusively
- Set Colima as active Docker context
- Disable Docker Desktop auto-start
- Configure Colima auto-start with LaunchAgent
- Verify ChromaDB accessibility before running tests

❌ **DON'T**:
- Run Docker Desktop and Colima simultaneously
- Switch contexts mid-session
- Assume containers are accessible without verifying context
- Use Docker Desktop for memoria development

**Expected State**:
- Colima: Running on boot
- Docker Desktop: Stopped, not in Login Items
- Active context: colima
- ChromaDB: Accessible on localhost:8001

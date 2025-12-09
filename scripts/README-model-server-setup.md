# Model Server mTLS Setup Scripts

Scripts for setting up external model server with SPIRE-based mTLS authentication.

---

## Scripts

### 1. `register-model-server-spire.sh`

**Location**: Run on **Hliðskjálf platform**  
**Purpose**: Register the external model server workload with SPIRE and generate join tokens

**Usage**:
```bash
# Generate join token for external machine
./scripts/register-model-server-spire.sh --generate-token

# Just register workload (no token)
./scripts/register-model-server-spire.sh
```

**Output**: Displays join token (expires in 10 minutes) and setup instructions

---

### 2. `setup-model-server-macos.sh`

**Location**: Run on **external macOS machine** (192.168.50.26)  
**Purpose**: Automated setup of SPIRE agent and spiffe-helper on macOS Apple Silicon

**Usage**:
```bash
# Transfer to external machine
scp scripts/setup-model-server-macos.sh user@192.168.50.26:~/

# SSH to machine
ssh user@192.168.50.26

# Run setup
chmod +x setup-model-server-macos.sh
./setup-model-server-macos.sh
```

**What it does**:
1. ✅ Checks prerequisites (macOS, ARM64, sudo)
2. ✅ Downloads SPIRE agent (darwin-arm64)
3. ✅ Downloads spiffe-helper (darwin-arm64)
4. ✅ Creates SPIRE agent config
5. ✅ Creates spiffe-helper config
6. ✅ Sets up launchd services
7. ✅ Tests connectivity to SPIRE server
8. ✅ Prompts for join token
9. ✅ Starts SPIRE agent
10. ✅ Starts spiffe-helper
11. ✅ Verifies certificate generation
12. ✅ Displays next steps

**Environment Variables** (optional):
```bash
# Override SPIRE server IP (default: 10.10.0.10)
export SPIRE_SERVER_IP="192.168.1.100"

# Override SPIRE server port (default: 8081)
export SPIRE_SERVER_PORT="8081"

./setup-model-server-macos.sh
```

---

### 3. `verify-model-server-mtls.sh`

**Location**: Run on **Hliðskjálf platform**  
**Purpose**: Verify mTLS configuration is correct

**Usage**:
```bash
./scripts/verify-model-server-mtls.sh
```

**Checks**:
- ✅ SPIRE server health
- ✅ Agent registration
- ✅ Workload registration
- ✅ Traefik certificates
- ✅ Traefik configuration
- ✅ Port registry
- ✅ Network connectivity
- ✅ End-to-end connection

---

## Complete Workflow

### Step 1: On Hliðskjálf Platform

```bash
cd /Users/nwalker/Development/hlidskjalf

# Register workload and get join token
./scripts/register-model-server-spire.sh --generate-token

# Copy the join token displayed (expires in 10 minutes)
```

### Step 2: Transfer Script to External Machine (192.168.50.26)

**Option A: AirDrop** (easiest for macOS to macOS)
```bash
# Open Finder, right-click the script, select "Share > AirDrop"
# Or drag to AirDrop in Finder sidebar
open -R /Users/nwalker/Development/hlidskjalf/scripts/setup-model-server-macos.sh
```

**Option B: Shared Network Folder**
```bash
# If you have a shared folder mounted on both machines
cp /Users/nwalker/Development/hlidskjalf/scripts/setup-model-server-macos.sh /Volumes/SharedFolder/
```

**Option C: HTTP Server** (temporary)
```bash
# On Hliðskjálf, start a simple HTTP server
cd /Users/nwalker/Development/hlidskjalf/scripts
python3 -m http.server 8888

# On external machine, download:
# curl http://YOUR_HLIDSKJALF_IP:8888/setup-model-server-macos.sh -o setup.sh
```

**Option D: Copy/Paste**
```bash
# On external machine, create the file
cat > setup-model-server-macos.sh << 'EOF'
# Paste the entire script contents here
EOF
chmod +x setup-model-server-macos.sh
```

**Option E: Git/Cloud**
```bash
# Commit to a private repo or push to the platform
# Then clone/pull on the external machine
```

### Step 3: Run Setup on External Machine

```bash
# On the external machine (192.168.50.26)
cd ~/Downloads  # or wherever you saved the script
chmod +x setup-model-server-macos.sh
./setup-model-server-macos.sh
# Paste join token when prompted
```

### Step 3: Configure Model Service

On the external machine:

```bash
# For Ollama
export OLLAMA_HOST=https://0.0.0.0:6701
export OLLAMA_CERT_FILE=/tmp/spire-certs/svid.pem
export OLLAMA_KEY_FILE=/tmp/spire-certs/key.pem
ollama serve

# Or create launchd service (see script output)
```

### Step 4: Verify from Platform

```bash
# Back on Hliðskjálf platform
./scripts/verify-model-server-mtls.sh

# Test connection
curl https://models.ravenhelm.dev/v1/models
```

---

## Troubleshooting

### Token Expired

```bash
# Generate new token on Hliðskjálf
./scripts/register-model-server-spire.sh --generate-token

# On external machine, stop agent and restart with new token
sudo launchctl stop com.spiffe.agent
sudo /usr/local/bin/spire-agent run \
    -config /opt/spire/conf/agent.conf \
    -joinToken "NEW_TOKEN" &
```

### Agent Won't Connect

```bash
# Check connectivity from external machine
nc -zv 10.10.0.10 8081

# Check agent logs
tail -f /var/log/spire-agent.log
tail -f /var/log/spire-agent-error.log
```

### Certificates Not Generated

```bash
# Check spiffe-helper logs
tail -f /var/log/spiffe-helper.log

# Manually test SVID fetch
/usr/local/bin/spire-agent api fetch x509 \
    -socketPath /tmp/spire-agent/public/api.sock
```

### Service Management (macOS)

```bash
# View loaded services
sudo launchctl list | grep spiffe

# Start/stop services
sudo launchctl start com.spiffe.agent
sudo launchctl stop com.spiffe.agent
sudo launchctl start com.spiffe.helper
sudo launchctl stop com.spiffe.helper

# Unload services
sudo launchctl unload /Library/LaunchDaemons/com.spiffe.agent.plist
sudo launchctl unload /Library/LaunchDaemons/com.spiffe.helper.plist

# Reload after config changes
sudo launchctl unload /Library/LaunchDaemons/com.spiffe.agent.plist
sudo launchctl load /Library/LaunchDaemons/com.spiffe.agent.plist
```

---

## Related Documentation

- **RUNBOOK-031**: Complete setup guide with both automated and manual options
- **Quick Start**: `.model-server-quick-start.md`
- **macOS Guide**: `.model-server-macos-setup.md` (manual step-by-step)
- **Migration Notes**: `.model-server-mtls-migration.md`



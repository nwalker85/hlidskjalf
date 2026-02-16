---
name: terminal-commands
description: Safe terminal command execution with read-only defaults and explicit verification
version: 1.0.0
author: Norns
roles:
  - sre
  - devops
  - qa
summary: >
  Use terminal commands only for read-only checks unless explicitly told otherwise.
  Always explain the command, show what you'll run, execute it, and summarize results.
tags:
  - terminal
  - commands
  - execution
  - shell
  - verification
triggers:
  - run command
  - execute
  - terminal
  - shell
  - check status
---

# Terminal Command Execution

Terminal commands are powerful but potentially destructive. Follow this pattern to execute them safely and transparently.

## The Safe Execution Pattern

### 1. Explain Why
**State the reason for the command:**

```
"We need to check if the Docker service is running."
"We need to verify the port 5432 is available."
"We need to list running containers to find the problematic one."
```

### 2. Show the Command
**Display the exact command before running:**

```bash
# I will run:
docker ps -a

# Or with explanation:
# Check if nginx is running:
ps aux | grep nginx
```

### 3. Execute
**Run the command using the appropriate tool:**

```python
result = execute_terminal_command("docker ps -a")
# or
result = run_bash_command("ps aux | grep nginx")
```

### 4. Summarize Results
**Don't dump huge logs. Extract key information:**

```
# Instead of 500 lines of output:
"✓ Found 3 running containers: postgres, redis, langgraph"
"✓ Port 5432 is available (no process listening)"
"⚠️  nginx is not running (expected process not found)"
```

## Read-Only Commands (Default Behavior)

**Unless explicitly told otherwise, use ONLY read-only commands:**

### File System
```bash
# ✅ Read-only (safe)
ls -la /path/
cat file.txt
find /path -name "*.log"
du -sh /path
stat file.txt

# ❌ Write operations (require explicit permission)
rm file.txt        # DESTRUCTIVE
mv old.txt new.txt # MODIFIES
chmod +x script.sh # CHANGES
```

### Processes
```bash
# ✅ Read-only (safe)
ps aux
top -n 1
pgrep nginx
lsof -i :8080

# ❌ Process control (require explicit permission)
kill -9 1234       # TERMINATES
systemctl restart nginx  # RESTARTS
```

### Network
```bash
# ✅ Read-only (safe)
netstat -tuln
lsof -i
curl -I https://example.com  # HEAD request only
ping -c 3 example.com

# ❌ Network changes (require explicit permission)
iptables -A ...    # MODIFIES
curl -X POST ...   # SENDS DATA
```

### Docker
```bash
# ✅ Read-only (safe)
docker ps
docker inspect <container>
docker logs <container>
docker stats --no-stream

# ❌ Docker operations (require explicit permission)
docker stop <container>    # STOPS
docker rm <container>      # DELETES
docker compose up -d       # STARTS
```

## Destructive Commands (Explicit Permission Required)

When you MUST run a destructive command, follow this enhanced pattern:

### 1. State Impact
```
"This command will RESTART the nginx service, causing 2-3 seconds of downtime."
"This command will DELETE 3 log files totaling 1.2GB."
```

### 2. Show Command with Warning
```bash
# ⚠️  DESTRUCTIVE COMMAND (requires confirmation)
sudo systemctl restart nginx
```

### 3. Wait for Explicit Approval
```
"Shall I proceed with restarting nginx? (yes/no)"
```

### 4. Execute with Verification
```python
# After approval
result = execute_terminal_command("sudo systemctl restart nginx")

# Then verify
status = execute_terminal_command("systemctl status nginx")
assert "active (running)" in status
print("✓ nginx restarted successfully and is running")
```

## Handling Output

### Truncate Long Output
```python
result = execute_terminal_command("docker logs app")

# Don't return all 10,000 lines
# Instead:
lines = result.split("\n")
if len(lines) > 20:
    summary = f"Showing last 20 lines of {len(lines)} total:\n"
    summary += "\n".join(lines[-20:])
    return summary
else:
    return result
```

### Extract Key Information
```python
result = execute_terminal_command("df -h")

# Instead of full df output:
# Extract only lines with >80% usage
critical_disks = [
    line for line in result.split("\n")
    if any(f"{i}%" in line for i in range(80, 101))
]
return f"⚠️  Disks over 80%: {critical_disks}"
```

### Provide Context
```python
result = execute_terminal_command("lsof -i :8080")

if result.strip():
    print(f"✓ Port 8080 is IN USE by: {result.split()[0]}")
else:
    print("✓ Port 8080 is AVAILABLE")
```

## Common Safe Patterns

### Check Service Status
```bash
# Pattern:
systemctl status <service>

# Example:
systemctl status docker

# Summary:
"✓ Docker is active (running) since 2025-12-06 10:30"
```

### Check Port Availability
```bash
# Pattern:
lsof -i :<port>

# Example:
lsof -i :5432

# Summary:
"⚠️  Port 5432 is in use by postgres (PID 1234)"
```

### Verify File Exists
```bash
# Pattern:
[ -f /path/to/file ] && echo "exists" || echo "not found"

# Example:
[ -f /etc/nginx/nginx.conf ] && echo "exists"

# Summary:
"✓ Configuration file exists at /etc/nginx/nginx.conf"
```

### Check Disk Space
```bash
# Pattern:
df -h /path

# Example:
df -h /var/lib/docker

# Summary:
"⚠️  Docker volume is 85% full (234GB used, 42GB free)"
```

### List Recent Logs
```bash
# Pattern:
tail -n 50 /path/to/log

# Example:
tail -n 50 /var/log/nginx/error.log

# Summary:
"Last 50 log entries show 3 errors related to SSL certificates"
```

## Multi-Step Command Workflows

### Example: Diagnose Container Issue
```bash
# Step 1: List containers
docker ps -a
# → "Container 'app' is in 'Exited (137)' state"

# Step 2: Check logs
docker logs --tail 50 app
# → "Last log shows OOMKilled"

# Step 3: Check resource limits
docker inspect app --format='{{.HostConfig.Memory}}'
# → "Memory limit: 512MB"

# Summary:
"Container 'app' was killed due to OOM. Current limit: 512MB. Consider increasing to 1GB."
```

### Example: Verify Deployment
```bash
# Step 1: Check if service is up
systemctl status myapp
# → "active (running)"

# Step 2: Verify port is listening
lsof -i :8000
# → "myapp listening on :8000"

# Step 3: Test endpoint
curl -f http://localhost:8000/health
# → "HTTP 200 OK"

# Summary:
"✓ myapp is running, listening on port 8000, and health endpoint responds OK"
```

## Error Handling

### Command Not Found
```python
result = execute_terminal_command("nonexistent_cmd")

if "command not found" in result.lower():
    return "⚠️  Command 'nonexistent_cmd' is not installed. Install with: apt install <package>"
```

### Permission Denied
```python
result = execute_terminal_command("cat /etc/shadow")

if "permission denied" in result.lower():
    return "⚠️  Insufficient permissions. This requires root/sudo access."
```

### Non-Zero Exit Code
```python
result = execute_terminal_command("docker inspect nonexistent")

# Check exit code or error output
if "Error: No such object" in result:
    return "⚠️  Container 'nonexistent' not found. List containers with: docker ps -a"
```

## Propose Follow-Up Actions

After running commands, suggest next steps:

```python
# After diagnosing issue:
print("✓ Diagnosis complete: nginx config has syntax error on line 42")
print("\nSuggested follow-up steps:")
print("1. Fix syntax error in /etc/nginx/nginx.conf")
print("2. Test config: nginx -t")
print("3. Reload nginx: systemctl reload nginx")
print("4. Verify: curl -I http://localhost")
```

## Integration with Other Skills

- **File Editing**: After editing configs, test with commands (e.g., `nginx -t`)
- **Docker Operations**: Check status before/after docker compose operations
- **Observability**: Use commands to check logs, metrics, health endpoints

## Troubleshooting

**Problem**: Command hangs or takes too long
- **Solution**: Use timeouts: `timeout 10s long_running_command`
- **Solution**: Check if command is waiting for input

**Problem**: Output is unreadable (binary data)
- **Solution**: Don't `cat` binary files, use `file` to identify type first

**Problem**: Command works locally but fails in container
- **Solution**: Check if command is installed: `which <command>`
- **Solution**: Verify working directory: `pwd`

## Summary

**Safe Terminal Execution Pattern:**
1. **Explain** why the command is needed
2. **Show** the exact command
3. **Execute** with appropriate tool
4. **Summarize** results (don't dump logs)
5. **Propose** follow-up actions

**Default to read-only commands unless explicitly instructed otherwise.**


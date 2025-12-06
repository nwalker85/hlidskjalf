# RUNBOOK-025: Use Host Ollama with Apple Silicon GPU

> **Category:** AI Platform  
> **Priority:** Standard Change  
> **Last Updated:** 2025-12-03

---

## Goal

Run the Ollama LLM server directly on an Apple Silicon host (M1/M2/M3) to leverage the built‑in Metal GPU, while keeping the platform stack inside Docker. Containers reach the host instance through `host.docker.internal`.

---

## Prerequisites

- macOS on Apple Silicon (M-series)  
- [Homebrew](https://brew.sh/) installed  
- Docker Desktop 4.24+ (provides `host.docker.internal`)  
- Platform repository cloned at `~/Development/hlidskjalf`

---

## Steps

### 1. Configure the Host Ollama Daemon

Run the helper script from the repo root:

```bash
scripts/setup-host-ollama.sh
```

What it does:

1. Installs Ollama via Homebrew if missing.  
2. Writes `~/.ollama/config` with:
   ```
   ListenHost = "0.0.0.0"
   Port = "11434"
   ```
   so containers can reach the host daemon.  
3. Restarts the launchd service (or starts `ollama serve` in the background).

Verify:

```bash
curl -s http://localhost:11434/api/tags | jq .
```

### 2. Ensure Docker Containers Can Resolve the Host

Docker Desktop automatically injects `host.docker.internal`, but confirm via:

```bash
docker run --rm alpine ping -c1 host.docker.internal
```

If it fails, add `extra_hosts` entries to the affected services or upgrade Docker Desktop.

### 3. Export/Override Environment Variables

The updated `docker-compose.yml` defaults `OLLAMA_URL`/`OLLAMA_BASE_URL` to `http://host.docker.internal:11434`. If you need a different port or TLS:

```bash
export OLLAMA_URL=http://host.docker.internal:23134
export OLLAMA_BASE_URL=$OLLAMA_URL
```

### 4. Restart the Stack

```bash
docker compose up -d hlidskjalf langgraph
```

Confirm the services are hitting the host daemon in the Ollama logs (`/usr/local/var/log/ollama.log` or `log stream --predicate 'process == "ollama"'`).

### 5. (Optional) Disable the Containerised Ollama

If you no longer want the Dockerised Ollama service at all, exclude it via profiles:

```bash
docker compose --profile no-ollama up -d
```

or comment/remove the `ollama` service block if you don't need the fallback.

---

## Troubleshooting

| Symptom | Fix |
|--------|-----|
| `curl http://host.docker.internal:11434` fails in containers | Ensure Docker Desktop is up-to-date and restart it. |
| Ollama logs show `permission denied` on port 11434 | Another process is bound to the port. Stop the Dockerised Ollama (`docker compose stop ollama`). |
| UI still slow after switch | Use lighter models via the LLM Configuration modal (`llama3.1:8b`, `phi3:mini`, etc.). |
| Security concern exposing 0.0.0.0 | macOS firewall restricts access to local subnets; additionally, enable the built-in firewall or pf rule to limit inbound traffic. |

---

## References

- [Ollama Docs](https://github.com/ollama/ollama)  
- `scripts/setup-host-ollama.sh`



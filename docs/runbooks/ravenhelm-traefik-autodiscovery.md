# Ravenhelm Local Platform – Traefik Autodiscovery Setup

Runbook owner: Platform Infra  
Status: Draft (local dev workflow)  
Last updated: 2025-12-02

---

## 1. Conceptual Overview

Patterns:

- **Single edge proxy**: One Traefik container bound to `:443` on the Mac.
- **Wildcard dev domain**: `*.ravenhelm.test` → `127.0.0.1` via local DNS.
- **Per-stack Docker networks**: Each stack lives on its own Docker bridge network (custom subnet).
- **Autodiscovery via labels**: New services register themselves with Traefik using Docker labels.

Result:

1. Create a new stack.
2. Add service labels like `Host(\`gitlab.ravenhelm.test\`)`.
3. Traefik auto-wires routing—no hand-edited nginx configs.

---

## 2. Prerequisites

- macOS with Docker Desktop (or Colima/Rancher Desktop exposing the Docker API).
- Homebrew installed.
- Basic familiarity with Docker Compose.

Example folder layout:

```
~/Development/infra/
  ├── edge/                # Traefik + dnsmasq configs
  │   ├── docker-compose.yml
  │   ├── traefik.yml
  │   └── certs/
  ├── gitlab-sre/
  │   └── docker-compose.yml
  └── m2c-demo/
      └── docker-compose.yml
```

---

## 3. Configure Wildcard DNS for `*.ravenhelm.test`

### 3.1 Install dnsmasq

```bash
brew install dnsmasq
sudo mkdir -p /usr/local/etc/dnsmasq.d
sudo tee /usr/local/etc/dnsmasq.d/ravenhelm.conf >/dev/null <<'EOF'
address=/.ravenhelm.test/127.0.0.1
EOF
```

### 3.2 Start and enable dnsmasq

```bash
sudo brew services start dnsmasq
brew services list   # confirm path on Apple Silicon
```

### 3.3 macOS resolver for the test domain

```bash
sudo mkdir -p /etc/resolver
sudo tee /etc/resolver/ravenhelm.test >/dev/null <<'EOF'
nameserver 127.0.0.1
EOF
```

Validation:

```bash
scutil --dns | grep ravenhelm -A3
ping -c 1 gitlab.ravenhelm.test
```

A successful ping resolves to `127.0.0.1`.

---

## 4. Define Docker Networks (Subnets)

Model each “subnet” as a custom Docker bridge network.

- **Option A – Pre-create**:

```bash
docker network create --driver bridge --subnet 10.10.0.0/24 m2c_net
docker network create --driver bridge --subnet 10.10.0.0/24 platform_net
```

- **Option B – Declare in `edge/docker-compose.yml`**:

```yaml
networks:
  edge:
    driver: bridge
    ipam:
      config:
        - subnet: 10.0.10.0/24
  platform_net:
    external: true
  m2c_net:
    external: true
```

Traefik (edge) attaches to `edge` plus whichever project networks it must reach.

---

## 5. Traefik Edge Proxy (`edge/docker-compose.yml`)

```yaml
version: "3.9"

services:
  traefik:
    image: traefik:v3.1
    container_name: ravenhelm-traefik
    command:
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.websecure.address=:443"
      - "--api.dashboard=true"            # optional
      - "--api.insecure=true"             # dev only
      - "--log.level=INFO"
      - "--serversTransport.insecureSkipVerify=true"
    ports:
      - "443:443"
      - "8080:8080"                       # Traefik dashboard (dev)
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
      - "./certs:/certs:ro"
    networks:
      - edge
      - platform_net
      - m2c_net

networks:
  edge:
    driver: bridge
    ipam:
      config:
        - subnet: 10.0.10.0/24
  platform_net:
    external: true
  m2c_net:
    external: true
```

Notes:

- Traefik multi-homes onto each project network.
- Only :443 (and optional :8080) are exposed to macOS.
- Routing is derived from Docker labels provided by downstream services.

---

## 6. TLS Certificates for `*.ravenhelm.test`

### 6.1 Using mkcert (recommended)

```bash
brew install mkcert nss
mkcert -install

cd ~/Development/infra/edge/certs
mkcert "*.ravenhelm.test"

mv *_ravenhelm.test+*.pem fullchain.pem
mv *_ravenhelm.test+*-key.pem privkey.pem
```

Configure Traefik (e.g., `traefik.yml`) to load the cert:

```yaml
entryPoints:
  websecure:
    address: ":443"
    http:
      tls: {}

tls:
  certificates:
    - certFile: "/certs/fullchain.pem"
      keyFile: "/certs/privkey.pem"
```

One wildcard cert covers all dev hosts; rerun `mkcert` when you add new SANs.

---

## 7. Example Stack – GitLab (`gitlab.ravenhelm.test`)

`~/Development/infra/gitlab-sre/docker-compose.yml`

```yaml
version: "3.9"

services:
  gitlab:
    image: gitlab/gitlab-ce:latest
    container_name: gitlab-ce
    hostname: gitlab.ravenhelm.test
    environment:
      GITLAB_OMNIBUS_CONFIG: |
        external_url "https://gitlab.ravenhelm.test"
    shm_size: "256m"
    networks:
      - platform_net
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.gitlab.rule=Host(`gitlab.ravenhelm.test`)"
      - "traefik.http.routers.gitlab.entrypoints=websecure"
      - "traefik.http.routers.gitlab.tls=true"
      - "traefik.http.services.gitlab.loadbalancer.server.port=80"

networks:
  platform_net:
    external: true
```

Startup sequence:

```bash
cd ~/Development/infra/edge && docker compose up -d
cd ../gitlab-sre           && docker compose up -d
```

Browse to `https://gitlab.ravenhelm.test`.

---

## 8. Example Stack – M2C Demo (`m2c.ravenhelm.test`)

`~/Development/infra/m2c-demo/docker-compose.yml`

```yaml
version: "3.9"

services:
  m2c-api:
    image: ravenhelm/m2c-api:dev
    container_name: m2c-api
    networks:
      - m2c_net
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.m2c.rule=Host(`m2c.ravenhelm.test`)"
      - "traefik.http.routers.m2c.entrypoints=websecure"
      - "traefik.http.routers.m2c.tls=true"
      - "traefik.http.services.m2c.loadbalancer.server.port=8080"

networks:
  m2c_net:
    external: true
```

No host ports exposed; Traefik handles ingress.

---

## 9. Adding a New Stack (`foo.ravenhelm.test`)

1. **Create a network** (if needed):

```bash
docker network create --driver bridge --subnet 10.30.0.0/24 foo_net
```

2. **Attach Traefik to the network**:

```yaml
networks:
  ...
  foo_net:
    external: true
```

Then redeploy the edge stack:

```bash
cd ~/Development/infra/edge
docker compose up -d
```

3. **Define the app with labels**:

```yaml
services:
  foo-api:
    image: ravenhelm/foo-api:dev
    networks:
      - foo_net
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.foo.rule=Host(`foo.ravenhelm.test`)"
      - "traefik.http.routers.foo.entrypoints=websecure"
      - "traefik.http.routers.foo.tls=true"
      - "traefik.http.services.foo.loadbalancer.server.port=8000"

networks:
  foo_net:
    external: true
```

4. **Bring the stack up**:

```bash
docker compose up -d
```

5. Visit `https://foo.ravenhelm.test`.

---

## 10. Troubleshooting Checklist

- **DNS resolution**  
  `dig gitlab.ravenhelm.test` should return `127.0.0.1`. If not, re-check `/etc/resolver/ravenhelm.test` and dnsmasq status.

- **Traefik discovery issues**  
  Ensure the Docker socket is mounted (`/var/run/docker.sock:/var/run/docker.sock:ro`). Review logs with `docker logs ravenhelm-traefik`.

- **404 / 502 responses**  
  Verify label spelling (`router`, `service`, `server.port`). Confirm the backend container is healthy and listening on the declared internal port.

- **SSL warnings**  
  Confirm `fullchain.pem`/`privkey.pem` exist under `edge/certs` and that `mkcert -install` was executed on the host so macOS trusts the CA.

---

## 11. Future Enhancements

- Split Traefik static vs. dynamic config (YAML) for cleaner version control.
- Add middleware (basic auth, IP allowlists) for sensitive dev services.
- Maintain a lightweight “stack registry” to auto-generate network names/subnets.
- Introduce LocalStack on a dedicated network to emulate AWS services for CI/CD.
- Mirror this runbook into Notion (Knowledge Base → Platform → Networking) for broader visibility.

---

**Mental Model**: Traefik is the front door; Docker networks are subnets; labels are wiring instructions; `*.ravenhelm.test` is the universe you control.


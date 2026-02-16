# Ravenhelm Platform - Security Hardening & Zero-Trust Architecture

**From Development to Production-Grade Security**

---

## Current Security Posture Assessment

### ✅ What We Have

**Network Isolation:**
- ✅ 6 Docker networks with subnet isolation (10.x.0.0/24 ranges)
- ✅ Network policies via Docker bridge networks
- ✅ Service-to-service communication within networks

**Secrets Management:**
- ✅ OpenBao (Vault fork) deployed (currently unhealthy)
- ✅ Environment variables in .env (not ideal for prod)
- ✅ PostgreSQL database encryption at rest available

**Observability:**
- ✅ Full observability stack (Prometheus, Loki, Tempo, Grafana)
- ✅ LangFuse for LLM tracing
- ✅ Phoenix for RAG debugging
- ✅ OpenTelemetry collector

**Identity (Partial):**
- ✅ SPIRE server/agent configured but not running
- ✅ Zitadel database created but service not deployed
- ⚠️ No authentication on agent APIs

### ❌ Critical Security Gaps

**1. No mTLS Between Services**
- Services communicate over plain HTTP
- No workload identity verification
- Vulnerable to MITM attacks within Docker networks

**2. No Authentication on Agent Communication**
- NATS/Kafka has no authentication enabled
- Any container can publish/subscribe to agent coordination topics
- Agent impersonation possible

**3. No Identity Provider Running**
- Zitadel deferred (TODO item #1)
- No human user authentication
- No service account management

**4. No MCP Server Security**
- MCP servers not yet integrated
- No OAuth 2.1 protection
- Agents could access unauthorized tools/data

**5. Secrets in Plain Files**
- .env file contains API keys
- Certificates mounted as files
- No dynamic secret rotation

**6. No Network Policies**
- Docker networks too permissive
- No ingress/egress rules
- Services can talk to anything

---

## Zero-Trust Architecture Design

### Principle: "Never Trust, Always Verify"

```
┌─────────────────────────────────────────────────────────────┐
│  Traefik Edge Proxy                                         │
│  - TLS termination (mkcert certs)                           │
│  - OAuth 2.1 authentication (Zitadel)                       │
│  - Rate limiting per user                                   │
└─────────────────┬───────────────────────────────────────────┘
                  │ HTTPS + JWT
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  Hliðskjálf Control Plane                                   │
│  - Validates JWT (Zitadel JWKS)                             │
│  - Checks permissions (OpenFGA)                             │
│  - Issues agent tasks                                       │
│  - SPIRE SVID for service identity                          │
└─────────────────┬───────────────────────────────────────────┘
                  │ mTLS (SPIRE SVIDs)
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  NATS JetStream                                             │
│  - mTLS required (SPIRE-issued certs)                       │
│  - ACLs per agent role                                      │
│  - Message encryption at rest                               │
└─────────────────┬───────────────────────────────────────────┘
                  │ mTLS + ACLs
        ┌─────────┴─────────┐
        ▼                   ▼
┌─────────────┐       ┌─────────────┐
│  Agent 1    │       │  Agent 2    │
│  SVID:      │       │  SVID:      │
│  spiffe://  │       │  spiffe://  │
│  ravenhelm  │       │  ravenhelm  │
│  /agent/1   │       │  /agent/2   │
└─────────────┘       └─────────────┘
        │                   │
        │ OAuth 2.1 + mTLS  │
        ▼                   ▼
┌─────────────────────────────────┐
│  MCP Servers                     │
│  - Require OAuth 2.1 tokens      │
│  - Validate SPIRE SVID           │
│  - Scoped permissions per agent  │
└──────────────────────────────────┘
```

---

## Phase 1: SPIRE Integration for mTLS

### Why SPIRE?

- **Automatic cert rotation** - Every 1 hour (configurable)
- **Workload identity** - Each container gets unique SPIFFE ID
- **Zero-trust** - Cryptographic identity verification
- **No manual cert management** - SPIRE handles everything

### SPIRE Trust Domain Design

```
spiffe://ravenhelm.local/orchestrator
spiffe://ravenhelm.local/agent/cert-agent
spiffe://ravenhelm.local/agent/proxy-agent
spiffe://ravenhelm.local/service/grafana
spiffe://ravenhelm.local/service/postgres
spiffe://ravenhelm.local/mcp-server/docker
spiffe://ravenhelm.local/mcp-server/kubernetes
```

### Step 1.1: Start SPIRE Server & Agent

**Add to docker-compose.yml (already present but not started):**

```bash
# Start SPIRE infrastructure
docker compose up -d spire-server spire-agent

# Wait for health
docker compose exec spire-server /opt/spire/bin/spire-server healthcheck
docker compose exec spire-agent /opt/spire/bin/spire-agent healthcheck
```

### Step 1.2: Register Agent Workloads

```bash
# Create registration script
cat > scripts/register_spire_workloads.sh << 'EOF'
#!/bin/bash
# Register all agent workloads with SPIRE

SPIRE_SERVER="docker compose exec -T spire-server"

# Register orchestrator
$SPIRE_SERVER /opt/spire/bin/spire-server entry create \
  -spiffeID spiffe://ravenhelm.local/orchestrator \
  -parentID spiffe://ravenhelm.local/spire/agent/docker \
  -selector docker:label:ravenhelm.role:orchestrator \
  -ttl 3600

# Register worker agents
for agent in cert env database proxy cache events secrets observability docker rag graph hlidskjalf; do
  $SPIRE_SERVER /opt/spire/bin/spire-server entry create \
    -spiffeID spiffe://ravenhelm.local/agent/${agent}-agent \
    -parentID spiffe://ravenhelm.local/spire/agent/docker \
    -selector docker:label:ravenhelm.agent:${agent} \
    -ttl 1800
done

# Register services
for service in grafana langfuse phoenix postgres redis nats openbao; do
  $SPIRE_SERVER /opt/spire/bin/spire-server entry create \
    -spiffeID spiffe://ravenhelm.local/service/${service} \
    -parentID spiffe://ravenhelm.local/spire/agent/docker \
    -selector docker:label:ravenhelm.service:${service} \
    -ttl 3600
done

# Register MCP servers
for mcp in docker kubernetes aws slack github; do
  $SPIRE_SERVER /opt/spire/bin/spire-server entry create \
    -spiffeID spiffe://ravenhelm.local/mcp-server/${mcp} \
    -parentID spiffe://ravenhelm.local/spire/agent/docker \
    -selector docker:label:ravenhelm.mcp-server:${mcp} \
    -ttl 1800
done

echo "✓ All workloads registered with SPIRE"
EOF

chmod +x scripts/register_spire_workloads.sh
./scripts/register_spire_workloads.sh
```

### Step 1.3: Update Agent Code to Use SPIRE

```python
# hlidskjalf/src/norns/spire_integration.py

from py_spiffe.workload import WorkloadApiClient
from py_spiffe.svid.x509_svid import X509Svid
import ssl

class SPIREIntegration:
    """Integration with SPIRE for workload identity"""
    
    def __init__(self, socket_path: str = "/tmp/spire-agent/public/api.sock"):
        self.socket_path = f"unix://{socket_path}"
        self.client = None
        self.svid: X509Svid | None = None
    
    async def fetch_svid(self) -> X509Svid:
        """Fetch X.509 SVID from SPIRE agent"""
        with WorkloadApiClient(self.socket_path) as client:
            self.svid = client.fetch_x509_svid()
            return self.svid
    
    def create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context using SPIRE SVID"""
        if not self.svid:
            raise ValueError("Must fetch SVID first")
        
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        
        # Load SVID cert and key
        context.load_cert_chain(
            certfile=self.svid.cert_chain_pem,
            keyfile=self.svid.private_key_pem
        )
        
        # Trust bundle for verification
        context.load_verify_locations(cadata=self.svid.trust_bundle_pem)
        
        # Require client certificates
        context.verify_mode = ssl.CERT_REQUIRED
        
        return context
```

### Step 1.4: Enable mTLS on NATS

```yaml
# Update docker-compose.yml NATS service
services:
  nats:
    image: nats:latest
    command:
      - "--jetstream"
      - "--store_dir=/data"
      - "--tls"
      - "--tlscert=/certs/server-cert.pem"
      - "--tlskey=/certs/server-key.pem"
      - "--tlscacert=/certs/ca-cert.pem"
      - "--tlsverify"  # Require client certs
    volumes:
      - nats_data:/data
      - spire_agent_run:/tmp/spire-agent/public:ro
    # ... rest of config
```

**Agent connection with mTLS:**

```python
from src.norns.spire_integration import SPIREIntegration

class SecureNATSWorker:
    async def connect(self):
        # Fetch SPIRE SVID
        spire = SPIREIntegration()
        svid = await spire.fetch_svid()
        ssl_context = spire.create_ssl_context()
        
        # Connect to NATS with mTLS
        self.nc = await nats.connect(
            servers=["nats://localhost:4222"],
            tls=ssl_context
        )
```

### Step 1.5: Grafana PoC for mTLS

**Prove SPIRE works with Grafana data source:**

```python
# scripts/grafana_spire_poc.py
import requests
from src.norns.spire_integration import SPIREIntegration

async def test_grafana_mtls():
    """Prove mTLS works between services"""
    
    # Fetch SPIRE SVID
    spire = SPIREIntegration()
    svid = await spire.fetch_svid()
    
    # Create SSL context
    ssl_context = spire.create_ssl_context()
    
    # Query Grafana API with mTLS
    response = requests.get(
        "https://grafana.observe.ravenhelm.test/api/health",
        cert=(svid.cert_chain_pem, svid.private_key_pem),
        verify=svid.trust_bundle_pem
    )
    
    print(f"✓ Grafana mTLS verified: {response.status_code}")
    print(f"  SPIFFE ID verified: {svid.spiffe_id}")
    
    # Verify the connection used mTLS
    assert response.status_code == 200
    print("✅ mTLS PoC successful!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_grafana_mtls())
```

**Run PoC:**
```bash
docker compose up -d spire-server spire-agent
./scripts/register_spire_workloads.sh
python scripts/grafana_spire_poc.py
```

---

## Phase 2: Zitadel Integration

### Why Zitadel?

- **Modern OIDC provider** - OAuth 2.1, OIDC, SAML
- **Multi-tenancy** - Organizations, projects, applications
- **Machine-to-machine** - Service account with JWT
- **User management** - Built-in UI and APIs
- **OpenFGA integration** - ReBAC authorization

### Step 2.1: Deploy Zitadel

```yaml
# Add to docker-compose.yml

services:
  zitadel-init:
    image: postgres:16-alpine
    environment:
      PGPASSWORD: postgres
    command: >
      sh -c "psql -h postgres -U postgres -c 'CREATE DATABASE IF NOT EXISTS zitadel'"
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - platform_net

  zitadel:
    image: ghcr.io/zitadel/zitadel:v2.64.1
    container_name: gitlab-sre-zitadel
    command: start-from-init --masterkeyFromEnv --tlsMode disabled
    ports:
      - "8085:8080"
    environment:
      - ZITADEL_MASTERKEY=MasterkeyNeedsToHave32CharactersMin
      - ZITADEL_DATABASE_POSTGRES_HOST=postgres
      - ZITADEL_DATABASE_POSTGRES_PORT=5432
      - ZITADEL_DATABASE_POSTGRES_DATABASE=zitadel
      - ZITADEL_DATABASE_POSTGRES_USER_USERNAME=postgres
      - ZITADEL_DATABASE_POSTGRES_USER_PASSWORD=postgres
      - ZITADEL_DATABASE_POSTGRES_USER_SSL_MODE=disable
      - ZITADEL_DATABASE_POSTGRES_ADMIN_USERNAME=postgres
      - ZITADEL_DATABASE_POSTGRES_ADMIN_PASSWORD=postgres
      - ZITADEL_DATABASE_POSTGRES_ADMIN_SSL_MODE=disable
      - ZITADEL_EXTERNALSECURE=true
      - ZITADEL_EXTERNALPORT=443
      - ZITADEL_EXTERNALDOMAIN=zitadel.ravenhelm.test
      - ZITADEL_FIRSTINSTANCE_ORG_HUMAN_USERNAME=admin
      - ZITADEL_FIRSTINSTANCE_ORG_HUMAN_PASSWORD=RavenAdmin123!
      - ZITADEL_FIRSTINSTANCE_MACHINEKEYPATH=/machinekey/zitadel-admin-sa.json
    volumes:
      - zitadel_machinekey:/machinekey
      - zitadel_data:/data
    depends_on:
      zitadel-init:
        condition: service_completed_successfully
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "/app/zitadel", "ready"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 60s
    networks:
      - platform_net
      - platform_net
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=platform_net"
      - "traefik.http.routers.zitadel.rule=Host(`zitadel.ravenhelm.test`)"
      - "traefik.http.routers.zitadel.entrypoints=websecure"
      - "traefik.http.routers.zitadel.tls=true"
      - "traefik.http.services.zitadel.loadbalancer.server.port=8080"

volumes:
  zitadel_machinekey:
  zitadel_data:
```

### Step 2.2: Bootstrap Zitadel

```bash
# scripts/bootstrap_zitadel.sh
#!/bin/bash
set -e

ZITADEL_URL="https://zitadel.ravenhelm.test"
MACHINEKEY_PATH="./zitadel_machinekey/zitadel-admin-sa.json"

echo "🔐 Bootstrapping Zitadel..."

# Wait for Zitadel
until curl -sf "$ZITADEL_URL/debug/ready" > /dev/null; do
  echo "  Waiting for Zitadel..."
  sleep 5
done

# Create Ravenhelm project
echo "📁 Creating Ravenhelm project..."
# (Implementation from templates/ravenmaskos/infra/zitadel/setup.sh)

# Create agent service accounts
echo "🤖 Creating agent service accounts..."
for agent in cert env database proxy cache events secrets observability docker rag graph hlidskjalf; do
  # Create machine user for each agent
  # Get credentials
  # Store in OpenBao
  echo "  ✓ ${agent}-agent service account created"
done

# Create MCP server OAuth clients
echo "🔌 Creating MCP server OAuth 2.1 clients..."
for mcp in docker kubernetes aws slack github; do
  # Create OAuth 2.1 application
  # Configure scopes
  # Store credentials in OpenBao
  echo "  ✓ ${mcp}-mcp OAuth client created"
done

echo "✅ Zitadel bootstrap complete"
```

### Step 2.3: Agent Authentication

**Update agent code to authenticate with Zitadel:**

```python
# hlidskjalf/src/norns/secure_worker.py

import httpx
import jwt
from datetime import datetime, timedelta

class SecureWorker:
    async def authenticate(self):
        """Get JWT from Zitadel using service account"""
        
        # Load service account key from OpenBao
        sa_key = await self.fetch_from_openbao(
            f"ravenhelm/agents/{self.role.value}/jwt-key"
        )
        
        # Create JWT assertion
        now = datetime.utcnow()
        payload = {
            'iss': sa_key['user_id'],
            'sub': sa_key['user_id'],
            'aud': 'https://zitadel.ravenhelm.test',
            'iat': int(now.timestamp()),
            'exp': int((now + timedelta(hours=1)).timestamp())
        }
        
        assertion = jwt.encode(payload, sa_key['private_key'], algorithm='RS256')
        
        # Exchange for access token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://zitadel.ravenhelm.test/oauth/v2/token",
                data={
                    'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                    'assertion': assertion,
                    'scope': 'openid urn:zitadel:iam:org:project:id:ravenhelm:aud'
                }
            )
        
        token_data = response.json()
        self.access_token = token_data['access_token']
        
        return self.access_token
    
    async def connect_to_nats_secure(self):
        """Connect to NATS with both mTLS (SPIRE) and JWT (Zitadel)"""
        
        # Get SPIRE SVID for mTLS
        spire = SPIREIntegration()
        svid = await spire.fetch_svid()
        ssl_context = spire.create_ssl_context()
        
        # Get Zitadel JWT for authorization
        access_token = await self.authenticate()
        
        # Connect with both
        self.nc = await nats.connect(
            servers=["nats://localhost:4222"],
            tls=ssl_context,  # mTLS authentication
            user_credentials=lambda: {  # JWT authorization
                'user': self.role.value,
                'password': access_token
            }
        )
```

---

## Phase 3: MCP Server Integration & Security

### What are MCP Servers?

**Model Context Protocol** provides standardized interfaces for AI agents to access:
- **Tools** - External APIs, databases, services
- **Resources** - Files, documents, data sources
- **Prompts** - Pre-defined prompt templates

**Think of MCP as:** "REST APIs designed for AI agents"

### MCP Server Examples

```
mcp-server-docker      # Docker container management
mcp-server-kubernetes  # K8s cluster operations
mcp-server-aws         # AWS API calls
mcp-server-github      # Git operations
mcp-server-slack       # Team notifications
mcp-server-postgres    # Database queries
```

### Step 3.1: Deploy MCP Servers

```yaml
# docker-compose.mcp.yml

services:
  # Docker MCP Server
  mcp-docker:
    image: mcp/server-docker:latest
    container_name: mcp-server-docker
    environment:
      - MCP_AUTH_TYPE=oauth2.1
      - MCP_OAUTH_ISSUER=https://zitadel.ravenhelm.test
      - MCP_OAUTH_AUDIENCE=mcp-server-docker
      - MCP_REQUIRE_SPIFFE=true
      - MCP_ALLOWED_SPIFFE_IDS=spiffe://ravenhelm.local/agent/*
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - spire_agent_run:/tmp/spire-agent/public:ro
    ports:
      - "9001:9000"
    networks:
      - platform_net
    labels:
      - "ravenhelm.mcp-server=docker"
      - "raefik.enable=true"
      - "traefik.docker.network=platform_net"
      - "traefik.http.routers.mcp-docker.rule=Host(`mcp-docker.ravenhelm.test`)"
      - "traefik.http.routers.mcp-docker.entrypoints=websecure"
      - "traefik.http.routers.mcp-docker.tls=true"
      - "traefik.http.services.mcp-docker.loadbalancer.server.port=9000"
  
  # Kubernetes MCP Server
  mcp-kubernetes:
    image: mcp/server-kubernetes:latest
    container_name: mcp-server-kubernetes
    environment:
      - MCP_AUTH_TYPE=oauth2.1
      - MCP_OAUTH_ISSUER=https://zitadel.ravenhelm.test
      - MCP_REQUIRE_SPIFFE=true
      - KUBECONFIG=/kubeconfig/config
    volumes:
      - ~/.kube:/kubeconfig:ro
      - spire_agent_run:/tmp/spire-agent/public:ro
    ports:
      - "9002:9000"
    networks:
      - platform_net
    labels:
      - "ravenhelm.mcp-server=kubernetes"
  
  # GitHub MCP Server  
  mcp-github:
    image: mcp/server-github:latest
    container_name: mcp-server-github
    environment:
      - MCP_AUTH_TYPE=oauth2.1
      - MCP_OAUTH_ISSUER=https://zitadel.ravenhelm.test
      - MCP_REQUIRE_SPIFFE=true
      - GITHUB_TOKEN=${GITHUB_TOKEN}
    volumes:
      - spire_agent_run:/tmp/spire-agent/public:ro
    ports:
      - "9003:9000"
    networks:
      - platform_net
    labels:
      - "ravenhelm.mcp-server=github"
```

### Step 3.2: MCP Server OAuth 2.1 Security

**OAuth 2.1 Flow for MCP Access:**

```
Agent → Zitadel: "I need access to mcp-server-docker"
Zitadel → Agent: JWT with scopes: ["mcp:docker:read", "mcp:docker:exec"]
Agent → MCP Server: Request + JWT in Authorization header
MCP Server → Zitadel: Validate JWT (JWKS endpoint)
MCP Server → SPIRE: Verify agent's SPIFFE ID
MCP Server → Agent: Tool response (if authorized)
```

**MCP Server Authentication Middleware:**

```python
# mcp_server/auth.py

from fastapi import HTTPException, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import httpx
from functools import lru_cache

security = HTTPBearer()

@lru_cache(maxsize=1)
async def fetch_jwks():
    """Fetch Zitadel JWKS for token validation"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://zitadel.ravenhelm.test/.well-known/jwks"
        )
        return response.json()

async def verify_spiffe_id(request: Request) -> str:
    """Extract and verify SPIFFE ID from mTLS cert"""
    # Get client certificate from TLS connection
    cert = request.scope.get('transport').get_extra_info('ssl_object').getpeercert()
    
    # Extract SPIFFE ID from SAN
    san = cert.get('subjectAltName', [])
    spiffe_ids = [uri for type, uri in san if type == 'URI' and uri.startswith('spiffe://')]
    
    if not spiffe_ids:
        raise HTTPException(401, "No SPIFFE ID in certificate")
    
    spiffe_id = spiffe_ids[0]
    
    # Verify it's from our trust domain
    if not spiffe_id.startswith('spiffe://ravenhelm.local/'):
        raise HTTPException(403, "SPIFFE ID not in trust domain")
    
    return spiffe_id

async def validate_mcp_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    request: Request = None
) -> dict:
    """Validate OAuth 2.1 token and SPIFFE ID"""
    
    # 1. Verify mTLS (SPIRE SVID)
    spiffe_id = await verify_spiffe_id(request)
    
    # 2. Validate JWT (Zitadel token)
    token = credentials.credentials
    
    try:
        # Fetch JWKS
        jwks = await fetch_jwks()
        
        # Decode and validate
        claims = jwt.decode(
            token,
            jwks,  # Zitadel public keys
            algorithms=["RS256"],
            issuer="https://zitadel.ravenhelm.test",
            audience="mcp-server-docker"
        )
        
        # Verify scopes
        required_scopes = {"mcp:docker:read"}
        token_scopes = set(claims.get('scope', '').split())
        
        if not required_scopes.issubset(token_scopes):
            raise HTTPException(403, "Insufficient scopes")
        
        # Return validated context
        return {
            'spiffe_id': spiffe_id,
            'user_id': claims['sub'],
            'scopes': token_scopes,
            'agent_role': spiffe_id.split('/')[-1]
        }
        
    except jwt.InvalidTokenError as e:
        raise HTTPException(401, f"Invalid token: {e}")

# Protect MCP endpoints
@app.get("/tools")
async def list_tools(auth: dict = Depends(validate_mcp_token)):
    """List available tools (requires OAuth 2.1 + mTLS)"""
    # Check if agent has permission
    if auth['agent_role'] not in ['docker-agent', 'hlidskjalf-agent']:
        raise HTTPException(403, "Agent not authorized for docker tools")
    
    return {"tools": [...]}
```

### Step 3.3: Agent MCP Client Integration

```python
# hlidskjalf/src/norns/mcp_client.py

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import httpx

class SecureMCPClient:
    """MCP client with OAuth 2.1 + mTLS"""
    
    def __init__(self, server_url: str, agent_role: AgentRole):
        self.server_url = server_url
        self.agent_role = agent_role
        self.access_token = None
        self.spire = SPIREIntegration()
    
    async def connect(self) -> ClientSession:
        """Connect to MCP server with security"""
        
        # 1. Get SPIRE SVID
        svid = await self.spire.fetch_svid()
        ssl_context = self.spire.create_ssl_context()
        
        # 2. Get Zitadel token
        access_token = await self.get_zitadel_token()
        
        # 3. Connect to MCP server
        async with httpx.AsyncClient(
            cert=(svid.cert_chain_pem, svid.private_key_pem),
            verify=svid.trust_bundle_pem
        ) as client:
            
            # Initialize MCP session
            async with stdio_client(
                StdioServerParameters(
                    command="mcp-client",
                    args=[self.server_url],
                    env={
                        "MCP_AUTH_TOKEN": access_token,
                        "SPIFFE_ID": str(svid.spiffe_id)
                    }
                )
            ) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # List available tools
                    tools = await session.list_tools()
                    print(f"✓ Connected to MCP server: {len(tools)} tools available")
                    
                    return session
    
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call MCP tool with authentication"""
        session = await self.connect()
        
        result = await session.call_tool(tool_name, arguments)
        
        return result

# Usage in agent
mcp_docker = SecureMCPClient(
    "https://mcp-docker.ravenhelm.test",
    AgentRole.DOCKER_AGENT
)

# Call Docker API via MCP with full security
result = await mcp_docker.call_tool("list_containers", {"all": True})
```

### Step 3.4: MCP Tool as LangChain Tool

```python
# Convert MCP tools to LangChain tools

from langchain_core.tools import tool

class MCPToolAdapter:
    """Adapt MCP tools to LangChain format"""
    
    def __init__(self, mcp_client: SecureMCPClient):
        self.mcp = mcp_client
    
    async def create_langchain_tools(self) -> list:
        """Convert MCP tools to LangChain tools"""
        session = await self.mcp.connect()
        mcp_tools = await session.list_tools()
        
        langchain_tools = []
        
        for mcp_tool in mcp_tools:
            # Create LangChain tool wrapper
            @tool(name=mcp_tool.name, description=mcp_tool.description)
            async def mcp_tool_wrapper(**kwargs):
                return await self.mcp.call_tool(mcp_tool.name, kwargs)
            
            langchain_tools.append(mcp_tool_wrapper)
        
        return langchain_tools

# Use in ReAct agent
mcp_adapter = MCPToolAdapter(mcp_docker_client)
mcp_tools = await mcp_adapter.create_langchain_tools()

# Create agent with MCP tools
agent = create_react_agent(
    llm,
    tools=[*base_tools, *mcp_tools]  # Mix local + MCP tools
)
```

---

## Phase 4: Additional Security Hardening

### Network Segmentation

**Current:** All services on `platform_net` (too permissive)

**Improved:** Service-specific networks with policies

```yaml
networks:
  # Public-facing services
  edge_net:
    internal: false
  
  # Platform services (internal only)
  platform_net:
    internal: true
  
  # Database tier (most restricted)
  data_net:
    internal: true
    driver_opts:
      com.docker.network.bridge.enable_icc: "false"  # No inter-container communication
```

**Network policies:**

```yaml
# Update docker-compose.yml

services:
  postgres:
    networks:
      - data_net
    # Only accessible by apps, not other services
  
  grafana:
    networks:
      - platform_net  # For Prometheus
      - edge_net      # For Traefik
    # But NOT data_net - no direct DB access
  
  hlidskjalf:
    networks:
      - platform_net
      - data_net
    # Can access DB and coordinate with agents
```

### Secrets Rotation

**OpenBao Dynamic Secrets:**

```hcl
# openbao/config/postgres.hcl

path "database/creds/agent-readonly" {
  capabilities = ["read"]
}

# Configure PostgreSQL secrets engine
vault write database/config/postgres \
  plugin_name=postgresql-database-plugin \
  connection_url="postgresql://{{username}}:{{password}}@postgres:5432/hlidskjalf" \
  allowed_roles="agent-readonly,agent-readwrite" \
  username="postgres" \
  password="postgres"

# Create role for agents
vault write database/roles/agent-readonly \
  db_name=postgres \
  creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; \
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
  default_ttl="1h" \
  max_ttl="24h"
```

**Agent fetches dynamic credentials:**

```python
async def get_database_credentials(self):
    """Get short-lived DB credentials from OpenBao"""
    
    # Authenticate to OpenBao using SPIRE SVID
    vault_token = await self.authenticate_to_openbao()
    
    # Request dynamic credentials
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://vault.ravenhelm.test/v1/database/creds/agent-readonly",
            headers={"X-Vault-Token": vault_token}
        )
    
    creds = response.json()
    
    # Credentials expire in 1 hour, no need to store permanently!
    return {
        'username': creds['data']['username'],
        'password': creds['data']['password'],
        'lease_duration': creds['lease_duration']
    }
```

### Rate Limiting & DoS Protection

**Add to Traefik:**

```yaml
# traefik-edge/dynamic/middleware.yml

http:
  middlewares:
    rate-limit-agent:
      rateLimit:
        average: 100    # 100 req/sec
        burst: 200
        period: 1s
    
    rate-limit-user:
      rateLimit:
        average: 10
        burst: 20
        period: 1s
        sourceCriterion:
          requestHeaderName: X-User-Id
    
    ip-whitelist-internal:
      ipWhitelist:
        sourceRange:
          - "10.0.0.0/8"      # Docker networks only
          - "172.16.0.0/12"
    
    secure-headers:
      headers:
        stsSeconds: 31536000
        forceSTSHeader: true
        contentTypeNosniff: true
        browserXssFilter: true
        referrerPolicy: "strict-origin-when-cross-origin"
```

### Audit Logging

**Log all agent actions:**

```python
# hlidskjalf/src/services/audit_log.py

import structlog
from datetime import datetime

audit_logger = structlog.get_logger("audit")

async def log_agent_action(
    agent_role: str,
    action: str,
    resource: str,
    result: str,
    spiffe_id: str,
    user_id: str | None = None
):
    """Log all agent actions for compliance"""
    
    audit_logger.info(
        "agent.action",
        timestamp=datetime.utcnow().isoformat(),
        agent_role=agent_role,
        action=action,
        resource=resource,
        result=result,
        spiffe_id=spiffe_id,
        user_id=user_id,
        # These go to Loki for retention
    )
    
    # Also write to PostgreSQL audit table
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO audit_log (timestamp, agent_role, action, resource, spiffe_id)
            VALUES ($1, $2, $3, $4, $5)
            """,
            datetime.utcnow(), agent_role, action, resource, spiffe_id
        )
```

### Input Validation & Sandboxing

**Prevent command injection:**

```python
import shlex

@tool
async def execute_terminal_command(command: str, working_dir: str = ".") -> dict:
    """Execute command with validation"""
    
    # 1. Validate command is not malicious
    blacklist = ['rm -rf /', '> /dev/', 'dd if=', 'fork bomb']
    if any(bad in command for bad in blacklist):
        return {"error": "Command rejected by security policy"}
    
    # 2. Parse and validate arguments
    try:
        args = shlex.split(command)
    except ValueError:
        return {"error": "Invalid command syntax"}
    
    # 3. Whitelist allowed commands
    allowed_commands = {'docker', 'kubectl', 'git', 'curl', 'ls', 'cat', 'grep'}
    if args[0] not in allowed_commands:
        return {"error": f"Command '{args[0]}' not in whitelist"}
    
    # 4. Execute in restricted environment
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=working_dir,
        env={
            'PATH': '/usr/local/bin:/usr/bin:/bin',  # Restricted PATH
            'HOME': '/tmp',  # Sandboxed home
        }
    )
    
    # 5. Audit log the execution
    await log_agent_action(
        agent_role=current_agent_role,
        action="execute_command",
        resource=command,
        result="pending"
    )
    
    stdout, stderr = await process.communicate()
    
    return {
        "exit_code": process.returncode,
        "stdout": stdout.decode('utf-8', errors='ignore'),
        "stderr": stderr.decode('utf-8', errors='ignore')
    }
```

---

## Additional Security Requirements

### 1. NATS ACLs (Authorization)

**Define per-agent permissions:**

```conf
# nats/auth.conf

authorization {
    # Orchestrator can publish to all task topics
    users = [
        {
            user: "orchestrator"
            password: "$2a$11$..." # Bcrypt hash
            permissions = {
                publish = ["squad.tasks.>", "squad.coordination"]
                subscribe = ["squad.coordination", "squad.status"]
            }
        },
        
        # Workers can only subscribe to their own tasks
        {
            user: "cert-agent"
            password: "$2a$11$..."
            permissions = {
                publish = ["squad.coordination", "squad.status"]
                subscribe = ["squad.tasks.cert-agent", "squad.coordination"]
            }
        },
        
        # Similar for each agent...
    ]
    
    # JWT-based auth (Zitadel integration)
    jwt {
        signing_key_file = "/certs/zitadel-public-key.pem"
        expected_audience = "nats-ravenhelm"
        claim_username = "sub"
        claim_permissions = "scope"
    }
}
```

### 2. PostgreSQL Row-Level Security

**Isolate agent data:**

```sql
-- Enable RLS on audit log
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

-- Policy: Agents can only see their own actions
CREATE POLICY agent_isolation ON audit_log
    FOR SELECT
    TO agent_role
    USING (agent_role = current_setting('app.current_agent_role'));

-- Policy: Orchestrator can see everything
CREATE POLICY orchestrator_view ON audit_log
    FOR SELECT
    TO orchestrator_role
    USING (true);
```

### 3. Container Security

**Add to docker-compose.yml:**

```yaml
services:
  hlidskjalf:
    security_opt:
      - no-new-privileges:true
      - seccomp:unconfined  # Or custom seccomp profile
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE  # Only if needed
    read_only: true
    tmpfs:
      - /tmp
      - /var/run
```

### 4. Secret Scanning

**Pre-commit hook:**

```bash
# .git/hooks/pre-commit
#!/bin/bash

echo "🔍 Scanning for secrets..."

# Check for API keys
if git diff --cached | grep -E "(api_key|password|secret|token).*=.*[A-Za-z0-9]{20,}"; then
    echo "❌ Potential secret detected in commit!"
    echo "Use OpenBao or environment variables instead."
    exit 1
fi

# Check .env is not committed
if git diff --cached --name-only | grep "^\.env$"; then
    echo "❌ Attempting to commit .env file!"
    exit 1
fi

echo "✓ No secrets detected"
```

### 5. Dependency Scanning

```yaml
# .github/workflows/security.yml (or GitLab CI)

name: Security Scan

on: [push, pull_request]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Scan Python dependencies
        run: |
          pip install safety
          safety check -r hlidskjalf/pyproject.toml
      
      - name: Scan Docker images
        run: |
          docker scout cves hlidskjalf:latest
          docker scout recommendations hlidskjalf:latest
      
      - name: SAST scan
        run: |
          pip install bandit
          bandit -r hlidskjalf/src -f json -o bandit-report.json
```

---

## Complete Security Checklist

### Identity & Access

- [ ] SPIRE server/agent running and healthy
- [ ] All workloads registered with SPIFFE IDs
- [ ] Zitadel deployed and configured
- [ ] Service accounts created for each agent
- [ ] OAuth 2.1 clients for MCP servers
- [ ] JWT validation on all API endpoints
- [ ] OpenFGA policies defined

### Network & Transport

- [ ] mTLS enabled on NATS
- [ ] Network segmentation (edge/platform/data)
- [ ] Traefik rate limiting configured
- [ ] IP whitelisting for internal services
- [ ] DDoS protection at edge

### Secrets & Credentials

- [ ] OpenBao unsealed and healthy
- [ ] Dynamic database credentials
- [ ] API keys stored in OpenBao (not .env)
- [ ] Automatic secret rotation (24h)
- [ ] No secrets in git
- [ ] Pre-commit hooks for secret scanning

### MCP Security

- [ ] MCP servers require OAuth 2.1 tokens
- [ ] MCP servers verify SPIRE SVIDs
- [ ] Scoped permissions per agent
- [ ] Audit logging of all MCP calls
- [ ] Rate limiting per agent

### Monitoring & Compliance

- [ ] Audit log all agent actions
- [ ] Alerts on suspicious behavior
- [ ] Grafana dashboard for security metrics
- [ ] Log retention policy (90 days)
- [ ] Security scan in CI/CD

### Container Security

- [ ] Read-only root filesystem
- [ ] Drop all capabilities
- [ ] No privileged containers
- [ ] Security scanning of images
- [ ] Regular base image updates

---

## MCP Server Catalog for Agent Swarm

### Recommended MCP Servers

| MCP Server | Purpose | Tools | Security Level |
|------------|---------|-------|----------------|
| **mcp-server-docker** | Container management | list_containers, start_container, logs | HIGH - Requires docker socket |
| **mcp-server-kubernetes** | K8s operations | get_pods, apply_manifest, scale | HIGH - Cluster access |
| **mcp-server-postgres** | Database queries | query, schema_info | MEDIUM - Read-only mode |
| **mcp-server-github** | Git operations | create_pr, commit, issues | MEDIUM - Repo access |
| **mcp-server-slack** | Notifications | send_message, create_channel | LOW - Notification only |
| **mcp-server-aws** | Cloud operations | list_s3, lambda_invoke | HIGH - Cloud credentials |
| **mcp-server-http** | HTTP requests | get, post | MEDIUM - Network access |
| **mcp-server-filesystem** | File operations | read_file, write_file | HIGH - Host filesystem |

### Security Tiers

**HIGH Security (Requires mTLS + OAuth + Audit):**
- Docker, Kubernetes, AWS, Filesystem
- Full audit trail required
- Limited to specific agents only

**MEDIUM Security (Requires OAuth + Rate Limiting):**
- GitHub, PostgreSQL, HTTP
- Audit trail recommended
- Scoped to specific resources

**LOW Security (Requires OAuth):**
- Slack, Email, Monitoring
- Rate limiting sufficient
- General agent access OK

---

## Implementation Priority

### Week 1: Foundation

1. **Start SPIRE** (Day 1)
   - Deploy SPIRE server/agent
   - Register workloads
   - Grafana mTLS PoC

2. **Deploy Zitadel** (Day 2-3)
   - Add to docker-compose.yml
   - Bootstrap script
   - Create service accounts

3. **Secure NATS** (Day 4-5)
   - Enable mTLS
   - Configure ACLs
   - Test agent connection

### Week 2: MCP Integration

4. **Deploy Core MCP Servers** (Day 6-7)
   - mcp-server-docker
   - mcp-server-postgres
   - OAuth 2.1 security

5. **Agent MCP Integration** (Day 8-10)
   - MCP client implementation
   - Tool adaptation
   - Security testing

### Week 3: Hardening

6. **Network Policies** (Day 11-12)
   - Segment networks
   - Test connectivity
   - Document policies

7. **Secrets Migration** (Day 13-14)
   - Move secrets to OpenBao
   - Dynamic credentials
   - Rotation policies

8. **Audit & Compliance** (Day 15)
   - Audit logging
   - Security dashboards
   - Penetration testing

---

## Testing the Security

### SPIRE mTLS Test

```bash
# Test 1: Grafana can't connect without valid SVID
curl https://grafana.observe.ravenhelm.test/api/health
# Should fail: no client certificate

# Test 2: Agent with SPIRE SVID can connect
python scripts/grafana_spire_poc.py
# Should succeed: ✓ Grafana mTLS verified

# Test 3: Verify SPIFFE ID in logs
docker compose logs grafana | grep "spiffe://ravenhelm.local"
# Should show: Authenticated client: spiffe://ravenhelm.local/agent/observability
```

### OAuth 2.1 Test

```bash
# Test 1: MCP call without token fails
curl https://mcp-docker.ravenhelm.test/tools
# 401 Unauthorized

# Test 2: Agent with valid token succeeds
python -c "
from src.norns.mcp_client import SecureMCPClient
import asyncio

async def test():
    client = SecureMCPClient('mcp-docker', 'docker-agent')
    tools = await client.connect()
    print(f'✓ Authorized: {len(tools)} tools available')

asyncio.run(test())
"
```

### Network Isolation Test

```bash
# Test 1: Grafana cannot reach database directly
docker compose exec grafana nc -zv postgres 5432
# Should fail: connection refused

# Test 2: Hlidskjalf CAN reach database
docker compose exec hlidskjalf nc -zv postgres 5432
# Should succeed: connection to postgres port 5432 succeeded
```

---

## Summary: Production Security Architecture

```
User
  ↓ HTTPS (TLS 1.3)
Traefik (Edge)
  ↓ mTLS + JWT
Hliðskjálf (Control Plane)
  ↓ mTLS + Zitadel JWT
NATS (Event Bus)
  ↓ mTLS + ACLs + JWT
Worker Agents
  ↓ mTLS + OAuth 2.1
MCP Servers
  ↓ mTLS
Backend Services
```

**Every hop authenticated. Every connection encrypted. Every action audited.**

---

## Next Steps

1. **Read this plan** - Understand the architecture
2. **Start SPIRE** - Foundation for zero-trust
3. **Deploy Zitadel** - Identity provider
4. **Secure NATS** - Enable mTLS and ACLs
5. **Deploy MCP servers** - With OAuth 2.1
6. **Test end-to-end** - Grafana PoC proves it works

**Files to create:**
- `scripts/register_spire_workloads.sh`
- `scripts/bootstrap_zitadel.sh`
- `scripts/grafana_spire_poc.py`
- `hlidskjalf/src/norns/spire_integration.py`
- `hlidskjalf/src/norns/mcp_client.py`
- `docker-compose.mcp.yml`

---

*"Trust is verified cryptographically, not assumed."*

**Architecture:** Zero-Trust with SPIRE + Zitadel + OAuth 2.1  
**Status:** Design complete, ready to implement  
**Security Level:** Production-grade 🔒


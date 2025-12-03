# Ravenhelm Platform Template

> A comprehensive template for deploying applications on the Ravenhelm platform with full CI/CD, infrastructure as code, and observability.

## 🚀 Quick Start

```bash
# Clone this template
git clone https://gitlab.ravenhelm.test/ravenhelm/platform-template.git my-project
cd my-project

# Initialize for your project
./scripts/init-project.sh my-project

# Start local development
docker compose up -d
```

## 📁 Structure

```
.
├── .gitlab/                    # GitLab templates
│   ├── issue_templates/        # Bug, Feature, Incident templates
│   └── merge_request_templates/
├── .gitlab-ci.yml              # Main CI/CD pipeline
├── gitlab-ci/                  # Modular CI configurations
│   ├── terraform.yml           # Infrastructure jobs
│   ├── docker.yml              # Container build jobs
│   ├── security.yml            # Security scanning
│   ├── deploy.yml              # Deployment jobs
│   └── monitoring.yml          # Observability integration
├── terraform/                  # Infrastructure as Code
│   ├── main.tf                 # Root module
│   ├── modules/                # Reusable modules
│   └── environments/           # Environment configs
│       ├── dev/                # Local Docker deployment
│       ├── staging/            # AWS (LocalStack) deployment
│       └── prod/               # Production AWS deployment
├── docs/                       # Documentation
└── scripts/                    # Utility scripts
```

## 🔄 CI/CD Pipeline

### Stages

1. **Validate** - Lint, format check, terraform validate
2. **Build** - Docker image build and push
3. **Test** - Unit tests, coverage
4. **Security** - SAST, dependency scan, container scan
5. **Deploy Dev** - Automatic on merge to main
6. **Integration Test** - Against dev environment
7. **Deploy Staging** - After integration tests pass
8. **Acceptance Test** - E2E tests against staging
9. **Deploy Prod** - Manual approval required
10. **Post-Deploy** - Smoke tests, notifications

### Pipeline Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `CI_REGISTRY_*` | GitLab Container Registry | Auto |
| `SLACK_WEBHOOK_URL` | Slack notifications | Optional |
| `GRAFANA_API_KEY` | Deployment annotations | Optional |
| `AWS_ACCESS_KEY_ID` | AWS deployment | For staging/prod |
| `AWS_SECRET_ACCESS_KEY` | AWS deployment | For staging/prod |

## 🏗️ Infrastructure

### Environments

| Environment | Infrastructure | URL |
|-------------|----------------|-----|
| Dev | Docker (local) | `https://dev.{app}.ravenhelm.test` |
| Staging | AWS (LocalStack or real) | `https://staging.{app}.ravenhelm.test` |
| Prod | AWS | `https://{app}.ravenhelm.co` |

### Terraform Modules

- **networking** - VPC, subnets, security groups
- **compute** - ECS cluster, task definitions
- **database** - RDS PostgreSQL
- **monitoring** - CloudWatch, alerts

## 🔒 Security

### Automated Scans

- **SAST** - Semgrep static analysis
- **Dependency** - pip-audit, safety
- **Secrets** - TruffleHog
- **Container** - Trivy
- **IaC** - Trivy config scan

### Access Control

- All changes via merge request
- Protected branches (main, release/*)
- Required approvals for production

## 📊 Observability

### Metrics
- Application metrics via OpenTelemetry
- Prometheus scraping
- Grafana dashboards

### Logging
- Structured JSON logs
- Shipped to Loki via Alloy
- Retention: 30 days

### Tracing
- Distributed tracing via OpenTelemetry
- Tempo backend
- Trace-log correlation

## 📝 Issue Tracking

### Templates Available

- **Bug** - For defects and issues
- **Feature** - For new functionality
- **Incident** - For production incidents (auto-creates from alerts)

### Labels

- `bug`, `feature`, `incident`
- `needs-triage`, `needs-refinement`, `needs-review`
- `dev`, `staging`, `prod`
- `priority::critical`, `priority::high`, `priority::medium`, `priority::low`

## 🔧 Local Development

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Run tests
pytest tests/

# Deploy to dev (via terraform)
cd terraform/environments/dev
terraform init
terraform apply
```

## 📚 Documentation

- [Architecture](docs/architecture.md)
- [Development Guide](docs/development.md)
- [Deployment Guide](docs/deployment.md)
- [Runbooks](docs/runbooks/)

## 🤝 Contributing

1. Create issue for the work
2. Create branch from `main`
3. Make changes with tests
4. Create merge request
5. Get approval and merge

## 📄 License

Proprietary - Ravenhelm © 2025


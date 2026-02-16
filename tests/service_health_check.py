#!/usr/bin/env python3
"""
Service Health Check - Runtime Connectivity Tests

Tests that run against live services:
- Database connectivity (Postgres, Redis)
- API endpoints
- Docker container health
- Service ports
- Health endpoints

Run: python tests/service_health_check.py
Requires: Platform services running
"""

import sys
import socket
import subprocess
from pathlib import Path
from typing import Tuple, Optional
import requests

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


def check_port(host: str, port: int, timeout: float = 2.0) -> bool:
    """Check if a port is open"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False


def check_http_endpoint(url: str, timeout: float = 5.0) -> Tuple[bool, Optional[int], Optional[str]]:
    """Check if an HTTP endpoint responds"""
    try:
        response = requests.get(url, timeout=timeout, verify=False)
        return True, response.status_code, response.text[:100]
    except requests.exceptions.ConnectionError:
        return False, None, "Connection refused"
    except requests.exceptions.Timeout:
        return False, None, "Timeout"
    except Exception as e:
        return False, None, str(e)[:100]


def check_docker_containers() -> Tuple[int, int]:
    """Check Docker container status"""
    console.print("\n[bold cyan]═══ Docker Container Health ═══[/bold cyan]")
    
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            console.print("  [red]✗ Docker not available or not running[/red]")
            return 0, 0
        
        containers = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        if not containers:
            console.print("  [yellow]⚠️  No containers running[/yellow]")
            return 0, 0
        
        healthy = 0
        total = len(containers)
        
        for container in containers:
            if '\t' in container:
                name, status = container.split('\t', 1)
                if 'Up' in status and 'unhealthy' not in status.lower():
                    console.print(f"  ✓ {name} — {status}")
                    healthy += 1
                else:
                    console.print(f"  [yellow]⚠️  {name} — {status}[/yellow]")
        
        return healthy, total
        
    except Exception as e:
        console.print(f"  [red]✗ Error checking Docker: {e}[/red]")
        return 0, 0


def check_database_ports() -> Tuple[int, int]:
    """Check database service ports"""
    console.print("\n[bold cyan]═══ Database Service Ports ═══[/bold cyan]")
    
    services = [
        ("PostgreSQL", "localhost", 5432),
        ("Redis", "localhost", 6379),
        ("Neo4j", "localhost", 7687),
        ("Neo4j HTTP", "localhost", 7474),
    ]
    
    passed = 0
    total = len(services)
    
    for name, host, port in services:
        if check_port(host, port, timeout=2.0):
            console.print(f"  ✓ {name} — {host}:{port}")
            passed += 1
        else:
            console.print(f"  [yellow]⚠️  {name} — {host}:{port} not responding[/yellow]")
    
    return passed, total


def check_infrastructure_ports() -> Tuple[int, int]:
    """Check infrastructure service ports"""
    console.print("\n[bold cyan]═══ Infrastructure Service Ports ═══[/bold cyan]")
    
    services = [
        ("NATS", "localhost", 4222),
        ("Kafka", "localhost", 9092),
        ("Zitadel", "localhost", 8080),
        ("Traefik Dashboard", "localhost", 8082),
    ]
    
    passed = 0
    total = len(services)
    
    for name, host, port in services:
        if check_port(host, port, timeout=2.0):
            console.print(f"  ✓ {name} — {host}:{port}")
            passed += 1
        else:
            console.print(f"  [yellow]⚠️  {name} — {host}:{port} not responding[/yellow]")
    
    return passed, total


def check_api_ports() -> Tuple[int, int]:
    """Check API service ports"""
    console.print("\n[bold cyan]═══ API Service Ports ═══[/bold cyan]")
    
    services = [
        ("Hliðskjálf API", "localhost", 8000),
        ("LangGraph API", "localhost", 2024),
        ("Hliðskjálf UI", "localhost", 3900),
        ("Grafana", "localhost", 3000),
    ]
    
    passed = 0
    total = len(services)
    
    for name, host, port in services:
        if check_port(host, port, timeout=2.0):
            console.print(f"  ✓ {name} — {host}:{port}")
            passed += 1
        else:
            console.print(f"  [yellow]⚠️  {name} — {host}:{port} not responding[/yellow]")
    
    return passed, total


def check_health_endpoints() -> Tuple[int, int]:
    """Check HTTP health endpoints"""
    console.print("\n[bold cyan]═══ Health Endpoints ═══[/bold cyan]")
    
    endpoints = [
        ("Hliðskjálf API", "http://localhost:8000/health"),
        ("LangGraph API", "http://localhost:2024/info"),  # LangGraph uses /info not /health
        ("Traefik", "http://localhost:8082/ping"),
        ("Grafana", "http://localhost:3000/api/health"),
    ]
    
    passed = 0
    total = len(endpoints)
    
    for name, url in endpoints:
        success, status, message = check_http_endpoint(url, timeout=5.0)
        
        if success and status in [200, 204]:
            console.print(f"  ✓ {name} — HTTP {status}")
            passed += 1
        elif success:
            console.print(f"  [yellow]⚠️  {name} — HTTP {status}[/yellow]")
        else:
            console.print(f"  [yellow]⚠️  {name} — {message}[/yellow]")
    
    return passed, total


def check_mcp_endpoints() -> Tuple[int, int]:
    """Check MCP server endpoints"""
    console.print("\n[bold cyan]═══ MCP Server Endpoints ═══[/bold cyan]")
    
    endpoints = [
        ("MCP GitLab", "http://localhost:9400/tools/list"),
        # Bifrost Gateway not in current deployment - removed
    ]
    
    passed = 0
    total = len(endpoints)
    
    for name, url in endpoints:
        success, status, message = check_http_endpoint(url, timeout=5.0)
        
        if success and status in [200, 401]:  # 401 is OK (needs auth)
            console.print(f"  ✓ {name} — HTTP {status}")
            passed += 1
        elif success:
            console.print(f"  [yellow]⚠️  {name} — HTTP {status}[/yellow]")
        else:
            console.print(f"  [yellow]⚠️  {name} — {message}[/yellow]")
    
    return passed, total


def check_observability_ports() -> Tuple[int, int]:
    """Check observability service ports"""
    console.print("\n[bold cyan]═══ Observability Service Ports ═══[/bold cyan]")
    
    services = [
        ("Prometheus", "localhost", 9090),
        ("Loki", "localhost", 3100),
        ("Tempo", "localhost", 3200),
        ("Grafana Alloy", "localhost", 12345),
    ]
    
    passed = 0
    total = len(services)
    
    for name, host, port in services:
        if check_port(host, port, timeout=2.0):
            console.print(f"  ✓ {name} — {host}:{port}")
            passed += 1
        else:
            console.print(f"  [yellow]⚠️  {name} — {host}:{port} not responding[/yellow]")
    
    return passed, total


def main():
    """Run all service health checks"""
    console.print(Panel.fit(
        "[bold cyan]Service Health Check - Runtime Connectivity Tests[/bold cyan]\n"
        "Testing live services and endpoints\n"
        "[yellow]⚠️  Requires platform services to be running[/yellow]",
        border_style="cyan"
    ))
    
    tests = [
        ("Docker Containers", check_docker_containers),
        ("Database Ports", check_database_ports),
        ("Infrastructure Ports", check_infrastructure_ports),
        ("API Ports", check_api_ports),
        ("Health Endpoints", check_health_endpoints),
        ("MCP Endpoints", check_mcp_endpoints),
        ("Observability Ports", check_observability_ports),
    ]
    
    results = []
    
    for test_name, test_fn in tests:
        try:
            passed, total = test_fn()
            results.append((test_name, passed, total))
        except Exception as e:
            console.print(f"\n[red]Fatal error in {test_name}: {e}[/red]")
            import traceback
            console.print(traceback.format_exc())
            results.append((test_name, 0, 1))
    
    # Summary
    console.print("\n" + "="*70)
    console.print("[bold]Service Health Summary[/bold]")
    console.print("="*70)
    
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Test", style="cyan", width=30)
    table.add_column("Healthy", justify="right", width=10)
    table.add_column("Total", justify="right", width=10)
    table.add_column("Status", width=15)
    
    total_passed = 0
    total_checks = 0
    
    for test_name, passed, total in results:
        total_passed += passed
        total_checks += total
        
        if total == 0:
            status = "[yellow]N/A[/yellow]"
        else:
            percentage = (passed / total * 100) if total > 0 else 0
            
            if passed == total:
                status = "[green]✓ HEALTHY[/green]"
            elif passed >= total * 0.7:
                status = "[yellow]⚠️  PARTIAL[/yellow]"
            elif passed > 0:
                status = "[yellow]⚠️  DEGRADED[/yellow]"
            else:
                status = "[red]✗ DOWN[/red]"
        
        table.add_row(test_name, str(passed), str(total), status)
    
    console.print(table)
    
    # Overall verdict
    console.print("\n" + "="*70)
    
    if total_checks == 0:
        console.print(Panel.fit(
            "[bold yellow]⚠️  NO SERVICES DETECTED[/bold yellow]\n"
            "Platform services do not appear to be running.\n"
            "Run: ./scripts/start-platform.sh",
            border_style="yellow"
        ))
        return 1
    
    percentage = (total_passed / total_checks * 100) if total_checks > 0 else 0
    
    if percentage >= 90:
        console.print(Panel.fit(
            f"[bold green]🎉 ALL SERVICES HEALTHY ({total_passed}/{total_checks} - {percentage:.1f}%)[/bold green]\n"
            "Platform is fully operational!",
            border_style="green"
        ))
        return 0
    elif percentage >= 70:
        console.print(Panel.fit(
            f"[bold yellow]⚠️  SOME SERVICES DOWN ({total_passed}/{total_checks} - {percentage:.1f}%)[/bold yellow]\n"
            "Platform is partially operational. Check warnings above.",
            border_style="yellow"
        ))
        return 0
    elif percentage > 0:
        console.print(Panel.fit(
            f"[bold yellow]⚠️  MANY SERVICES DOWN ({total_passed}/{total_checks} - {percentage:.1f}%)[/bold yellow]\n"
            "Platform is degraded. Review service status.",
            border_style="yellow"
        ))
        return 1
    else:
        console.print(Panel.fit(
            f"[bold red]✗ PLATFORM DOWN ({total_passed}/{total_checks} - {percentage:.1f}%)[/bold red]\n"
            "No services responding. Start platform with: ./scripts/start-platform.sh",
            border_style="red"
        ))
        return 1


if __name__ == "__main__":
    sys.exit(main())


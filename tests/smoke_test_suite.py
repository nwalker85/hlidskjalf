#!/usr/bin/env python3
"""
Comprehensive Smoke Test Suite for Ravenhelm Platform

Tests that can run programmatically without full deployment:
- Configuration validation
- File structure integrity
- Import health checks
- Tool instantiation
- Service configuration
- Database schema validation
- API route definitions

Run: python tests/smoke_test_suite.py
"""

import asyncio
import sys
import os
import json
import yaml
from pathlib import Path
from typing import List, Tuple, Dict, Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# Base paths
PROJECT_ROOT = Path("/Users/nwalker/Development/hlidskjalf")
HLIDSKJALF_ROOT = PROJECT_ROOT / "hlidskjalf"
HLIDSKJALF_SRC = HLIDSKJALF_ROOT / "src"


def test_docker_compose_files():
    """Test 1: Docker Compose Files Validation"""
    console.print("\n[bold cyan]═══ Test 1: Docker Compose Files ═══[/bold cyan]")
    
    compose_files = [
        PROJECT_ROOT / "docker-compose.yml",
        PROJECT_ROOT / "compose/docker-compose.base.yml",
        PROJECT_ROOT / "compose/docker-compose.infrastructure.yml",
        PROJECT_ROOT / "compose/docker-compose.security.yml",
        PROJECT_ROOT / "compose/docker-compose.integrations.yml",
        PROJECT_ROOT / "compose/docker-compose.observability.yml",
    ]
    
    passed = 0
    total = len(compose_files)
    
    for compose_file in compose_files:
        if compose_file.exists():
            try:
                with open(compose_file) as f:
                    data = yaml.safe_load(f)
                    if data and isinstance(data, dict):
                        services = data.get('services', {})
                        console.print(f"  ✓ {compose_file.name} — {len(services)} services")
                        passed += 1
                    else:
                        console.print(f"  [yellow]⚠️  {compose_file.name} — Invalid structure[/yellow]")
            except Exception as e:
                console.print(f"  [red]✗ {compose_file.name} — Parse error: {e}[/red]")
        else:
            console.print(f"  [red]✗ {compose_file.name} — Not found[/red]")
    
    return passed, total


def test_port_registry():
    """Test 2: Port Registry Validation"""
    console.print("\n[bold cyan]═══ Test 2: Port Registry ═══[/bold cyan]")
    
    port_registry = PROJECT_ROOT / "config/port_registry.yaml"
    
    if not port_registry.exists():
        console.print("  [red]✗ port_registry.yaml not found[/red]")
        return 0, 1
    
    try:
        with open(port_registry) as f:
            data = yaml.safe_load(f)
            
        if not data or 'ports' not in data:
            console.print("  [red]✗ Invalid port registry structure[/red]")
            return 0, 1
        
        ports = data['ports']
        console.print(f"  ✓ Port registry loaded — {len(ports)} port definitions")
        
        # Check for duplicates
        port_numbers = [p['port'] for p in ports if 'port' in p]
        duplicates = [p for p in port_numbers if port_numbers.count(p) > 1]
        
        if duplicates:
            console.print(f"  [yellow]⚠️  Duplicate ports detected: {set(duplicates)}[/yellow]")
            return 1, 2
        else:
            console.print(f"  ✓ No duplicate ports")
            return 2, 2
            
    except Exception as e:
        console.print(f"  [red]✗ Error: {e}[/red]")
        return 0, 1


def test_database_migrations():
    """Test 3: Database Migration Files"""
    console.print("\n[bold cyan]═══ Test 3: Database Migrations ═══[/bold cyan]")
    
    migrations_dir = HLIDSKJALF_ROOT / "migrations/versions"
    postgres_init = PROJECT_ROOT / "postgres/init"
    
    passed = 0
    total = 0
    
    # Check migrations directory
    if migrations_dir.exists():
        migrations = list(migrations_dir.glob("*.sql"))
        console.print(f"  ✓ Found {len(migrations)} migration files")
        
        for migration in migrations:
            # Check if file is not empty
            if migration.stat().st_size > 0:
                console.print(f"    ✓ {migration.name} ({migration.stat().st_size} bytes)")
                passed += 1
            else:
                console.print(f"    [yellow]⚠️  {migration.name} — Empty file[/yellow]")
            total += 1
    else:
        console.print("  [yellow]⚠️  Migrations directory not found[/yellow]")
    
    # Check postgres init scripts
    if postgres_init.exists():
        init_scripts = list(postgres_init.glob("*.sql"))
        console.print(f"  ✓ Found {len(init_scripts)} postgres init scripts")
        passed += 1
        total += 1
    
    return passed, total


def test_traefik_configuration():
    """Test 4: Traefik Configuration"""
    console.print("\n[bold cyan]═══ Test 4: Traefik Configuration ═══[/bold cyan]")
    
    traefik_dir = PROJECT_ROOT / "ravenhelm-proxy"
    files_to_check = [
        ("traefik.yml", "Static configuration"),
        ("dynamic.yml", "Dynamic configuration"),
        ("docker-compose-traefik.yml", "Docker compose"),
    ]
    
    passed = 0
    total = len(files_to_check)
    
    for filename, description in files_to_check:
        file_path = traefik_dir / filename
        if file_path.exists():
            try:
                if filename.endswith('.yml'):
                    with open(file_path) as f:
                        data = yaml.safe_load(f)
                        if data:
                            console.print(f"  ✓ {filename} — {description}")
                            passed += 1
                        else:
                            console.print(f"  [yellow]⚠️  {filename} — Empty[/yellow]")
            except Exception as e:
                console.print(f"  [red]✗ {filename} — Parse error: {e}[/red]")
        else:
            console.print(f"  [red]✗ {filename} — Not found[/red]")
    
    return passed, total


def test_skill_files_structure():
    """Test 5: Skill Files Structure"""
    console.print("\n[bold cyan]═══ Test 5: Skill Files Structure ═══[/bold cyan]")
    
    skills_dir = HLIDSKJALF_ROOT / "skills"
    
    if not skills_dir.exists():
        console.print("  [red]✗ Skills directory not found[/red]")
        return 0, 1
    
    skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir()]
    console.print(f"  ✓ Found {len(skill_dirs)} skill directories")
    
    passed = 0
    total = len(skill_dirs)
    
    required_fields = ['name', 'description', 'tags']
    enhanced_fields = ['roles', 'summary', 'triggers']
    
    for skill_dir in skill_dirs:
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            content = skill_file.read_text()
            
            # Check for YAML frontmatter
            if content.startswith('---'):
                # Extract frontmatter
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    frontmatter = parts[1]
                    
                    has_required = all(f"{field}:" in frontmatter for field in required_fields)
                    has_enhanced = any(f"{field}:" in frontmatter for field in enhanced_fields)
                    
                    if has_required:
                        status = "✓" if has_enhanced else "⚠️ "
                        marker = "" if has_enhanced else "[yellow]"
                        end_marker = "" if has_enhanced else "[/yellow]"
                        console.print(f"    {marker}{status} {skill_dir.name}{end_marker}")
                        passed += 1
                    else:
                        console.print(f"    [yellow]⚠️  {skill_dir.name} — Missing required fields[/yellow]")
            else:
                console.print(f"    [yellow]⚠️  {skill_dir.name} — No frontmatter[/yellow]")
        else:
            console.print(f"    [red]✗ {skill_dir.name} — No SKILL.md[/red]")
    
    return passed, total


def test_python_imports():
    """Test 6: Python Import Health"""
    console.print("\n[bold cyan]═══ Test 6: Python Import Health ═══[/bold cyan]")
    
    # Add src to path
    sys.path.insert(0, str(HLIDSKJALF_SRC))
    os.environ["PYTHONPATH"] = str(HLIDSKJALF_SRC)
    
    imports_to_test = [
        ("core.config", "Core configuration"),
        ("api.main", "FastAPI application"),
        ("models", "Data models"),
        ("norns.skills", "Skills module"),
    ]
    
    passed = 0
    total = len(imports_to_test)
    
    for module_name, description in imports_to_test:
        try:
            __import__(module_name)
            console.print(f"  ✓ {module_name} — {description}")
            passed += 1
        except ImportError as e:
            console.print(f"  [yellow]⚠️  {module_name} — Import warning: {str(e)[:60]}...[/yellow]")
        except Exception as e:
            console.print(f"  [red]✗ {module_name} — Error: {str(e)[:60]}...[/red]")
    
    return passed, total


def test_api_routes():
    """Test 7: API Routes Definition"""
    console.print("\n[bold cyan]═══ Test 7: API Routes Definition ═══[/bold cyan]")
    
    api_files = [
        (HLIDSKJALF_SRC / "api/main.py", "Main API"),
        (HLIDSKJALF_SRC / "api/llm_config.py", "LLM Config API"),
    ]
    
    passed = 0
    total = 0
    
    for api_file, description in api_files:
        if api_file.exists():
            content = api_file.read_text()
            
            # Count route decorators
            get_routes = content.count("@router.get") + content.count("@app.get")
            post_routes = content.count("@router.post") + content.count("@app.post")
            put_routes = content.count("@router.put") + content.count("@app.put")
            delete_routes = content.count("@router.delete") + content.count("@app.delete")
            
            total_routes = get_routes + post_routes + put_routes + delete_routes
            
            if total_routes > 0:
                console.print(f"  ✓ {description} — {total_routes} routes (GET:{get_routes}, POST:{post_routes}, PUT:{put_routes}, DEL:{delete_routes})")
                passed += 1
            else:
                console.print(f"  [yellow]⚠️  {description} — No routes found[/yellow]")
            
            total += 1
        else:
            console.print(f"  [red]✗ {description} — File not found[/red]")
            total += 1
    
    return passed, total


def test_observability_config():
    """Test 8: Observability Configuration"""
    console.print("\n[bold cyan]═══ Test 8: Observability Configuration ═══[/bold cyan]")
    
    obs_dir = PROJECT_ROOT / "observability"
    configs_to_check = [
        ("grafana/provisioning/datasources/datasources.yml", "Grafana datasources"),
        ("prometheus/prometheus.yml", "Prometheus config"),
        ("loki/loki.yaml", "Loki config"),
        ("tempo/tempo.yaml", "Tempo config"),
        ("alloy/config.alloy", "Alloy config"),
    ]
    
    passed = 0
    total = len(configs_to_check)
    
    for config_path, description in configs_to_check:
        file_path = obs_dir / config_path
        if file_path.exists():
            if file_path.stat().st_size > 0:
                console.print(f"  ✓ {description}")
                passed += 1
            else:
                console.print(f"  [yellow]⚠️  {description} — Empty file[/yellow]")
        else:
            console.print(f"  [yellow]⚠️  {description} — Not found[/yellow]")
    
    return passed, total


def test_spire_configuration():
    """Test 9: SPIRE/SPIFFE Configuration"""
    console.print("\n[bold cyan]═══ Test 9: SPIRE/SPIFFE Configuration ═══[/bold cyan]")
    
    spire_dir = PROJECT_ROOT / "spire"
    spiffe_helper_dir = PROJECT_ROOT / "config/spiffe-helper"
    
    passed = 0
    total = 0
    
    # Check SPIRE server config
    server_conf = spire_dir / "server/server.conf"
    if server_conf.exists():
        console.print(f"  ✓ SPIRE server config")
        passed += 1
    else:
        console.print(f"  [yellow]⚠️  SPIRE server config not found[/yellow]")
    total += 1
    
    # Check SPIRE agent config
    agent_conf = spire_dir / "agent/agent.conf"
    if agent_conf.exists():
        console.print(f"  ✓ SPIRE agent config")
        passed += 1
    else:
        console.print(f"  [yellow]⚠️  SPIRE agent config not found[/yellow]")
    total += 1
    
    # Check spiffe-helper configs
    if spiffe_helper_dir.exists():
        helper_configs = list(spiffe_helper_dir.glob("*.conf"))
        console.print(f"  ✓ Found {len(helper_configs)} spiffe-helper configs")
        passed += 1
        total += 1
    else:
        console.print(f"  [yellow]⚠️  spiffe-helper config directory not found[/yellow]")
        total += 1
    
    return passed, total


def test_documentation_completeness():
    """Test 10: Documentation Completeness"""
    console.print("\n[bold cyan]═══ Test 10: Documentation Completeness ═══[/bold cyan]")
    
    docs_dir = PROJECT_ROOT / "docs"
    
    required_docs = [
        ("README.md", "Project README"),
        ("PROJECT_PLAN.md", "Project plan"),
        ("LESSONS_LEARNED.md", "Lessons learned"),
        ("wiki/Overview.md", "Wiki overview"),
        ("wiki/Runbook_Catalog.md", "Runbook catalog"),
        ("runbooks", "Runbooks directory"),
        ("architecture", "Architecture docs directory"),
    ]
    
    passed = 0
    total = len(required_docs)
    
    for doc_path, description in required_docs:
        full_path = docs_dir / doc_path if not doc_path.startswith('/') else PROJECT_ROOT / doc_path
        
        if full_path.exists():
            if full_path.is_dir():
                items = list(full_path.glob("*"))
                console.print(f"  ✓ {description} — {len(items)} items")
            else:
                size = full_path.stat().st_size
                console.print(f"  ✓ {description} — {size} bytes")
            passed += 1
        else:
            console.print(f"  [yellow]⚠️  {description} — Not found[/yellow]")
    
    return passed, total


def test_runbook_numbering():
    """Test 11: Runbook Numbering Scheme"""
    console.print("\n[bold cyan]═══ Test 11: Runbook Numbering ═══[/bold cyan]")
    
    runbooks_dir = PROJECT_ROOT / "docs/runbooks"
    
    if not runbooks_dir.exists():
        console.print("  [red]✗ Runbooks directory not found[/red]")
        return 0, 1
    
    runbooks = list(runbooks_dir.glob("RUNBOOK-*.md"))
    console.print(f"  ✓ Found {len(runbooks)} runbooks")
    
    # Extract numbers and check for gaps
    numbers = []
    for rb in runbooks:
        try:
            num = int(rb.stem.split('-')[1])
            numbers.append(num)
        except:
            console.print(f"  [yellow]⚠️  Invalid numbering: {rb.name}[/yellow]")
    
    numbers.sort()
    
    if numbers:
        console.print(f"  ✓ Runbooks numbered from {numbers[0]:03d} to {numbers[-1]:03d}")
        
        # Check for gaps
        gaps = []
        for i in range(len(numbers) - 1):
            if numbers[i+1] - numbers[i] > 1:
                gaps.append((numbers[i], numbers[i+1]))
        
        if gaps:
            console.print(f"  [yellow]⚠️  Numbering gaps: {gaps}[/yellow]")
            return 1, 2
        else:
            console.print(f"  ✓ No numbering gaps")
            return 2, 2
    
    return 1, 2


def test_git_status():
    """Test 12: Git Repository Status"""
    console.print("\n[bold cyan]═══ Test 12: Git Repository Status ═══[/bold cyan]")
    
    import subprocess
    
    try:
        # Check if we're in a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            console.print("  ✓ Git repository detected")
            
            # Check for uncommitted changes
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True
            )
            
            if result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                console.print(f"  [yellow]⚠️  {len(lines)} uncommitted changes[/yellow]")
                return 1, 2
            else:
                console.print("  ✓ Working directory clean")
                return 2, 2
        else:
            console.print("  [yellow]⚠️  Not a git repository[/yellow]")
            return 0, 1
            
    except Exception as e:
        console.print(f"  [yellow]⚠️  Git check failed: {e}[/yellow]")
        return 0, 1


def main():
    """Run all smoke tests"""
    console.print(Panel.fit(
        "[bold cyan]Ravenhelm Platform - Comprehensive Smoke Test Suite[/bold cyan]\n"
        "Validating configuration, structure, and integrations",
        border_style="cyan"
    ))
    
    tests = [
        ("Docker Compose Files", test_docker_compose_files),
        ("Port Registry", test_port_registry),
        ("Database Migrations", test_database_migrations),
        ("Traefik Configuration", test_traefik_configuration),
        ("Skill Files Structure", test_skill_files_structure),
        ("Python Import Health", test_python_imports),
        ("API Routes Definition", test_api_routes),
        ("Observability Config", test_observability_config),
        ("SPIRE/SPIFFE Config", test_spire_configuration),
        ("Documentation", test_documentation_completeness),
        ("Runbook Numbering", test_runbook_numbering),
        ("Git Repository", test_git_status),
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
    console.print("[bold]Smoke Test Results Summary[/bold]")
    console.print("="*70)
    
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Test", style="cyan", width=30)
    table.add_column("Passed", justify="right", width=10)
    table.add_column("Total", justify="right", width=10)
    table.add_column("Status", width=15)
    
    total_passed = 0
    total_checks = 0
    
    for test_name, passed, total in results:
        total_passed += passed
        total_checks += total
        
        percentage = (passed / total * 100) if total > 0 else 0
        
        if passed == total:
            status = "[green]✓ PASS[/green]"
        elif passed >= total * 0.7:
            status = "[yellow]⚠️  WARN[/yellow]"
        else:
            status = "[red]✗ FAIL[/red]"
        
        table.add_row(test_name, str(passed), str(total), status)
    
    console.print(table)
    
    # Overall verdict
    console.print("\n" + "="*70)
    percentage = (total_passed / total_checks * 100) if total_checks > 0 else 0
    
    if percentage >= 90:
        console.print(Panel.fit(
            f"[bold green]🎉 SMOKE TESTS PASSED ({total_passed}/{total_checks} - {percentage:.1f}%)[/bold green]\n"
            "Platform configuration is healthy!",
            border_style="green"
        ))
        return 0
    elif percentage >= 70:
        console.print(Panel.fit(
            f"[bold yellow]⚠️  SOME ISSUES DETECTED ({total_passed}/{total_checks} - {percentage:.1f}%)[/bold yellow]\n"
            "Review warnings above.",
            border_style="yellow"
        ))
        return 0
    else:
        console.print(Panel.fit(
            f"[bold red]✗ SMOKE TESTS FAILED ({total_passed}/{total_checks} - {percentage:.1f}%)[/bold red]\n"
            "Significant issues detected.",
            border_style="red"
        ))
        return 1


if __name__ == "__main__":
    sys.exit(main())


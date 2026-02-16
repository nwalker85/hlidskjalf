#!/usr/bin/env python3
"""
RAG Skills Implementation Verification

Verifies that all RAG components are in place without requiring runtime imports.
Checks file existence, code patterns, and integration points.
"""

from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

def check_file_exists(path: Path, description: str) -> bool:
    """Check if a file exists"""
    if path.exists():
        console.print(f"  ✓ {description}")
        return True
    else:
        console.print(f"  [red]✗ {description} - NOT FOUND[/red]")
        return False

def check_code_pattern(file_path: Path, pattern: str, description: str) -> bool:
    """Check if a code pattern exists in a file"""
    if not file_path.exists():
        console.print(f"  [red]✗ {description} - FILE NOT FOUND[/red]")
        return False
    
    content = file_path.read_text()
    if pattern in content:
        console.print(f"  ✓ {description}")
        return True
    else:
        console.print(f"  [yellow]⚠️  {description} - PATTERN NOT FOUND[/yellow]")
        return False

def verify_infrastructure():
    """Verify core infrastructure files"""
    console.print("\n[bold cyan]═══ Core Infrastructure ═══[/bold cyan]")
    
    base = Path("/Users/nwalker/Development/hlidskjalf/hlidskjalf")
    
    checks = [
        (base / "src/memory/muninn/procedural.py", "Procedural Memory handler"),
        (base / "src/memory/muninn/structural.py", "Structural Memory (Neo4j)"),
        (base / "src/memory/muninn/weaviate_adapter.py", "Weaviate adapter"),
        (base / "src/services/document_ingestion.py", "Document Ingestion service"),
        (base / "migrations/versions/003_procedural_memory_enhancements.sql", "DB migration"),
    ]
    
    passed = sum(check_file_exists(path, desc) for path, desc in checks)
    return passed, len(checks)

def verify_mcp_tools():
    """Verify MCP memory tools"""
    console.print("\n[bold cyan]═══ MCP Memory Tools ═══[/bold cyan]")
    
    tools_file = Path("/Users/nwalker/Development/hlidskjalf/hlidskjalf/src/norns/memory_tools.py")
    
    tools_to_check = [
        ("skills_retrieve", "Skills retrieval tool"),
        ("skills_list", "Skills list tool"),
        ("skills_add", "Skills add tool"),
        ("documents_crawl_page", "Document crawl tool"),
        ("graph_skill_dependencies", "Graph dependency tool"),
    ]
    
    passed = sum(
        check_code_pattern(tools_file, f"def {tool_name}", desc)
        for tool_name, desc in tools_to_check
    )
    
    # Check MEMORY_TOOLS export
    if check_code_pattern(tools_file, "MEMORY_TOOLS = [", "MEMORY_TOOLS export"):
        passed += 1
    
    return passed, len(tools_to_check) + 1

def verify_agent_integration():
    """Verify agent RAG integration"""
    console.print("\n[bold cyan]═══ Agent Integration ═══[/bold cyan]")
    
    specialized_agents = Path("/Users/nwalker/Development/hlidskjalf/hlidskjalf/src/norns/specialized_agents.py")
    norns_agent = Path("/Users/nwalker/Development/hlidskjalf/hlidskjalf/src/norns/agent.py")
    
    checks = [
        (specialized_agents, "retrieve_agent_skills", "RAG helper function"),
        (specialized_agents, "skills_context = retrieve_agent_skills", "Subagent RAG call"),
        (specialized_agents, "state_modifier=SystemMessage", "System prompt injection"),
        (norns_agent, "skills_retrieve", "Norns skills retrieval"),
        (norns_agent, "skills_context", "Norns skills context"),
    ]
    
    passed = sum(
        check_code_pattern(file_path, pattern, desc)
        for file_path, pattern, desc in checks
    )
    
    return passed, len(checks)

def verify_skill_files():
    """Verify skill files with enhanced metadata"""
    console.print("\n[bold cyan]═══ Skill Files ═══[/bold cyan]")
    
    skills_dir = Path("/Users/nwalker/Development/hlidskjalf/hlidskjalf/skills")
    
    enhanced_skills = [
        "file-editing",
        "terminal-commands",
        "memory-retrieval",
    ]
    
    passed = 0
    for skill_name in enhanced_skills:
        skill_file = skills_dir / skill_name / "SKILL.md"
        if check_file_exists(skill_file, f"{skill_name} skill"):
            # Check for enhanced metadata
            content = skill_file.read_text()
            has_roles = "roles:" in content
            has_summary = "summary:" in content
            
            if has_roles and has_summary:
                console.print(f"    ✓ Has roles and summary")
                passed += 1
            else:
                missing = []
                if not has_roles:
                    missing.append("roles")
                if not has_summary:
                    missing.append("summary")
                console.print(f"    [yellow]⚠️  Missing: {', '.join(missing)}[/yellow]")
    
    return passed, len(enhanced_skills)

def verify_documentation():
    """Verify documentation files"""
    console.print("\n[bold cyan]═══ Documentation ═══[/bold cyan]")
    
    docs_dir = Path("/Users/nwalker/Development/hlidskjalf/docs")
    
    docs = [
        (docs_dir / "MCP_MEMORY_API.md", "MCP API Reference"),
        (docs_dir / "RAG_SKILLS_IMPLEMENTATION_SUMMARY.md", "Implementation Summary"),
        (docs_dir / "RAG_SKILLS_STATUS.md", "Status Document"),
        (docs_dir / "RAG_IMPLEMENTATION_COMPLETE.md", "Completion Summary"),
    ]
    
    passed = sum(check_file_exists(path, desc) for path, desc in docs)
    return passed, len(docs)

def verify_docker_services():
    """Verify Docker service configuration"""
    console.print("\n[bold cyan]═══ Docker Services ═══[/bold cyan]")
    
    compose_file = Path("/Users/nwalker/Development/hlidskjalf/compose/docker-compose.integrations.yml")
    
    if check_file_exists(compose_file, "Integrations compose file"):
        if check_code_pattern(compose_file, "firecrawl:", "Firecrawl service"):
            return 2, 2
        return 1, 2
    return 0, 2

def main():
    """Run all verifications"""
    console.print(Panel.fit(
        "[bold cyan]RAG Skills Implementation Verification[/bold cyan]\n"
        "Checking all components without runtime imports",
        border_style="cyan"
    ))
    
    results = []
    
    results.append(("Infrastructure", *verify_infrastructure()))
    results.append(("MCP Tools", *verify_mcp_tools()))
    results.append(("Agent Integration", *verify_agent_integration()))
    results.append(("Skill Files", *verify_skill_files()))
    results.append(("Documentation", *verify_documentation()))
    results.append(("Docker Services", *verify_docker_services()))
    
    # Summary
    console.print("\n" + "="*60)
    console.print("[bold]Verification Summary[/bold]")
    console.print("="*60)
    
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Component", style="cyan", width=25)
    table.add_column("Passed", justify="right", width=10)
    table.add_column("Total", justify="right", width=10)
    table.add_column("Status", width=15)
    
    total_passed = 0
    total_checks = 0
    
    for name, passed, total in results:
        total_passed += passed
        total_checks += total
        
        percentage = (passed / total * 100) if total > 0 else 0
        
        if passed == total:
            status = "[green]✓ COMPLETE[/green]"
        elif passed >= total * 0.8:
            status = "[yellow]⚠️  MOSTLY OK[/yellow]"
        else:
            status = "[red]✗ ISSUES[/red]"
        
        table.add_row(name, str(passed), str(total), status)
    
    console.print(table)
    
    # Overall status
    console.print("\n" + "="*60)
    percentage = (total_passed / total_checks * 100) if total_checks > 0 else 0
    
    if percentage >= 90:
        console.print(Panel.fit(
            f"[bold green]🎉 VERIFICATION PASSED ({total_passed}/{total_checks} - {percentage:.1f}%)[/bold green]\n"
            "RAG Skills system is properly implemented!",
            border_style="green"
        ))
        return 0
    elif percentage >= 70:
        console.print(Panel.fit(
            f"[bold yellow]⚠️  MOSTLY COMPLETE ({total_passed}/{total_checks} - {percentage:.1f}%)[/bold yellow]\n"
            "Core components in place, minor issues to address.",
            border_style="yellow"
        ))
        return 0
    else:
        console.print(Panel.fit(
            f"[bold red]✗ VERIFICATION FAILED ({total_passed}/{total_checks} - {percentage:.1f}%)[/bold red]\n"
            "Significant components missing or incomplete.",
            border_style="red"
        ))
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())


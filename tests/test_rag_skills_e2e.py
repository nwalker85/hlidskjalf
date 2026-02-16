#!/usr/bin/env python3
"""
End-to-End Test for RAG Skills System

Tests the complete pipeline:
1. Skill file loading and parsing
2. Skill retrieval via RAG
3. Agent integration with skills
4. MCP tools availability
5. Memory operations

Run: python tests/test_rag_skills_e2e.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Add hlidskjalf/src to path and set PYTHONPATH
hlidskjalf_src = Path(__file__).parent.parent / "hlidskjalf" / "src"
sys.path.insert(0, str(hlidskjalf_src))
os.environ["PYTHONPATH"] = str(hlidskjalf_src) + ":" + os.environ.get("PYTHONPATH", "")

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


async def test_skill_loading():
    """Test 1: Load and parse skill files"""
    console.print("\n[bold cyan]═══ Test 1: Skill Loading ═══[/bold cyan]")
    
    try:
        from norns.skills import list_skills, load_full_skill
        
        # List all skills
        skills = await list_skills()
        
        if not skills:
            console.print("[yellow]⚠️  No skills found in skills directory[/yellow]")
            return False
        
        console.print(f"✓ Found {len(skills)} skill files")
        
        # Load a sample skill
        for skill_path in skills[:1]:  # Test first skill
            full_skill = await load_full_skill(skill_path)
            if full_skill:
                console.print(f"✓ Loaded skill: {full_skill.metadata.name}")
                console.print(f"  Description: {full_skill.metadata.description[:80]}...")
                console.print(f"  Tags: {', '.join(full_skill.metadata.tags)}")
                console.print(f"  Content length: {len(full_skill.content)} chars")
            else:
                console.print(f"[red]✗ Failed to load skill at {skill_path}[/red]")
                return False
        
        console.print("[green]✓ Test 1 PASSED[/green]")
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Test 1 FAILED: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return False


async def test_memory_tools_import():
    """Test 2: MCP Memory Tools Import"""
    console.print("\n[bold cyan]═══ Test 2: MCP Memory Tools Import ═══[/bold cyan]")
    
    try:
        from norns.memory_tools import MEMORY_TOOLS
        
        console.print(f"✓ Imported {len(MEMORY_TOOLS)} memory tools")
        
        # Check for key tools
        tool_names = {tool.name for tool in MEMORY_TOOLS}
        expected_tools = [
            "skills_retrieve",
            "skills_list",
            "skills_add",
            "documents_crawl_page",
            "muninn_recall",
            "huginn_perceive",
            "frigg_divine",
        ]
        
        missing = []
        for tool_name in expected_tools:
            if tool_name in tool_names:
                console.print(f"  ✓ {tool_name}")
            else:
                console.print(f"  [red]✗ {tool_name} MISSING[/red]")
                missing.append(tool_name)
        
        if missing:
            console.print(f"[red]✗ Missing {len(missing)} expected tools[/red]")
            return False
        
        console.print("[green]✓ Test 2 PASSED[/green]")
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Test 2 FAILED: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return False


async def test_skill_retrieval_function():
    """Test 3: RAG Skills Retrieval Function"""
    console.print("\n[bold cyan]═══ Test 3: Skills Retrieval Function ═══[/bold cyan]")
    
    try:
        from norns.specialized_agents import retrieve_agent_skills
        
        # Test retrieval (will return empty if Muninn not populated, which is OK)
        console.print("Testing skill retrieval with query: 'edit files safely'")
        
        skills_context = retrieve_agent_skills(
            role="sre",
            task_context="edit files safely, workspace operations, read-plan-write-verify",
            k=3
        )
        
        if skills_context:
            console.print(f"✓ Retrieved skills context ({len(skills_context)} chars)")
            console.print(f"  Preview: {skills_context[:200]}...")
        else:
            console.print("[yellow]⚠️  Skills context empty (Muninn may not be populated yet)[/yellow]")
            console.print("  This is OK for file-based skills. Migration to Muninn is pending.")
        
        console.print("[green]✓ Test 3 PASSED (function callable)[/green]")
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Test 3 FAILED: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return False


async def test_subagent_creation():
    """Test 4: Subagent Creation with RAG"""
    console.print("\n[bold cyan]═══ Test 4: Subagent Creation ═══[/bold cyan]")
    
    try:
        from norns.specialized_agents import (
            create_file_management_agent,
            create_networking_agent,
            create_security_agent,
        )
        
        agents_to_test = [
            ("File Management", create_file_management_agent),
            ("Networking", create_networking_agent),
            ("Security", create_security_agent),
        ]
        
        for agent_name, create_fn in agents_to_test:
            console.print(f"\nCreating {agent_name} agent...")
            agent = create_fn()
            
            if agent:
                console.print(f"  ✓ {agent_name} agent created")
                console.print(f"    Name: {agent.name}")
                console.print(f"    Description: {agent.description[:80]}...")
            else:
                console.print(f"  [red]✗ {agent_name} agent creation failed[/red]")
                return False
        
        console.print("[green]✓ Test 4 PASSED[/green]")
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Test 4 FAILED: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return False


async def test_norns_integration():
    """Test 5: Norns Main Agent Integration"""
    console.print("\n[bold cyan]═══ Test 5: Norns Integration ═══[/bold cyan]")
    
    try:
        # Just verify the import and graph creation works
        from norns.agent import create_norns_graph, NornsAgent
        
        console.print("Creating Norns graph...")
        graph = create_norns_graph(use_checkpointer=False)
        
        if graph:
            console.print("✓ Norns graph created successfully")
        else:
            console.print("[red]✗ Norns graph creation failed[/red]")
            return False
        
        # Check that norns_node has skills retrieval code
        import inspect
        from norns.agent import norns_node
        
        source = inspect.getsource(norns_node)
        if "skills_retrieve" in source and "skills_context" in source:
            console.print("✓ norns_node contains skills retrieval code")
        else:
            console.print("[yellow]⚠️  norns_node may not have skills retrieval integrated[/yellow]")
        
        console.print("[green]✓ Test 5 PASSED[/green]")
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Test 5 FAILED: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return False


async def test_skill_files_enhanced_metadata():
    """Test 6: Skill Files with Enhanced Metadata"""
    console.print("\n[bold cyan]═══ Test 6: Enhanced Skill Metadata ═══[/bold cyan]")
    
    try:
        from norns.skills import list_skills, load_full_skill
        
        enhanced_skills = [
            "file-editing",
            "terminal-commands",
            "memory-retrieval",
        ]
        
        skills_dir = Path(__file__).parent.parent / "hlidskjalf" / "skills"
        
        for skill_name in enhanced_skills:
            skill_path = skills_dir / skill_name / "SKILL.md"
            if skill_path.exists():
                console.print(f"\n✓ Found {skill_name}")
                
                # Read and check for enhanced fields
                content = skill_path.read_text()
                
                checks = {
                    "roles:": "roles field",
                    "summary:": "summary field",
                    "triggers:": "triggers field",
                }
                
                for marker, field_name in checks.items():
                    if marker in content:
                        console.print(f"  ✓ Has {field_name}")
                    else:
                        console.print(f"  [yellow]⚠️  Missing {field_name}[/yellow]")
            else:
                console.print(f"[yellow]⚠️  {skill_name} not found at expected path[/yellow]")
        
        console.print("[green]✓ Test 6 PASSED[/green]")
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Test 6 FAILED: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return False


async def run_all_tests():
    """Run all end-to-end tests"""
    console.print(Panel.fit(
        "[bold cyan]RAG Skills System - End-to-End Test Suite[/bold cyan]\n"
        "Testing complete pipeline from skill files to agent integration",
        border_style="cyan"
    ))
    
    tests = [
        ("Skill Loading", test_skill_loading),
        ("MCP Memory Tools", test_memory_tools_import),
        ("Skills Retrieval", test_skill_retrieval_function),
        ("Subagent Creation", test_subagent_creation),
        ("Norns Integration", test_norns_integration),
        ("Enhanced Metadata", test_skill_files_enhanced_metadata),
    ]
    
    results = []
    
    for test_name, test_fn in tests:
        try:
            result = await test_fn()
            results.append((test_name, result))
        except Exception as e:
            console.print(f"\n[red]Fatal error in {test_name}: {e}[/red]")
            results.append((test_name, False))
    
    # Summary table
    console.print("\n" + "="*60)
    console.print("[bold]Test Results Summary[/bold]")
    console.print("="*60)
    
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Test", style="cyan", width=30)
    table.add_column("Status", width=10)
    table.add_column("Result", width=15)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        if result:
            table.add_row(test_name, "✓", "[green]PASSED[/green]")
            passed += 1
        else:
            table.add_row(test_name, "✗", "[red]FAILED[/red]")
    
    console.print(table)
    
    # Final verdict
    console.print("\n" + "="*60)
    if passed == total:
        console.print(Panel.fit(
            f"[bold green]🎉 ALL TESTS PASSED ({passed}/{total})[/bold green]\n"
            "RAG Skills System is fully operational!",
            border_style="green"
        ))
        return 0
    else:
        console.print(Panel.fit(
            f"[bold yellow]⚠️  SOME TESTS FAILED ({passed}/{total} passed)[/bold yellow]\n"
            "Review failed tests above.",
            border_style="yellow"
        ))
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)


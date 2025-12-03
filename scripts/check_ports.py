#!/usr/bin/env python3
"""
Utility to verify that a project's ports stay inside their assigned ranges.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "config" / "port_registry.yaml"

PROJECT_TYPE_RANGES = {
    "platform": {"api": "platform_api", "ui": "platform_ui"},
    "personal": {"api": "personal_api", "ui": "personal_ui"},
    "work": {"api": "work_api", "ui": "work_ui"},
    "sandbox": {"api": "sandbox_api", "ui": "sandbox_ui"},
}


class RegistryError(Exception):
    """Raised when the registry file cannot be processed."""


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        raise RegistryError(f"Registry not found at {REGISTRY_PATH}")
    with REGISTRY_PATH.open() as handle:
        return yaml.safe_load(handle)


def flatten_projects(data: dict) -> Dict[str, dict]:
    projects: Dict[str, dict] = {}
    for name, payload in data.get("platform", {}).items():
        projects[name] = {"id": name, "type": "platform", **payload}
    for name, payload in data.get("personal", {}).items():
        projects[name] = {"id": name, "type": "personal", **payload}
    for name, payload in data.get("work", {}).items():
        projects[name] = {"id": name, "type": "work", **payload}
    for name, payload in data.get("shared", {}).items():
        project_type = payload.get("type", "sandbox")
        projects[name] = {"id": name, "type": project_type, **payload}
    return projects


def port_in_range(port: int, range_def: dict) -> bool:
    return range_def["start"] <= port <= range_def["end"]


def find_matching_range(port: int, ranges: dict) -> Optional[str]:
    for name, definition in ranges.items():
        if port_in_range(port, definition):
            return name
    return None


def check_project_ports(project: dict, ranges: dict, reserved: List[dict]) -> dict:
    report = {"errors": [], "warnings": [], "passes": []}

    type_ranges = PROJECT_TYPE_RANGES.get(project.get("type", ""))
    reserved_by_port = {item["port"]: item for item in reserved}

    if "api_port" in project and project["api_port"] is not None:
        if not type_ranges:
            report["warnings"].append(
                f"API port {project['api_port']} has no range mapping for type '{project.get('type')}'."
            )
        else:
            range_name = type_ranges["api"]
            definition = ranges[range_name]
            if port_in_range(project["api_port"], definition):
                report["passes"].append(
                    f"API port {project['api_port']} is within {range_name} ({definition['start']}-{definition['end']})."
                )
            else:
                report["errors"].append(
                    f"API port {project['api_port']} falls outside {range_name} ({definition['start']}-{definition['end']})."
                )

    if "ui_port" in project and project["ui_port"] is not None:
        if not type_ranges:
            report["warnings"].append(
                f"UI port {project['ui_port']} has no range mapping for type '{project.get('type')}'."
            )
        else:
            range_name = type_ranges["ui"]
            definition = ranges[range_name]
            if port_in_range(project["ui_port"], definition):
                report["passes"].append(
                    f"UI port {project['ui_port']} is within {range_name} ({definition['start']}-{definition['end']})."
                )
            else:
                report["errors"].append(
                    f"UI port {project['ui_port']} falls outside {range_name} ({definition['start']}-{definition['end']})."
                )

    for service in project.get("services", []):
        port = service.get("port")
        if port is None:
            continue
        if port in reserved_by_port:
            reserved_entry = reserved_by_port[port]
            report["passes"].append(
                f"Service '{service.get('name')}' uses reserved port {port} ({reserved_entry['service']})."
            )
            continue
        matching_range = find_matching_range(port, ranges)
        if matching_range:
            report["passes"].append(
                f"Service '{service.get('name')}' port {port} fits {matching_range} ({ranges[matching_range]['start']}-{ranges[matching_range]['end']})."
            )
        else:
            report["warnings"].append(
                f"Service '{service.get('name')}' port {port} is outside declared ranges and not reserved."
            )

    return report


def format_report(project: dict, report: dict) -> List[str]:
    lines = [f"Port audit for project '{project['id']}' ({project.get('type', 'unknown')}):"]
    for entry in report["passes"]:
        lines.append(f"  ✓ {entry}")
    for entry in report["warnings"]:
        lines.append(f"  ! {entry}")
    for entry in report["errors"]:
        lines.append(f"  ✗ {entry}")
    return lines


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate project ports against registry ranges.")
    parser.add_argument("--project", "-p", required=True, help="Project identifier from port_registry.yaml")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    data = load_registry()
    projects = flatten_projects(data)
    project = projects.get(args.project)
    if not project:
        print(f"Unknown project '{args.project}'. Available: {', '.join(sorted(projects.keys()))}", file=sys.stderr)
        return 2

    ranges = data.get("ranges", {})
    reserved = data.get("reserved", [])
    report = check_project_ports(project, ranges, reserved)
    for line in format_report(project, report):
        print(line)

    if report["errors"]:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


"""
The Norns — The Weavers of Fate

Three sisters who sit at the Well of Urðr beneath Yggdrasil:
- Urðr (Urd): "That which has become" — analyzes the past
- Verðandi: "That which is happening" — observes the present
- Skuld: "That which shall be" — predicts and plans the future

Together they weave the threads of fate for all who dwell in the Nine Realms.
"""

from src.norns.agent import NornsAgent, create_norns_graph
from src.norns.tools import (
    get_platform_overview,
    list_projects,
    get_project_details,
    allocate_ports,
    check_deployment_health,
    generate_nginx_config,
    analyze_logs,
    predict_issues,
)

__all__ = [
    "NornsAgent",
    "create_norns_graph",
    "get_platform_overview",
    "list_projects",
    "get_project_details",
    "allocate_ports",
    "check_deployment_health",
    "generate_nginx_config",
    "analyze_logs",
    "predict_issues",
]


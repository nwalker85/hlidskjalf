#!/usr/bin/env python3
"""
Helper CLI for interacting with the GitLab Operations Board.

Usage examples:
  export GITLAB_TOKEN=glpat-xxxx
  ./scripts/ops_board.py list --labels wiki
  ./scripts/ops_board.py create --title "Update Architecture Index" --description "Sync latest docs" --labels wiki status::ready
  ./scripts/ops_board.py move --iid 12 --add status::in-progress --remove status::ready
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Sequence

import requests

PROJECT_ID = 2  # ravenhelm/hlidskjalf
BASE_URL = "https://gitlab.ravenhelm.test/api/v4"


def get_session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({"PRIVATE-TOKEN": token})
    return session


def as_csv(values: Sequence[str] | None) -> str:
    return ",".join(values or [])


def cmd_list(args: argparse.Namespace, session: requests.Session) -> None:
    params = {
        "per_page": args.per_page,
    }
    if args.labels:
        params["labels"] = as_csv(args.labels)
    resp = session.get(f"{BASE_URL}/projects/{PROJECT_ID}/issues", params=params)
    resp.raise_for_status()
    issues = resp.json()
    for issue in issues:
        labels = ", ".join(issue.get("labels", []))
        print(f"#{issue['iid']:>3} [{labels}] {issue['title']}")


def cmd_create(args: argparse.Namespace, session: requests.Session) -> None:
    payload = {
        "title": args.title,
        "description": args.description or "",
        "labels": as_csv(args.labels),
    }
    resp = session.post(f"{BASE_URL}/projects/{PROJECT_ID}/issues", json=payload)
    resp.raise_for_status()
    issue = resp.json()
    print(f"Created issue #{issue['iid']}: {issue['web_url']}")


def cmd_move(args: argparse.Namespace, session: requests.Session) -> None:
    payload: dict[str, str] = {}
    if args.add:
        payload["add_labels"] = as_csv(args.add)
    if args.remove:
        payload["remove_labels"] = as_csv(args.remove)
    if not payload:
        print("Nothing to update. Provide --add and/or --remove labels.", file=sys.stderr)
        sys.exit(1)
    resp = session.put(
        f"{BASE_URL}/projects/{PROJECT_ID}/issues/{args.iid}",
        json=payload,
    )
    resp.raise_for_status()
    print(f"Issue #{args.iid} updated.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GitLab Operations Board helper")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List issues (optionally filtered by labels)")
    p_list.add_argument("--labels", nargs="+", help="Filter by labels (e.g. status::in-progress)")
    p_list.add_argument("--per-page", type=int, default=50, help="Number of issues to fetch")
    p_list.set_defaults(func=cmd_list)

    p_create = sub.add_parser("create", help="Create a new issue")
    p_create.add_argument("--title", required=True, help="Issue title")
    p_create.add_argument("--description", help="Issue description")
    p_create.add_argument("--labels", nargs="+", default=[], help="Labels to apply")
    p_create.set_defaults(func=cmd_create)

    p_move = sub.add_parser("move", help="Add/remove labels to change status")
    p_move.add_argument("--iid", type=int, required=True, help="Issue IID (not ID)")
    p_move.add_argument("--add", nargs="+", help="Labels to add")
    p_move.add_argument("--remove", nargs="+", help="Labels to remove")
    p_move.set_defaults(func=cmd_move)

    return parser


def main() -> None:
    token = os.environ.get("GITLAB_TOKEN")
    if not token:
        print("Set GITLAB_TOKEN before running this script.", file=sys.stderr)
        sys.exit(1)

    parser = build_parser()
    args = parser.parse_args()
    session = get_session(token)
    args.func(args, session)


if __name__ == "__main__":
    main()


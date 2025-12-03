#!/usr/bin/env bash
#
# Sync docs/wiki/* into the GitLab wiki repository.
#
# Requirements:
#   - $GITLAB_TOKEN set to a GitLab PAT with wiki write access.
#   - git, rsync installed.
#
set -euo pipefail

if [[ -z "${GITLAB_TOKEN:-}" ]]; then
  echo "GITLAB_TOKEN is not set. Export a GitLab personal access token first." >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WIKI_SRC="${ROOT_DIR}/docs/wiki"
WIKI_TMP="${ROOT_DIR}/.tmp/wiki-sync"
WIKI_REPO="https://oauth2:${GITLAB_TOKEN}@gitlab.ravenhelm.test/ravenhelm/hlidskjalf.wiki.git"

if [[ ! -d "${WIKI_SRC}" ]]; then
  echo "Source directory ${WIKI_SRC} not found." >&2
  exit 1
fi

rm -rf "${WIKI_TMP}"
mkdir -p "$(dirname "${WIKI_TMP}")"
git clone --quiet "${WIKI_REPO}" "${WIKI_TMP}"

rsync -av --delete "${WIKI_SRC}/" "${WIKI_TMP}/" >/dev/null

pushd "${WIKI_TMP}" >/dev/null
git config user.name "Ravenhelm Platform Bot"
git config user.email "bot@ravenhelm.test"

if [[ -n "$(git status --porcelain)" ]]; then
  git add .
  git commit -m "Sync wiki from docs/wiki" >/dev/null
  git push origin main >/dev/null
  echo "Wiki synchronized successfully."
else
  echo "Wiki already up to date. No changes pushed."
fi
popd >/dev/null

rm -rf "${WIKI_TMP}"


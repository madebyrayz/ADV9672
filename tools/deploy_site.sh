#!/usr/bin/env bash
# Publish docs/ to the public site repo, which GitHub Pages serves at
# https://madebyrayz.github.io/ADV9672/.
#
# The source repo (madebyrayz/ADV9672-source) is private, and Pages on a free plan
# only serves public repos, so the built site lives in a second, public repo
# (madebyrayz/ADV9672) that holds nothing but the contents of docs/. This script
# splits the docs/ subtree into its own history and force-pushes it as that repo's
# main. Nothing outside docs/ ever leaves this repo.
#
#   python3 tools/build_static.py   # regenerate docs/
#   git add docs && git commit      # the split reads history, not the working tree
#   tools/deploy_site.sh
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

REMOTE=site
SITE_URL=https://github.com/madebyrayz/ADV9672.git
PREFIX=docs

git remote get-url "$REMOTE" >/dev/null 2>&1 || git remote add "$REMOTE" "$SITE_URL"

if [ -n "$(git status --porcelain -- "$PREFIX")" ]; then
  echo "docs/ has uncommitted changes; commit them first." >&2
  exit 1
fi

# subtree split prints a progress bar with carriage returns before the commit id.
SPLIT=$(git subtree split --prefix "$PREFIX" HEAD 2>/dev/null | tr -d '\r\n')
git push --force "$REMOTE" "$SPLIT:refs/heads/main"
echo "published $SPLIT -> https://madebyrayz.github.io/ADV9672/"

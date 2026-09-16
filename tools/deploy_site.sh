#!/usr/bin/env bash
# Publish docs/ to the public site repo, which GitHub Pages serves at
# https://madebyrayz.github.io/ADV9672/.
#
# The source repo (madebyrayz/ADV9672-source) is private, and Pages on a free plan
# only serves public repos, so the built site lives in a second, public repo
# (madebyrayz/ADV9672) that holds nothing but the contents of docs/.
#
# docs/ holds two kinds of file: the build, which is committed here, and the Lab's
# Gaussian files, which are ignored (600 MB of them would sit in this repo's history
# for good). So the site repo is not a split of this one; it is a clone that docs/ is
# copied into, ignored files included, and committed there. The clone is kept between
# runs so a push only carries what changed.
#
#   python3 tools/build_static.py   # regenerate docs/
#   git add docs && git commit      # what is published should match a commit here
#   tools/deploy_site.sh
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

SITE_URL=https://github.com/madebyrayz/ADV9672.git
SITE_DIR=.site    # ignored by git

if [ -n "$(git status --porcelain -- docs)" ]; then
  echo "docs/ has uncommitted changes; commit them first." >&2
  exit 1
fi

[ -d "$SITE_DIR/.git" ] || git clone -q "$SITE_URL" "$SITE_DIR"
git -C "$SITE_DIR" fetch -q origin main
git -C "$SITE_DIR" reset -q --hard origin/main

rsync -a --delete --exclude .git --exclude .DS_Store docs/ "$SITE_DIR"/
git -C "$SITE_DIR" add -A
if git -C "$SITE_DIR" diff --cached --quiet; then
  echo "site already matches docs/"
  exit 0
fi
git -C "$SITE_DIR" commit -q -m "Publish $(git rev-parse --short HEAD)"
git -C "$SITE_DIR" push -q origin HEAD:main
echo "published $(git rev-parse --short HEAD) -> https://madebyrayz.github.io/ADV9672/"

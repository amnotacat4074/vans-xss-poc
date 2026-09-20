#!/usr/bin/env bash
#
# setbase.sh -- set the attacker BASE URL in every file of this repo.
#
# The whole PoC hangs off ONE value: the base URL that the vans.com toolkit is
# told to load its runtime config from (via the ?domainName= query parameter).
# Every asset URL inside the JSON/SVG payloads is absolute and must equal that
# same base. This script rewrites that value everywhere, in one command.
#
# USE:
#   ./tools/setbase.sh https://raw.githubusercontent.com/<user>/<repo>/<branch>
#
# Example:
#   ./tools/setbase.sh https://raw.githubusercontent.com/nope8824/vans-xss-poc/main
#
# It is IDEMPOTENT: run it again with a new base and it rewrites the old one.
# It matches (and replaces) any of:
#   * an existing raw.githubusercontent.com/<u>/<r>/<b> base
#   * the placeholder https://raw.githubusercontent.com/USER/REPO/main
#   * legacy bases used during testing (surge.sh / *.lhr.life tunnels)
#
set -euo pipefail

BASE="${1:-}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ -z "$BASE" ]; then
  echo "usage: $0 https://raw.githubusercontent.com/<user>/<repo>/<branch>" >&2
  echo "   e.g: $0 https://raw.githubusercontent.com/nope8824/vans-xss-poc/main" >&2
  exit 2
fi
BASE="${BASE%/}"          # strip trailing slash
case "$BASE" in
  http://*|https://*) : ;;
  *) echo "ERROR: base must start with http:// or https://" >&2; exit 2 ;;
esac

python3 - "$ROOT" "$BASE" <<'PY'
import os, re, sys

root, base = sys.argv[1], sys.argv[2]

# Replace any previously-substituted attacker base (raw github / old tunnels)
# with the new one. Only the 3 path components of a raw URL are matched, so a
# trailing "/evil" or "/vfdp-..." is preserved.
PAT = re.compile(
    r'https://raw\.githubusercontent\.com/[^/\s"\'<>`]+/[^/\s"\'<>`]+/[^/\s"\'<>`]+'
    r'|https://[A-Za-z0-9-]+\.surge\.sh'
    r'|https://[A-Za-z0-9]+\.lhr\.life'
    r'|__BASE_URL__|\{\{BASE\}\}'
)

# Documentation is intentionally left alone (it describes the base generically).
SKIP = {'README.md', 'PUSH-TO-GITHUB.txt', 'setbase.sh', 'DEPLOY-README.txt'}

changed = 0
for dp, dirs, files in os.walk(root):
    dirs[:] = [d for d in dirs if d not in ('.git', 'tools')]
    for fn in files:
        if fn in SKIP:
            continue
        p = os.path.join(dp, fn)
        try:
            s = open(p, encoding='utf-8').read()
        except (UnicodeDecodeError, OSError):
            continue  # binary (png) -- never touched
        ns = PAT.sub(base, s)
        if ns != s:
            open(p, 'w', encoding='utf-8').write(ns)
            changed += 1

print(f"[+] base set to: {base}")
print(f"[+] rewrote {changed} file(s)")
PY

echo "[*] sanity check (should print the new base and no legacy bases):"
grep -rhoE 'https://(raw\.githubusercontent\.com/[^/"]+/[^/"]+/[^/"]+|[A-Za-z0-9-]+\.surge\.sh|[A-Za-z0-9]+\.lhr\.life)|__BASE_URL__|\{\{BASE\}\}' "$ROOT" \
  --exclude-dir=.git | sort -u | sed 's/^/    /'
echo "[*] now commit + push, then: /home/amnotacat/Desktop/vans-xss-poc/verify.sh $BASE"

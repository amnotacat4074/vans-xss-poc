#!/usr/bin/env bash
#
# verify_public.sh -- assert the PUBLISHED tree serves the impact payload.
#
# Checks, for every required path:
#   * HTTP 200 + Access-Control-Allow-Origin: *
#   * JSON   : "customsAssets" present, base rewritten, no {{BASE}} placeholder
#   * SVG    : inline onerror + onbegin, __XSS_FIRED marker, the
#              'XSS EXFILTRATION PROOF' overlay, window.top.__NUXT__ harvest,
#              localStorage harvest, position:fixed, and an exfil beacon
#              (either an OOB collector URL or the <BASE>/fired?d= sink)
#
# Usage:
#   ./tools/verify_public.sh https://raw.githubusercontent.com/<user>/<repo>/<branch>
#
set -uo pipefail

BASE="${1:-}"
[ -n "$BASE" ] || { echo "usage: $0 <base-url>" >&2; exit 2; }
BASE="${BASE%/}"

SVGS=(
  "evil/svg/customizer/icon-back.svg"
  "evil/svg/customizer/icon-close.svg"
  "evil/svg/randomizer/sk8-hi/sk8-hi-left-view.svg"
)
# endpoints files must carry the attacker asset keys
ENDPOINTS=(
  "vfdp-customs-prod-pdm/configurations/nora-en-us-sfcc/endpoints.json"
  "vfdp-customs-prod-pdm/configurations/nora-en-us-sfcc/endpoints-randomizer.json"
  "vfdp-customs-prod-pdm/configurations/nora-en-us-sfcc/endpoints-ugcentrypoint.json"
  "vfdp-customs-prod-pdm/configurations/nora-en-us-sfcc-canvas/endpoints.json"
)
# plain config/i18n JSON: just 200 + ACAO:* + no leftover placeholder
PLAINJSON=(
  "vfdp-customs-prod-pdm/configurations/nora-en-us-sfcc/configuration.json"
  "vfdp-customs-prod-pdm/configurations/nora-en-us-sfcc/translation.json"
  "vfdp-customs-prod-pdm/configurations/nora-en-us-sfcc-canvas/configuration.json"
)

TMP="$(mktemp)"; PASS=0; FAIL=0
trap 'rm -f "$TMP"' EXIT

fetch() { # -> writes body to $TMP, echoes "<code> <acao>"
  local hdr code acao
  hdr="$(curl -s -m 30 -H 'Cache-Control: no-cache' -D - -o "$TMP" "$BASE/$1")"
  code="$(printf '%s' "$hdr" | head -1 | awk '{print $2}')"
  acao="$(printf '%s' "$hdr" | grep -i '^access-control-allow-origin:' | tr -d '\r' | awk '{print $2}')"
  printf '%s %s' "${code:-000}" "${acao:-NONE}"
}

report() { # <name> <ok> <why>
  if [ "$2" = "1" ]; then PASS=$((PASS+1)); printf '  PASS  %-62s %s\n' "$1" "($3)"
  else FAIL=$((FAIL+1)); printf '  FAIL  %-62s %s\n' "$1" "$3"; fi
}

check_common() { # <path> <code> <acao>
  local p="$1" code="$2" acao="$3" why=""
  [ "$code" = "200" ] || why="$why http=$code"
  [ "$acao" = "*" ]   || why="$why acao=${acao:-NONE}"
  [ -z "$why" ] && { echo 1; return; }; echo "0:$why"
}

echo "[*] base: $BASE"
for p in "${SVGS[@]}"; do
  read -r code acao < <(fetch "$p")
  r="$(check_common "$p" "$code" "$acao")"
  if [ "${r%%:*}" = "0" ]; then report "$p" 0 "${r#0:}"; continue; fi
  why=""
  grep -q 'onerror='                 "$TMP" || why="$why no-onerror"
  grep -q 'onbegin='                 "$TMP" || why="$why no-onbegin"
  grep -q '__XSS_FIRED=1'            "$TMP" || why="$why no-marker"
  grep -q '__EXFIL_RAN'              "$TMP" || why="$why no-exfil-guard"
  grep -q 'XSS EXFILTRATION PROOF'   "$TMP" || why="$why no-overlay-title"
  grep -q 'localStorage.getItem(k)'  "$TMP" || why="$why no-ls-harvest"
  grep -q 'window.top'               "$TMP" || why="$why no-top-access"
  grep -q '__NUXT__'                 "$TMP" || why="$why no-nuxt"
  grep -q 'position:fixed'           "$TMP" || why="$why no-overlay"
  grep -q 'fetch(EXFIL'              "$TMP" || why="$why no-exfil-fetch"
  grep -qE 'pipedream\.net|webhook\.site|/fired\?d=' "$TMP" || why="$why no-beacon"
  [ -z "$why" ] && report "$p" 1 "200 acao=* impact-markers" || report "$p" 0 "$why"
done

for p in "${ENDPOINTS[@]}"; do
  read -r code acao < <(fetch "$p")
  r="$(check_common "$p" "$code" "$acao")"
  if [ "${r%%:*}" = "0" ]; then report "$p" 0 "${r#0:}"; continue; fi
  why=""
  grep -q '"customsAssets"' "$TMP" || why="$why no-customsAssets"
  grep -q "$BASE/evil"      "$TMP" || why="$why base-not-rewritten"
  grep -q '{{BASE}}'        "$TMP" && why="$why placeholder-left"
  [ -z "$why" ] && report "$p" 1 "200 acao=* asset-keys" || report "$p" 0 "$why"
done

for p in "${PLAINJSON[@]}"; do
  read -r code acao < <(fetch "$p")
  r="$(check_common "$p" "$code" "$acao")"
  if [ "${r%%:*}" = "0" ]; then report "$p" 0 "${r#0:}"; continue; fi
  why=""
  grep -q '{{BASE}}' "$TMP" && why="$why placeholder-left"
  python3 -c "import json,sys; json.load(open('$TMP'))" 2>/dev/null || why="$why invalid-json"
  [ -z "$why" ] && report "$p" 1 "200 acao=* valid-json" || report "$p" 0 "$why"
done

echo
echo "[*] result: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]

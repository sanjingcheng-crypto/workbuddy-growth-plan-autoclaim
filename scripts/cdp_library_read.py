# -*- coding: utf-8 -*-
import sys, time
from playwright.sync_api import sync_playwright
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except: pass

def log(*a): print(*a, flush=True)
MORE=(103,263); DOC="【示例】在线文档：如何创作一篇文档"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = b.contexts[0].pages[0]
    pg.keyboard.press("Escape"); pg.wait_for_timeout(500)
    pg.mouse.move(*MORE); pg.wait_for_timeout(900)
    for _ in range(4):
        r = pg.evaluate("""(name)=>{const e=[...document.querySelectorAll('div,li,span,a')].find(x=>(x.innerText||'').replace(/\u00a0/g,' ').trim()===name);if(!e)return 'nf';e.click();return 'ok';}""", "乐享知识库")
        if r!='nf': break
        pg.mouse.move(*MORE); pg.wait_for_timeout(600)
    pg.wait_for_timeout(3500)
    pg.locator("li.tencent-lexiang-list__row", has_text=DOC).first.click(timeout=8000)
    pg.wait_for_timeout(4000)
    # 找 iframe 帧并滚动
    fr = None
    for f in pg.frames:
        if 'lexiangla' in f.url: fr = f; break
    log("iframe frame:", fr.url if fr else None)
    if fr:
        try:
            for i in range(8):
                fr.evaluate("""()=>{const d=document.scrollingElement||document.body; if(d){d.scrollTop+=400;} window.scrollBy(0,400);}""")
                pg.wait_for_timeout(400)
            log("scrolled iframe")
        except Exception as e:
            log("scroll err:", repr(e))
    pg.wait_for_timeout(10000)
    log("DONE dwell")

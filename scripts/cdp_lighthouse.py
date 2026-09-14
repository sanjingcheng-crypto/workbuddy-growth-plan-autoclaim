# -*- coding: utf-8 -*-
"""
Expert_lighthouse 实测 v4：正确路由到「腾讯轻量云专家」后发具体操作请求，
点击「连接 Lighthouse 运维」尝试绑定腾讯云，观察是否自动连上 / 进入 OAuth。
"""
import os, sys, time
from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

JS_TAB = """() => { const e=[...document.querySelectorAll('button,[role=tab]')].find(x=>(x.innerText||'').trim()==='专家·技能·连接器'); if(!e) return 'nf'; e.click(); return 'ok'; }"""
JS_SUB = """(name) => { const e=[...document.querySelectorAll('button,[role=tab],div[class*=tab]')].find(x=>(x.innerText||'').trim()===name); if(!e) return 'nf'; e.click(); return 'ok'; }"""
JS_CARD = """(name) => { const main=[...document.querySelectorAll('div[class*=ec-card-main]')]; const pool = main.length ? main : [...document.querySelectorAll('div[class*=card]')]; const c = pool.find(x => (x.innerText||'').includes(name)); if(!c) return 'nf'; c.click(); return 'ok'; }"""
JS_SUMMON = """() => { const e=[...document.querySelectorAll('button')].find(x=>(x.innerText||'').includes('召唤')); if(!e) return 'nf'; e.click(); return 'ok:'+(e.innerText||'').trim(); }"""
JS_SEND = """() => {
  const sel='div[class*=cr-send-button],div[class*=cr-input-toolbar__send],div[class*=_large_hg7y0_],div[class*=_large_]';
  const c=[...document.querySelectorAll(sel)].map(e=>{const r=e.getBoundingClientRect();return {x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2),w:Math.round(r.width)};}).filter(o=>o.w>20&&o.y>0); c.sort((a,b)=>b.x-a.x); return c[0]||null; }"""
# 优先点「连接」(且位于 Lighthouse 卡片内)；否则点「连接腾讯云账号」之类
JS_CONNECT = """() => {
  const btns=[...document.querySelectorAll('button')].filter(x=>(x.innerText||'').trim()==='连接');
  const tgt = btns.find(x=>{const p=x.closest('div'); return p && (p.innerText||'').includes('Lighthouse');}) || btns[0];
  if(!tgt) return 'no-connect-btn';
  tgt.click(); return 'clicked:连接';
}"""
JS_CONNECTED_MARK = """() => { const t=document.body.innerText;
  return { hasLighthouse: t.includes('Lighthouse'), hasConnect: t.includes('连接腾讯云'),
           hasAuth: /授权|登录腾讯云|扫码/.test(t), hasInstance: /实例|防火墙|快照|监控/.test(t) }; }"""

PROMPT = "查我的轻量云实例列表"


def send_prompt(pg):
    for _ in range(4):
        try:
            pg.locator('div[class*="_editable_"]').first.click(timeout=6000)
            pg.wait_for_timeout(500)
            pg.keyboard.press("Control+a"); pg.keyboard.press("Delete")
            pg.wait_for_timeout(300)
            pg.keyboard.type(PROMPT, delay=30)
            pg.wait_for_timeout(900)
            s = pg.evaluate(JS_SEND)
            if s:
                pg.mouse.click(s["x"], s["y"])
            time.sleep(9)
            return True
        except Exception as e:
            print("  send retry:", e); time.sleep(2)
    return False


def main():
    port = 9222
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://127.0.0.1:%d" % port)
        pg = b.contexts[0].pages[0]
        # 若当前已在 腾讯轻量云专家 对话且连接器卡片还在，直接尝试点连接
        pre = pg.evaluate(JS_CONNECTED_MARK)
        print("PRE_MARK:", pre)
        if pre.get("hasLighthouse"):
            c = pg.evaluate(JS_CONNECT)
            print("PRE_CONNECT:", c)
            if c != "no-connect-btn":
                pg.wait_for_timeout(8000)
                print("POST_MARK:", pg.evaluate(JS_CONNECTED_MARK))
                print("PAGES:", [pp.url for pp in b.contexts[0].pages])
                return
        # 否则重新走：专家面板 -> 搜索 -> 召唤 -> 发请求 -> 连接
        pg.evaluate(JS_TAB); pg.wait_for_timeout(2000)
        pg.evaluate(JS_SUB, "专家"); pg.wait_for_timeout(2000)
        try:
            inp = pg.locator('input[placeholder*="搜索"]').first
            inp.click(timeout=5000); inp.fill("轻量云")
        except Exception as e:
            print("search fail:", e)
        pg.wait_for_timeout(2500)
        r = pg.evaluate(JS_CARD, "腾讯轻量云专家")
        print("card:", r)
        if r == "nf":
            print("FAIL: 无卡片"); return
        pg.wait_for_timeout(3000)
        print("detail:", pg.evaluate("""() => { const h=document.querySelector('div[class*=ec-card-title-row]'); return h?h.innerText.trim():'?'; }"""))
        pg.evaluate(JS_SUMMON); pg.wait_for_timeout(3500)
        send_prompt(pg); pg.wait_for_timeout(2500)
        c = pg.evaluate(JS_CONNECT)
        print("CONNECT_CLICK:", c)
        if c == "no-connect-btn":
            print("未出现连接按钮（可能已连或专家未调用连接器）")
        else:
            pg.wait_for_timeout(9000)
            print("POST_MARK:", pg.evaluate(JS_CONNECTED_MARK))
            print("PAGES:", [pp.url for pp in b.contexts[0].pages])
        print("DONE.")


if __name__ == "__main__":
    main()

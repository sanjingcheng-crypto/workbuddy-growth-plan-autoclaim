# -*- coding: utf-8 -*-
"""
expert_5 召唤专家（CDP 接管桌面客户端 UI）
==========================================

关键 DOM 契约（2026-09-13 实测，WorkBuddy 5.2.x / Electron 37）：
- 入口：侧栏 tab「专家·技能·连接器」→ 子 tab「专家」
- **专家卡片本身没有「召唤」按钮**；召唤键只在「点开卡片后的详情页」里。
  → 必须先点卡片（按名字匹配），进详情后再点「召唤 XX」。
- 专家列表是**虚拟滚动**，卡片只渲染可视区；直接 get_by_text 等会超时。
  → 先滚动列表把目标卡片加载进 DOM，再用卡片全名（如「教学设计总顾问-企鹅教师助手」）精确匹配点击。

计数特性：expert_5 召唤后**服务端滞后统计**（实测召唤后任务数立刻 +1，但 progress 仍 2/5，
推测需专家真实响应 + 小时级延迟）。靠每小时定时任务的 harvest 兜底计入并领取。

用法：
  python cdp_experts.py                       # 用下方 DEFAULT_POOL 里还没召唤过的专家
  python cdp_experts.py --names "吴八哥,企鹅教师助手,文爆爆"
  python cdp_experts.py --no-dialog           # 不尝试点连接器「连接」框
"""
import argparse
import os
import sys
import time

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))

# 候选专家池（用全名，便于虚拟列表精确匹配）。换账号/换电脑时按需增减。
DEFAULT_POOL = [
    "吴八哥",                 # 高级开发工程师
    "文爆爆",                 # 内容创作专家
    "教学设计总顾问-企鹅教师助手",
    "PPT制作专家",
    "数据分析专家",
    "WindAlice万得金融专家",
    "战略咨询顾问",
    "内容创作专家",
]

# 点「专家·技能·连接器」tab
JS_TAB = """() => { const e=[...document.querySelectorAll('button,[role=tab]')]
  .find(x=>(x.innerText||'').trim()==='专家·技能·连接器'); if(!e) return 'nf'; e.click(); return 'ok'; }"""
# 点子 tab（精确匹配文本）
JS_SUB = """(name) => { const e=[...document.querySelectorAll('button,[role=tab],div[class*=tab]')]
  .find(x=>(x.innerText||'').trim()===name); if(!e) return 'nf'; e.click(); return 'ok'; }"""
# 滚动所有可滚元素 + 页面，触发虚拟列表加载
JS_SCROLL = """() => { for (const el of document.querySelectorAll('div')) {
  if (el.scrollHeight > el.clientHeight + 80) try { el.scrollTop = el.scrollHeight; } catch(e){} }
  window.scrollTo(0, 1e7); return 'ok'; }"""
# 点名字匹配的卡片（卡片 innerText 含 name 即可，不要求卡片带召唤按钮）
# 5.2.6 实测：专家卡片根为 div.ec-card-main；旧选择器 div[class*=card] 会先命中
# ec-card-head/ec-card-body 等子元素，点它不触发卡片点击 → 优先 ec-card-main，回退旧选择器。
JS_CARD = """(name) => {
  const main=[...document.querySelectorAll('div[class*=ec-card-main]')];
  const pool = main.length ? main : [...document.querySelectorAll('div[class*=card]')];
  const c = pool.find(x => (x.innerText||'').includes(name));
  if(!c) return 'nf'; c.click(); return 'ok'; }"""
# 点详情里的「召唤 XX」按钮
JS_SUMMON = """() => { const e=[...document.querySelectorAll('button')]
  .find(x=>(x.innerText||'').includes('召唤')); if(!e) return 'nf'; e.click();
  return 'ok:'+(e.innerText||'').trim(); }"""
# 取最右的发送键（_large_hg7y0_ 同名下有两个：附件 x≈900、发送 x≈1158）
JS_SEND = """() => { const c=[...document.querySelectorAll('div[class*="_large_hg7y0_"]')]
  .map(e=>{const r=e.getBoundingClientRect();return {x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2),w:Math.round(r.width)};})
  .filter(o=>o.w>20&&o.y>0); c.sort((a,b)=>b.x-a.x); return c[0]||null; }"""
# 任务数侧栏
JS_TASKS = "() => (document.body.innerText.match(/\\u4efb\\u52a1\\s*\\((\\d+)\\)/) || [])[1] || '?'"
# 连接器授权框：有「连接」就点（尝试满足 Expert_lighthouse），否则点「暂不」关掉
JS_DIALOG = """(prefer) => { const btns=[...document.querySelectorAll('button')];
  const pick=btns.find(x=>(x.innerText||'').trim()===prefer);
  const other=btns.find(x=>['连接','暂不'].includes((x.innerText||'').trim()) && x!==pick);
  if(pick){pick.click();return 'clicked:'+prefer;}
  if(other){other.click();return 'clicked:'+other.innerText.trim();}
  return 'no-dialog'; }"""


def send_msg(pg):
    for _ in range(3):
        try:
            pg.locator('div[class*="_editable_"]').first.click(timeout=6000)
            pg.wait_for_timeout(600)
            pg.keyboard.press("Control+a")
            pg.keyboard.press("Delete")
            pg.wait_for_timeout(400)
            pg.keyboard.type("你好，请用一句话介绍你能帮我做什么", delay=20)
            pg.wait_for_timeout(900)
            s = pg.evaluate(JS_SEND)
            if s:
                pg.mouse.click(s["x"], s["y"])
            time.sleep(6)
            return True
        except Exception:
            time.sleep(2)
    return False


def summon_one(pg, name, handle_dialog):
    pg.evaluate(JS_TAB)
    pg.wait_for_timeout(2200)
    pg.evaluate(JS_SUB, "专家")
    pg.wait_for_timeout(2200)
    # 滚动加载虚拟列表（多次）
    for _ in range(6):
        pg.evaluate(JS_SCROLL)
        pg.wait_for_timeout(600)
    before = pg.evaluate(JS_TASKS)
    r = pg.evaluate(JS_CARD, name)
    if r == "nf":
        return False, "card not found (virtual list not loaded / name mismatch)"
    pg.wait_for_timeout(3000)
    r2 = pg.evaluate(JS_SUMMON)
    if r2 == "nf":
        return False, "summon btn not found in detail"
    pg.wait_for_timeout(4200)
    ok = send_msg(pg)
    d = "skip"
    if handle_dialog:
        pg.wait_for_timeout(1500)
        d = pg.evaluate(JS_DIALOG, "连接")
        pg.wait_for_timeout(3000)
    return True, "sent=%s dialog=%s tasks %s->%s" % (ok, d, before, pg.evaluate(JS_TASKS))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", help="逗号分隔的专家名（全名优先）")
    ap.add_argument("--no-dialog", action="store_true", help="不尝试点连接器授权框")
    ap.add_argument("--port", default=9222, type=int)
    args = ap.parse_args()

    names = [n.strip() for n in (args.names or "").split(",") if n.strip()] or DEFAULT_POOL

    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://127.0.0.1:%d" % args.port)
        pg = b.contexts[0].pages[0]
        ok_n = 0
        for name in names:
            print("== %s ==" % name)
            good, msg = summon_one(pg, name, not args.no_dialog)
            print("   %s  %s" % ("OK" if good else "FAIL", msg))
            if good:
                ok_n += 1
            time.sleep(3)
        print("\n召唤成功 %d/%d。expert_5 计数滞后，稍后(小时级)由定时任务兜底计入并领取。" % (ok_n, len(names)))


if __name__ == "__main__":
    main()

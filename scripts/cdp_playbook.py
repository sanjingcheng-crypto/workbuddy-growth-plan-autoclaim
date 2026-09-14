# -*- coding: utf-8 -*-
"""
playbook_prompt「探索优秀灵感」自动完成（CDP 接管桌面客户端 UI）
================================================================

2026-09-14 实测跑通（WorkBuddy 5.2.6 / Electron 37），已成功领取 +100 积分 / +5 能量。

官方要求：进入「灵感」界面 → 选任意 1 款灵感案例 → 点「+ 做同款」→ 完成 1 次对话。

关键 DOM 契约（5.2.6 实测）：
- 侧栏「更多」是 **hover 展开**的下拉菜单（点击不行！）：
    SPAN「更多」在 (约 48,252)，hover 后出现 `.wb-dropdown__label` 菜单项
    菜单项：我的文件 / 腾讯文档 / ima知识库 / 乐享知识库 / 灵感
- 「灵感」页：卡片容器 `dc-playbook-grid`，卡片 `dc-card-cover|info|title-row|footer`
- 点卡片 → 弹详情浮层 `dc-detail-overlay.is-open` / `dc-detail-modal`，内含「做同款」按钮
- 点「做同款」→ 输入框 `div[class*=_editable_]` **自动预填完整提示词**，进入对话界面
- 发送键：`div[class*="_large_"]` 中 x 最大的那个（右侧发送图标）

用法：
  python cdp_playbook.py            # 默认点第一张灵感卡片
  python cdp_playbook.py --index 3  # 点第 3 张卡片
  python cdp_playbook.py --port 9222
"""
import argparse
import os
import sys
import time

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 侧栏「更多」：hover 展开下拉
JS_HOVER_MORE = """() => {
  const e=[...document.querySelectorAll('span,div,button')]
    .find(x=>(x.innerText||'').trim()==='更多');
  if(!e) return null;
  const r=e.getBoundingClientRect();
  return {x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)};
}"""
# 下拉菜单项（hover 后才在 DOM）
JS_MENU_ITEM = """(name) => {
  const e=[...document.querySelectorAll('.wb-dropdown__label, [class*=dropdown] *')]
    .find(x=>(x.innerText||'').trim()===name);
  if(!e) return null;
  const r=e.getBoundingClientRect();
  return {x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)};
}"""
# 灵感卡片（返回第 idx 张可点击卡片封面中心）
JS_CARD = """(idx) => {
  let cards=[...document.querySelectorAll('.dc-card-cover')];
  if(!cards.length) cards=[...document.querySelectorAll('.dc-card-info, .dc-card-main')];
  const c=cards[idx]||cards[0];
  if(!c) return null;
  const r=c.getBoundingClientRect();
  return {x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)};
}"""
# 「做同款」按钮
JS_TONG = """() => {
  const e=[...document.querySelectorAll('button,[role=button]')]
    .find(x=>(x.innerText||'').trim()==='做同款');
  if(!e) return null;
  const r=e.getBoundingClientRect();
  return {x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)};
}"""
# 发送键（最右的 _large_ 图标）
JS_SEND = """() => {
  const c=[...document.querySelectorAll('div[class*="_large_"]')]
    .map(e=>{const r=e.getBoundingClientRect();
      return {x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2), w:Math.round(r.width)};})
    .filter(o=>o.w>20 && o.y>0);
  c.sort((a,b)=>b.x-a.x);
  return c[0]||null;
}"""
# 编辑框是否已预填
JS_EDITABLE = """() => {
  const e=document.querySelector('div[class*="_editable_"]');
  return e ? (e.innerText||'').trim().slice(0,80) : null;
}"""


def open_playbook(pg):
    """hover「更多」→ 点「灵感」，返回是否成功"""
    pos = pg.evaluate(JS_HOVER_MORE)
    if not pos:
        return False, "未找到侧栏「更多」"
    pg.mouse.move(pos["x"], pos["y"])
    pg.wait_for_timeout(1300)
    item = pg.evaluate(JS_MENU_ITEM, "灵感")
    if not item:
        # 再 hover 一次（菜单有时会收起）
        pg.mouse.move(pos["x"], pos["y"])
        pg.wait_for_timeout(1500)
        item = pg.evaluate(JS_MENU_ITEM, "灵感")
    if not item:
        return False, "下拉菜单未出现「灵感」（需 hover 展开）"
    pg.mouse.click(item["x"], item["y"])
    pg.wait_for_timeout(3200)
    return True, "已进入灵感页"


def do_one(pg, idx):
    card = pg.evaluate(JS_CARD, idx)
    if not card:
        return False, "未找到灵感卡片（页面未加载完？）"
    pg.mouse.click(card["x"], card["y"])
    pg.wait_for_timeout(2600)
    tong = pg.evaluate(JS_TONG)
    if not tong:
        return False, "详情浮层未出现「做同款」按钮"
    pg.mouse.click(tong["x"], tong["y"])
    pg.wait_for_timeout(4200)
    # 等待输入框预填
    text = None
    for _ in range(6):
        text = pg.evaluate(JS_EDITABLE)
        if text:
            break
        pg.wait_for_timeout(900)
    if not text:
        return False, "输入框未预填提示词"
    send = pg.evaluate(JS_SEND)
    if not send:
        return False, "未找到发送键"
    pg.mouse.click(send["x"], send["y"])
    pg.wait_for_timeout(4000)
    return True, "已发送做同款对话（预填前 40 字：%s…）" % text[:40]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default=0, type=int, help="点第几张灵感卡片（0 起）")
    ap.add_argument("--port", default=9222, type=int)
    ap.add_argument("--shot", help="执行后截图保存路径（可选）")
    args = ap.parse_args()

    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://127.0.0.1:%d" % args.port)
        pages = [x for c in b.contexts for x in c.pages]
        pg = next((x for x in pages if "index.html" in x.url), None)
        if not pg:
            print("FAIL 未找到 WorkBuddy 主页面（9222 是否连通？）")
            return 1
        ok, msg = open_playbook(pg)
        print(("OK   " if ok else "FAIL ") + msg)
        if ok:
            ok2, msg2 = do_one(pg, args.index)
            print(("OK   " if ok2 else "FAIL ") + msg2)
        if args.shot:
            try:
                pg.screenshot(path=args.shot)
                print("截图:", args.shot)
            except Exception as e:
                print("截图失败:", e)
        print("\n提示：完成后跑 harvest.py（不带 --list）领取 playbook_prompt +100c。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""Hp_Appearance：在用户菜单里切换「外观 深色/浅色」，检测主题是否真的切换。

用法:
  python cdp_appearance.py --set dark    # 切到深色
  python cdp_appearance.py --set light   # 切回浅色
"""
import sys, json, argparse, time
from playwright.sync_api import sync_playwright
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(*a):
    print(*a, flush=True)


JS_THEME = r"""() => {
  const h = document.documentElement, b = document.body;
  const cands = {};
  ['class','data-theme','data-color-scheme','style'].forEach(k=>{ cands['html.'+k] = (h.getAttribute(k)||'').toString().slice(0,200); });
  ['class','data-theme'].forEach(k=>{ cands['body.'+k] = (b.getAttribute(k)||'').toString().slice(0,200); });
  cands.bg = getComputedStyle(b).backgroundColor;
  cands.color = getComputedStyle(b).color;
  return cands;
}"""

JS_XPATH_MENU = r"""() => {
  const e = [...document.querySelectorAll('div.user-menu-item, .user-menu-item')].find(x=>/外观/.test(x.innerText||''));
  if (!e) return null;
  const r = e.getBoundingClientRect();
  return {disabled: /disabled/.test(e.className||''), x:Math.round(r.x), y:Math.round(r.y),
          w:Math.round(r.width), h:Math.round(r.height)};
}"""

JS_BTN = r"""(want) => {
  const b = [...document.querySelectorAll('button.user-menu-theme-option, .user-menu-theme-option')].find(x=>(x.innerText||'').trim()===want);
  if (!b) return null;
  const r = b.getBoundingClientRect();
  return {t:(b.innerText||'').trim(), cls:(b.className||'').toString().slice(0,80),
          x:Math.round(r.x), y:Math.round(r.y),
          cx:Math.round(r.x+r.width/2), cy:Math.round(r.y+r.height/2),
          w:Math.round(r.width), h:Math.round(r.height)};
}"""


def open_menu(pg):
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(400)
    pg.mouse.click(130, 686)
    pg.wait_for_timeout(1600)
    pg.mouse.move(150, 690)
    pg.wait_for_timeout(300)
    pg.mouse.move(140, 600)
    pg.wait_for_timeout(600)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", dest="target", default="dark", choices=["dark", "light"])
    ap.add_argument("--shot", default=None)
    args = ap.parse_args()
    want = "深色" if args.target == "dark" else "浅色"

    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        pg = b.contexts[0].pages[0]
        log("BEFORE_THEME:", json.dumps(pg.evaluate(JS_THEME), ensure_ascii=False))

        open_menu(pg)
        menu = pg.evaluate(JS_XPATH_MENU)
        log("MENU_ITEM:", json.dumps(menu, ensure_ascii=False))
        btn = pg.evaluate(JS_BTN, want)
        log("TARGET_BTN:", json.dumps(btn, ensure_ascii=False))
        if not btn:
            log("ERR: 未找到外观按钮")
            return

        log("HOVER menu item first...")
        pg.mouse.move(140, 517)
        pg.wait_for_timeout(700)
        btn2 = pg.evaluate(JS_BTN, want)
        log("TARGET_BTN_AFTER_HOVER:", json.dumps(btn2, ensure_ascii=False))
        use = btn2 or btn

        pg.mouse.click(use["cx"], use["cy"])
        log("CLICKED at (%d,%d)" % (use["cx"], use["cy"]))
        pg.wait_for_timeout(2000)

        if args.shot:
            try:
                pg.screenshot(path=args.shot)
                log("SHOT:", args.shot)
            except Exception as e:
                log("SHOT_ERR:", e)

        log("AFTER_THEME:", json.dumps(pg.evaluate(JS_THEME), ensure_ascii=False))
        log("ACTIVE_NOW:", pg.evaluate(r"""()=>{const b=[...document.querySelectorAll('.user-menu-theme-option')].map(x=>(x.innerText||'').trim()+'|'+(/active/.test(x.className)?'ACTIVE':'-'));return b.join(' , ');}"""))


if __name__ == "__main__":
    main()

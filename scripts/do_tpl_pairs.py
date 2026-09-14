# -*- coding: utf-8 -*-
"""按 (顶层模板, 子模板) 列表补齐 template_5 的不同模板种类。"""
import sys, time
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"
JS_CLICK_TEXT = """(args) => {
  const [sel, name] = args;
  const els = [...document.querySelectorAll(sel)];
  const hit = els.find(e => (e.innerText||'').trim() === name);
  if (!hit) return false;
  hit.scrollIntoView(); hit.click(); return true;
}"""
JS_PILLS = """() => [...document.querySelectorAll('[class*=quick-actions__item]')]
  .map(e => (e.innerText||'').trim()).filter(t => t && t !== '更多')"""
JS_MAIN_ED = """() => {
  const eds = [...document.querySelectorAll('div[class*=editable]')];
  if (!eds.length) return false;
  eds.sort((a,b)=>{const ra=a.getBoundingClientRect(), rb=b.getBoundingClientRect();
    return (rb.width*rb.height)-(ra.width*ra.height);});
  eds[0].click(); return true;
}"""
JS_SEND = """() => {
  const c = [...document.querySelectorAll('div[class*=large_hg7y0_]')]
    .map(e => { const r=e.getBoundingClientRect();
      return {x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2), w:Math.round(r.width)}; })
    .filter(o => o.w>10 && o.y>0);
  if (!c.length) return null;
  c.sort((a,b)=>b.x-a.x); return [c[0].x, c[0].y];
}"""

def connect():
    p = sync_playwright().start()
    b = p.chromium.connect_over_cdp(CDP)
    for ctx in b.contexts:
        for pg in ctx.pages:
            if "WorkBuddy" in (pg.title() or "") or "index.html" in pg.url:
                return p, b, pg
    return p, b, b.contexts[0].pages[0]

def ensure_composer(pg, scene="日常办公"):
    for _ in range(4):
        pg.evaluate(JS_CLICK_TEXT, ["button, [role=button], div[class*=tab], [class*=pill]", "新建任务"])
        pg.wait_for_timeout(2500)
        pg.evaluate(JS_CLICK_TEXT, ["[class*=wb-scene-tabs__pill]", scene])
        pg.wait_for_timeout(2000)
        tops = pg.evaluate(JS_PILLS) or []
        if tops:
            return tops
        pg.keyboard.press("Escape"); pg.wait_for_timeout(800)
    return None

def main():
    # CLI: 每个参数为 "场景|顶层|子" （子可省略）
    pairs = []
    for a in sys.argv[1:]:
        parts = a.split("|")
        scene = parts[0] if parts[0] in ("日常办公", "代码开发", "设计创意") else "日常办公"
        top = parts[1] if len(parts) > 1 else (parts[0] if parts[0] not in ("日常办公","代码开发","设计创意") else None)
        sub = parts[2] if len(parts) > 2 else None
        pairs.append((scene, top, sub))
    p, b, pg = connect()
    done = 0
    try:
        for scene, top, sub in pairs:
            tops = ensure_composer(pg, scene)
            if not tops:
                print("无法回到 composer(%s)，停止" % scene); break
            if not top or top not in tops:
                print("顶层 %s 不在列表 %s，跳过" % (top, tops)); continue
            pg.evaluate(JS_CLICK_TEXT, ["[class*=quick-actions__item]", top])
            pg.wait_for_timeout(1800)
            if sub:
                subs = pg.evaluate(JS_PILLS) or []
                if sub in subs:
                    pg.evaluate(JS_CLICK_TEXT, ["[class*=quick-actions__item]", sub])
                    pg.wait_for_timeout(1500)
            pg.evaluate(JS_MAIN_ED); pg.wait_for_timeout(400)
            pg.keyboard.type("请帮我处理一下这份材料", delay=20); pg.wait_for_timeout(700)
            xy = pg.evaluate(JS_SEND)
            if not xy:
                print("迭代 %s/%s/%s: 找不到发送键" % (scene, top, sub)); continue
            pg.mouse.click(xy[0], xy[1])
            print("迭代: 场景=%s 顶层=%s 子=%s 发送@%s" % (scene, top, sub, xy))
            pg.wait_for_timeout(8000)
            done += 1
    finally:
        p.stop()
    print("已发起 %d 个模板任务" % done)

if __name__ == "__main__":
    main()

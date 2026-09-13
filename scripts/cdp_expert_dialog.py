"""检查专家对话是否有回复 + 用搜索框精确召唤企鹅教师助手。"""
import os
import time

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))  # 截图输出到脚本所在目录

JS_TAB = """() => { const e=[...document.querySelectorAll('button,[role=tab]')]
  .find(x=>(x.innerText||'').trim()==='专家·技能·连接器'); if(!e) return 'nf'; e.click(); return 'ok'; }"""
JS_SEARCH = """(q) => {
  const inp = document.querySelector('input[placeholder*="\u641c\u7d22"]');
  if (!inp) return 'no-search-box';
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(inp, q);
  inp.dispatchEvent(new Event('input', {bubbles: true}));
  return 'typed';
}"""
JS_CARD = """(name) => {
  const e = [...document.querySelectorAll('*')]
    .find(x => x.childElementCount===0 && (x.innerText||'').trim().includes(name));
  if (!e) return 'nf';
  (e.closest('div[class*=card]') || e).click(); return 'ok';
}"""
JS_SUMMON = """() => { const e=[...document.querySelectorAll('button')]
  .find(x=>(x.innerText||'').includes('召唤')); if(!e) return 'nf'; e.click();
  return 'ok:'+(e.innerText||'').trim(); }"""
JS_SEND = """() => { const c=[...document.querySelectorAll('div[class*="_large_hg7y0_"]')]
  .map(e=>{const r=e.getBoundingClientRect();return {x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2),w:Math.round(r.width)};})
  .filter(o=>o.w>20&&o.y>0); c.sort((a,b)=>b.x-a.x); return c[0]||null; }"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = b.contexts[0].pages[0]

    # ① 看最近一个专家对话是否已有回复
    print("=== 打开最近的专家对话 ===")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(800)
    pg.get_by_text("新建任务", exact=True).first.click(timeout=8000)
    pg.wait_for_timeout(2200)
    try:
        pg.locator('div[class*="conversation-agent"]').first.click(timeout=6000)
        pg.wait_for_timeout(4000)
        txt = pg.evaluate("() => (document.body.innerText||'').slice(200, 900)")
        print(txt)
        pg.screenshot(path=HERE + "/expert_conv_check.png")
        print("shot: expert_conv_check.png")
    except Exception as e:
        print("打开失败:", str(e)[:90])

    # ② 搜索并精确召唤企鹅教师助手
    print("\n=== 搜索召唤 企鹅教师助手 ===")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(800)
    print("tab:", pg.evaluate(JS_TAB))
    pg.wait_for_timeout(3000)
    print("search:", pg.evaluate(JS_SEARCH, "企鹅教师助手"))
    pg.wait_for_timeout(2500)
    print("card:", pg.evaluate(JS_CARD, "企鹅教师助手"))
    pg.wait_for_timeout(2600)
    print("summon:", pg.evaluate(JS_SUMMON))
    pg.wait_for_timeout(4200)
    try:
        pg.locator('div[class*="_editable_"]').first.click(timeout=7000)
        pg.wait_for_timeout(500)
        pg.keyboard.press("Control+a"); pg.keyboard.press("Delete")
        pg.wait_for_timeout(400)
        pg.keyboard.type("你好", delay=30)
        pg.wait_for_timeout(900)
        s = pg.evaluate(JS_SEND)
        if s:
            pg.mouse.click(s["x"], s["y"])
        time.sleep(7)
        # 看有没有连接提示
        print("连接提示:", pg.evaluate("""() => {
          const b=[...document.querySelectorAll('button')].find(x=>(x.innerText||'').trim()==='连接');
          return b ? '有连接提示' : '无';
        }"""))
        pg.screenshot(path=HERE + "/teacher_summon.png")
        print("shot: teacher_summon.png")
    except Exception as e:
        print("发送失败:", str(e)[:90])

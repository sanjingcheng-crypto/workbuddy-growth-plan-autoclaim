# -*- coding: utf-8 -*-
"""
WorkBuddy CDP 自动完成「需客户端 UI」的成长任务
================================================

前提：WorkBuddy 以 `--remote-debugging-port=9222` 启动
      （用根目录的 start_workbuddy_debug.bat 一键完成）

原理
----
客户端是 Electron 应用，开启调试端口后，Playwright 可
`connect_over_cdp("http://127.0.0.1:9222")` 直接操作其 renderer DOM：
  操作目标 = app.asar/renderer/index.html（即 WorkBuddy 主界面）

已验证可完成的任务
------------------
- create_canvas（+300）：点「新建任务」→ 点场景 tab「设计创意」→
  在 contenteditable 输入 prompt → 点右下角发送按钮 → 服务端计数 ✅

关键 DOM 事实（2026-09-12 实测，WorkBuddy 5.2.6 / Electron 37）
-------------------------------------------------------------
- 输入框：`div[class*="_editable_"]`（contenteditable，尺寸约 724x70）
- 场景 tab：`[class*="wb-scene-tabs__pill"]`，文本 ∈ 日常办公 / 代码开发 / 设计创意
- 模板（quick actions）：`[class*="quick-actions__item"]`，文本 ∈ 文档处理 / 金融服务 / 数据分析及可视化
- 发送按钮：**不是 `<button>`**，是输入框右下方的 `div[class*="_icon_"]`（32x32，内含 SVG）
  → 最稳的定位方式是**坐标**：从输入框 box 推算右下角，或直接用实测坐标 (1158, 537)
- 任务列表计数在侧栏「任务 (N)」，发一次对话 N 会 +1

用法
----
  python cdp_autofarm.py --check                 # 只检查 CDP 是否可用 + 打印页面
  python cdp_autofarm.py --canvas                # 自动完成 create_canvas
  python cdp_autofarm.py --canvas --prompt "帮我设计一个移动端登录页"
  python cdp_autofarm.py --templates 4           # 依次用 N 个不同模板发起对话
  python cdp_autofarm.py --shot out.png          # 截图当前界面（排查用）
"""
import argparse
import os
import sys
import time

CDP = os.environ.get("WB_CDP", "http://127.0.0.1:9222")
EDITABLE = 'div[class*="_editable_"]'
SEND_XY_DEFAULT = (1158, 537)

JS_ED_TEXT = """() => {
  const e = document.querySelector('%s');
  return e ? (e.innerText || '') : null;
}""" % EDITABLE

JS_STATE = """() => {
  const ed = document.querySelector('%s');
  const r = ed ? ed.getBoundingClientRect() : null;
  const tabs = [...document.querySelectorAll('[class*=wb-scene-tabs__pill]')]
      .map(e => ({t: (e.innerText||'').trim(), active: /active/.test(e.className)}));
  const qa = [...document.querySelectorAll('[class*=quick-actions__item]')]
      .map(e => (e.innerText||'').trim()).filter(Boolean);
  const taskLabel = (document.body.innerText.match(/任务\\s*\\((\\d+)\\)/) || [])[1] || '?';
  return {edBox: r ? {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)} : null,
          edText: ed ? (ed.innerText||'').slice(0,60) : null,
          tabs: tabs, quickActions: qa, taskCount: taskLabel};
}""" % EDITABLE


def wait_cdp(seconds):
    """轮询等待 CDP 端口就绪（客户端重启后 UI 需要时间起来）。"""
    import urllib.request
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            urllib.request.urlopen(CDP + "/json/version", timeout=3).read()
            return True
        except Exception:
            time.sleep(2)
    return False


def connect(sync_playwright, wait=0):
    if wait > 0:
        print("等待 CDP 端口就绪（最多 %ss）..." % wait)
        if not wait_cdp(wait):
            print("! 等待超时：%s 未就绪" % CDP)
            sys.exit(2)
        print("CDP 已就绪")
        time.sleep(6)  # 再给 UI 一点渲染时间
    try:
        p = sync_playwright().start()
        b = p.chromium.connect_over_cdp(CDP)
        return p, b
    except Exception as e:
        print("! 连接 CDP 失败: %s" % e)
        print("  请先运行 start_workbuddy_debug.bat 启动带 --remote-debugging-port=9222 的客户端")
        sys.exit(2)


def page_of(b):
    for ctx in b.contexts:
        for pg in ctx.pages:
            if "WorkBuddy" in (pg.title() or "") or "index.html" in pg.url:
                return pg
    return b.contexts[0].pages[0]


JS_SEND_BTN = """() => {
  const c = [...document.querySelectorAll('div[class*="_large_hg7y0_"]')]
    .map(e => { const r = e.getBoundingClientRect();
                return {x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2),
                        w: Math.round(r.width)}; })
    .filter(o => o.w > 20 && o.y > 0);
  if (!c.length) return null;
  c.sort((a, b) => b.x - a.x);   // 最靠右的才是发送键（左侧 900px 那个是附件）
  return c[0];
}"""


def click_send(pg):
    """发送键不是 <button>；同类名元素有两个（附件在左、发送在右），必须取最右。"""
    info = pg.evaluate(JS_SEND_BTN)
    if info:
        pg.mouse.click(info["x"], info["y"])
        return (info["x"], info["y"])
    x, y = SEND_XY_DEFAULT
    pg.mouse.click(x, y)
    return (x, y)


def open_new_task(pg):
    pg.get_by_text("新建任务", exact=True).first.click(timeout=8000)
    pg.wait_for_timeout(2200)


def set_scene(pg, name):
    for t in pg.evaluate(JS_STATE)["tabs"]:
        if t["t"] == name and t["active"]:
            return True
    # 用 pill 选择器精确点击，避免 get_by_text 命中隐藏/祖先元素的歧义（脏态下常见）
    ok = pg.evaluate("""(name) => {
        const els = [...document.querySelectorAll('[class*=wb-scene-tabs__pill]')];
        const hit = els.find(e => (e.innerText||'').trim() === name);
        if (!hit) return false;
        hit.scrollIntoView(); hit.click(); return true;
    }""", name)
    if not ok:
        pg.get_by_text(name, exact=True).first.click(timeout=6000)  # 兜底
    pg.wait_for_timeout(2200)
    return True


def fill_prompt(pg, text):
    loc = pg.locator(EDITABLE).first
    loc.click(timeout=6000)
    pg.wait_for_timeout(400)
    pg.keyboard.type(text, delay=22)
    pg.wait_for_timeout(700)


def set_model(pg, name="Hy3"):
    """把 composer 的模型切到指定项。
    模型菜单（2026-09-12 实测）：Hy3(0.00x 限时免费) / Deepseek-V4.1(0.03x) /
    Hy4 preview(0.29x 夜间免费) / GLM-5.3-Flash(0.06x) / GLM-5.3(0.75x) / GLM-5.2(0.79x)。
    注意 Model_chat_GLM5.2 任务要求 GLM-5.2，其余任务用免费模型即可。"""
    JS_OPEN = """() => {
      if (document.querySelector('[role=menuitem],[role=option]')) return 'open';
      const e = [...document.querySelectorAll('button')].find(x => /GLM-|Flash|Hy\\d|Deepseek/.test(x.innerText||''));
      if (!e) return 'nf';
      e.click(); return 'opened';
    }"""
    JS_PICK = """(name) => {
      // 菜单里同名模型可能有多档（如 Hy3 0.00x / 0.05x）—— 优先选含 0.00 的行
      const leaves = [...document.querySelectorAll('*')].filter(e => e.childElementCount === 0);
      let hit = leaves.find(e => (e.innerText||'').trim().startsWith(name)
                                 && (e.parentElement.innerText||'').includes('0.00'))
             || leaves.find(e => (e.innerText||'').trim().startsWith(name));
      if (!hit) return 'nf';
      let row = hit;
      for (let i = 0; i < 6 && row; i++) {
        if (row.getAttribute && (row.getAttribute('role') === 'menuitem'
            || row.getAttribute('role') === 'option')) break;
        if (row.parentElement && /item|option|menu/i.test(row.parentElement.className||'')) row = row.parentElement;
        else break;
      }
      (row.getBoundingClientRect().width > 30 ? row : hit).click();
      return 'ok';
    }"""
    pg.evaluate(JS_OPEN)
    pg.wait_for_timeout(1500)
    r = pg.evaluate(JS_PICK, name)
    pg.wait_for_timeout(1200)
    cur = pg.evaluate("""() => {
      const e = [...document.querySelectorAll('button')].find(x => /GLM-|Hy\\d|Deepseek/.test(x.innerText||''));
      return e ? e.innerText.trim().split('\\n')[0] : '?';
    }""")
    print("  set_model(%s) -> %s | 当前模型: %s" % (name, r, cur))
    return cur


def auto_confirm(pg, prefer="连接"):
    """自动点确认/授权弹框。召唤专家后弹「是否连接 XX？」时用 prefer='连接'
    （Expert_lighthouse 需要）；不想授权时用 prefer='暂不'。
    返回: 'connected' / 'skipped' / 'no-dialog'。"""
    JS = """(prefer) => {
      const btns = [...document.querySelectorAll('button')];
      const pick = btns.find(x => (x.innerText||'').trim() === prefer);
      const other = btns.find(x => ['连接','暂不'].includes((x.innerText||'').trim()) && x !== pick);
      if (pick) { pick.click(); return 'clicked:' + prefer; }
      if (other) { other.click(); return 'clicked:' + other.innerText.trim(); }
      return 'no-dialog';
    }"""
    r = pg.evaluate(JS, prefer)
    pg.wait_for_timeout(1500)
    return r


def do_canvas(pg, prompt):
    open_new_task(pg)
    set_scene(pg, "设计创意")
    fill_prompt(pg, prompt)
    st = pg.evaluate(JS_STATE)
    print("  输入框: %r | 任务数: %s" % (st["edText"], st["taskCount"]))
    xy = click_send(pg)
    print("  已点击发送 @ %s" % (xy,))
    time.sleep(6)
    st2 = pg.evaluate(JS_STATE)
    print("  发送后任务数: %s" % st2["taskCount"])
    return st["taskCount"] != st2["taskCount"]


JS_PILLS = """() => [...document.querySelectorAll('[class*=quick-actions__item]')]
  .map(e => (e.innerText || '').trim()).filter(t => t && t !== '更多')"""
JS_TASK_N = "() => (document.body.innerText.match(/任务\\s*\\((\\d+)\\)/) || [])[1] || '?'"

TEMPLATE_POOL = ["文档处理", "金融服务", "数据分析及可视化", "财报分析全流程",
                 "MD转PDF文档", "竞品对比分析", "项目周报转Word"]


def do_templates(pg, n):
    """完成 template_5：每次「点模板 pill → 插入 chip」。

    ★ 关键（2026-09-12 实测）：只插 chip 不输入文本时，发送键点了也没反应
      （composer 被视为空）——必须再 keyboard.type 一段真实文本，发送才生效。
    """
    done = 0
    used = set()
    for _ in range(max(n * 3, 4)):
        if done >= n:
            break
        open_new_task(pg)
        set_scene(pg, "日常办公")
        avail = [t for t in pg.evaluate(JS_PILLS) if t not in used] or pg.evaluate(JS_PILLS)
        if not avail:
            print("  ! 无可用模板")
            break
        name = next((c for c in avail if c in TEMPLATE_POOL), avail[0])
        before = pg.evaluate(JS_TASK_N)
        try:
            pg.get_by_text(name, exact=True).first.click(timeout=6000)
            pg.wait_for_timeout(1800)
        except Exception as e:
            print("  [%s] 模板点击失败: %s" % (name, str(e)[:70]))
            used.add(name)
            continue
        try:
            pg.locator(EDITABLE).first.click(timeout=5000)
            pg.wait_for_timeout(400)
            pg.keyboard.press("End")
            pg.keyboard.type("请帮我处理一下", delay=22)
            pg.wait_for_timeout(800)
        except Exception as e:
            print("  [%s] 补文本失败: %s" % (name, str(e)[:70]))
        xy = click_send(pg)
        time.sleep(6)
        after = pg.evaluate(JS_TASK_N)
        ok = before != after
        print("  [%s] 发送@%s 任务数 %s → %s %s" % (name, xy, before, after, "✅" if ok else "✗"))
        used.add(name)
        if ok:
            done += 1
    return done


JS_EXPLORE = """() => {
  const dumpEl = e => ({tag: e.tagName,
      cls: (typeof e.className==='string'?e.className:'').slice(0,70),
      text: (e.innerText||'').replace(/\\n+/g,' | ').slice(0,120),
      html: (e.outerHTML||'').slice(0,300)});
  const ed = document.querySelector('[class*="_editable_"]');
  const pops = [...document.querySelectorAll('[role=dialog],[role=menu],[role=listbox],[class*=modal],[class*=dropdown],[class*=popover],[class*=picker]')]
      .filter(e => { const r = e.getBoundingClientRect(); return r.width>50 && r.height>30; })
      .map(dumpEl);
  return {
    sceneTabs: [...document.querySelectorAll('[class*=wb-scene-tabs__pill]')]
        .map(e => ({t:(e.innerText||'').trim(), active:/active/.test(e.className)})),
    quickActions: [...document.querySelectorAll('[class*=quick-actions__item]')].map(dumpEl),
    popups: pops,
    editable: ed ? {text:(ed.innerText||'').slice(0,80), children: ed.children.length,
                    html: ed.outerHTML.slice(0,500)} : null,
    taskCount: (document.body.innerText.match(/任务\\s*\\((\\d+)\\)/) || [])[1] || '?',
  };
}"""


def do_explore(pg, outfile):
    """深度探查：为 template_5 / expert_5 采集 DOM 情报，落盘 JSON 供离线分析。"""
    import json
    report = {}
    open_new_task(pg)
    report["before_click"] = pg.evaluate(JS_EXPLORE)
    for name in ["文档处理", "金融服务", "数据分析及可视化", "更多"]:
        try:
            pg.get_by_text(name, exact=True).first.click(timeout=5000)
            pg.wait_for_timeout(2200)
            report["after_click_" + name] = pg.evaluate(JS_EXPLORE)
        except Exception as e:
            report["after_click_" + name] = {"error": str(e)[:120]}
        try:
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(800)
        except Exception:
            pass
    try:
        pg.get_by_text("专家·技能·连接器", exact=True).first.click(timeout=5000)
        pg.wait_for_timeout(2500)
        report["experts_panel"] = pg.evaluate(JS_EXPLORE)
    except Exception as e:
        report["experts_panel"] = {"error": str(e)[:120]}
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("探查完成 → %s" % outfile)
    print("  sceneTabs:", report["before_click"]["sceneTabs"])
    print("  quickActions:", [q["text"][:20] for q in report["before_click"]["quickActions"]])
    for k, v in report.items():
        if k.startswith("after_click_"):
            print("  %s → popups=%d editable=%r" % (
                k, len(v.get("popups", [])), (v.get("editable") or {}).get("text", "")[:30]))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--canvas", action="store_true")
    ap.add_argument("--explore")
    ap.add_argument("--prompt", default="帮我设计一个移动端登录页")
    ap.add_argument("--templates", type=int, default=0)
    ap.add_argument("--model", default=None,
                    help="发送前把模型切到该项（如 Hy3=0.00x 免费 / Deepseek-V4.1=0.03x）")
    ap.add_argument("--confirm", default=None, choices=["连接", "暂不"],
                    help="自动确认授权弹框（召唤专家后用「连接」可触发 Expert_lighthouse）")
    ap.add_argument("--shot")
    ap.add_argument("--wait", type=int, default=0, help="先轮询等待 CDP 端口就绪（秒）")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright
    p, b = connect(sync_playwright, wait=args.wait)
    try:
        pg = page_of(b)
        print("页面: %s | %s" % (pg.title(), pg.url.split("/")[-1]))
        if args.check:
            st = pg.evaluate(JS_STATE)
            print("输入框:", st["edBox"])
            print("场景 tab:", [(t["t"], t["active"]) for t in st["tabs"]])
            print("模板:", st["quickActions"])
            print("任务数:", st["taskCount"])
        if args.explore:
            print("== 深度探查（template_5 / expert_5 情报采集）==")
            do_explore(pg, args.explore)
        if args.model:
            print("== 切换模型 ==")
            set_model(pg, args.model)
        if args.confirm:
            print("== 自动确认授权框 ==")
            print("  结果:", auto_confirm(pg, args.confirm))
        if args.canvas:
            print("== 自动完成 create_canvas ==")
            print("  结果:", do_canvas(pg, args.prompt))
        if args.templates:
            print("== 自动使用 %d 个模板 ==" % args.templates)
            print("  完成 %d 个" % do_templates(pg, args.templates))
        if args.shot:
            pg.screenshot(path=args.shot)
            print("截图:", args.shot)
    finally:
        p.stop()


if __name__ == "__main__":
    main()

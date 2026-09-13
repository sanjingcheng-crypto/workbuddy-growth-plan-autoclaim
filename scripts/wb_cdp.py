# -*- coding: utf-8 -*-
"""
WorkBuddy CDP 控制器
====================
前提：WorkBuddy 以 `--remote-debugging-port=9222` 启动
      （用 start_workbuddy_debug.bat 一键完成）

能力：
  1) 列出客户端内所有页面（webview），拿到标题/URL —— 判断是主界面还是别的东西
  2) **录制全部网络请求**（URL / method / postData / 响应片段）→ 挖出成长任务的业务 API
  3) 对任意页面执行 JS / 点击元素 —— 可直接操作客户端 UI

用法：
  python wb_cdp.py --list                       # 列出页面
  python wb_cdp.py --record 60                  # 录制 60 秒网络请求，存 wb_net.json
  python wb_cdp.py --record 60 --only canvas    # 只记录 URL 含 canvas 的
  python wb_cdp.py --js "<表达式>"               # 在所有页面执行 JS 并打印结果
  python wb_cdp.py --click "文字=设计创意"        # 按文字点击（穿透 shadow DOM）
  python wb_cdp.py --dump-body                   # 列表模式下同时导出页面正文前 500 字

说明：
  - 走 Playwright 的 connect_over_cdp，无需自签证书、不改系统代理
  - 录制时请**手动在客户端做一个动作**（比如新建画布），请求就会被捕获
"""
import argparse
import json
import os
import sys
import time

CDP = os.environ.get("WB_CDP", "http://127.0.0.1:9222")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wb_net.json")

INTERESTING = ("tencent.com", "codebuddy", "workbuddy", "copilot", "cloud.tencent",
               "api", "growth", "canvas", "template", "expert", "skill", "automation")


def connect():
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    try:
        browser = p.chromium.connect_over_cdp(CDP)
    except Exception as e:
        p.stop()
        print("! 连接 CDP 失败：%s" % e)
        print("  请先用 start_workbuddy_debug.bat 启动 WorkBuddy（带 --remote-debugging-port=9222）")
        sys.exit(2)
    return p, browser


def all_pages(browser):
    pages = []
    for ctx in browser.contexts:
        pages.extend(ctx.pages)
    return pages


def cmd_list(browser, args):
    pages = all_pages(browser)
    print("共 %d 个页面：" % len(pages))
    for i, pg in enumerate(pages):
        try:
            title = pg.title()
        except Exception:
            title = "?"
        print("\n[%d] title=%r\n    url=%s" % (i, title, pg.url))
        if args.dump_body:
            try:
                txt = pg.evaluate("() => (document.body ? document.body.innerText : '').slice(0,500)")
                print("    body: %s" % (txt or "").replace("\n", " ")[:500])
            except Exception as e:
                print("    body err: %s" % e)


def cmd_js(browser, args):
    for pg in all_pages(browser):
        try:
            r = pg.evaluate(args.js)
            print("[%s] %s" % (pg.url[:60], json.dumps(r, ensure_ascii=False)[:600]))
        except Exception as e:
            print("[%s] ERR %s" % (pg.url[:60], e))


def cmd_click(browser, args):
    spec = args.click
    mode, _, val = spec.partition("=")
    for pg in all_pages(browser):
        try:
            if mode in ("文字", "text"):
                loc = pg.get_by_text(val, exact=False)
            elif mode in ("label", "aria"):
                loc = pg.locator("[aria-label*=%r]" % val)
            else:
                loc = pg.locator(val)
            n = loc.count()
            if n:
                loc.first.click(timeout=5000)
                print("[%s] 已点击 %s（匹配 %d 个）" % (pg.url[:50], spec, n))
        except Exception as e:
            print("[%s] 点击失败: %s" % (pg.url[:50], str(e)[:120]))


def cmd_record(browser, args):
    only = args.only
    recs = []
    t0 = time.time()
    pages = all_pages(browser)

    def attach(pg):
        def on_req(req):
            try:
                u = req.url
                if only and only not in u:
                    return
                if not only and not any(k in u for k in INTERESTING):
                    return
                body = None
                try:
                    if req.method in ("POST", "PUT", "PATCH"):
                        body = req.post_data
                except Exception:
                    pass
                recs.append({
                    "t": round(time.time() - t0, 2),
                    "method": req.method,
                    "url": u,
                    "postData": body,
                })
            except Exception:
                pass

        def on_resp(resp):
            try:
                u = resp.url
                if only and only not in u:
                    return
                if not only and not any(k in u for k in INTERESTING):
                    return
                for r in reversed(recs):
                    if r.get("url") == u and "status" not in r:
                        r["status"] = resp.status
                        try:
                            r["respHead"] = resp.text()[:300]
                        except Exception:
                            pass
                        break
            except Exception:
                pass

        pg.on("request", on_req)
        pg.on("response", on_resp)

    for pg in pages:
        attach(pg)
    try:
        browser.contexts[0].on("page", lambda pg: attach(pg))
    except Exception:
        pass

    print("开始录制 %ss —— 现在请在客户端里做一次操作（例如新建画布）..." % args.record)
    time.sleep(args.record)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(recs, f, ensure_ascii=False, indent=1)
    print("\n捕获 %d 条请求 → %s" % (len(recs), OUT))
    for r in recs[:40]:
        pd = (r.get("postData") or "")[:130]
        print("  %-6s %s\n         %s" % (r["method"], r["url"][:150], pd))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dump-body", action="store_true")
    ap.add_argument("--record", type=int, metavar="SECONDS")
    ap.add_argument("--only")
    ap.add_argument("--js")
    ap.add_argument("--click")
    args = ap.parse_args()

    p, browser = connect()
    try:
        if args.record:
            cmd_record(browser, args)
        elif args.js:
            cmd_js(browser, args)
        elif args.click:
            cmd_click(browser, args)
        else:
            cmd_list(browser, args)
    finally:
        p.stop()


if __name__ == "__main__":
    main()

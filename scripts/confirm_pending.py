# -*- coding: utf-8 -*-
"""自动处理 WorkBuddy 左侧任务栏里标有"待确认"的会话：
点开会话 → 在"你想让我怎么处理"弹窗里选"总结归纳" → 清除待确认。
（针对 do_templates 产生的"请帮我处理一下这份材料"悬停会话）"""
import sys, json, time
sys.path.insert(0, r"C:\Users\onroud\.workbuddy\skills\workbuddy-growth-plan-autoclaim\scripts")
from wb_cdp import connect, all_pages

JS_LIST_PENDING = """() => {
  return [...document.querySelectorAll('._header_d0xfh_28')]
    .filter(h => {
      const t = (h.innerText || '').replace(/\\s+/g, ' ').trim();
      return t.includes('请帮我处理一下这份材料') &&
             [...h.querySelectorAll('._tag_d0xfh_354')].some(s => (s.innerText||'').trim() === '待确认');
    })
    .map(h => (h.innerText || '').replace(/\\s+/g, ' ').trim());
}"""

JS_CLICK_FIRST_PENDING = """() => {
  const h = [...document.querySelectorAll('._header_d0xfh_28')]
    .find(h => {
      const t = (h.innerText || '').replace(/\\s+/g, ' ').trim();
      return t.includes('请帮我处理一下这份材料') &&
             [...h.querySelectorAll('._tag_d0xfh_354')].some(s => (s.innerText||'').trim() === '待确认');
    });
  if (!h) return 'no-pending';
  h.click();
  return 'clicked:' + (h.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 60);
}"""

JS_HAS_OPTION = """() => {
  return [...document.querySelectorAll('._optionText_105i4_270')]
    .map(s => (s.innerText || '').trim()).filter(Boolean);
}"""

JS_CLICK_OPTION = """(txt) => {
  const s = [...document.querySelectorAll('._optionText_105i4_270')]
    .find(e => (e.innerText || '').trim() === txt);
  if (s) { s.click(); return 'clicked-option:' + txt; }
  return 'option-not-found:' + txt;
}"""

JS_CLICK_NEXT_ARROW = """() => {
  // 弹窗右箭头，翻到 2/2
  const arrows = [...document.querySelectorAll('svg, button, div')].filter(e => {
    const aria = e.getAttribute('aria-label') || '';
    return aria.includes('下一页') || aria.includes('next') || aria.includes('Next');
  });
  if (arrows.length) { arrows[0].click(); return 'clicked-next-arrow'; }
  return 'no-next-arrow';
}"""


def main():
    p, browser = connect()
    try:
        pg = next((page for page in all_pages(browser) if "index.html" in page.url), None)
        if not pg:
            print("未找到 WorkBuddy 主页面")
            return
        print("页面:", pg.title())
        for i in range(15):
            pending = pg.evaluate(JS_LIST_PENDING)
            print("\n[%d] 当前待确认会话数: %d" % (i, len(pending)))
            if not pending:
                print("没有更多待确认会话，结束。")
                break
            print("  处理:", pending[0][:70])
            r = pg.evaluate(JS_CLICK_FIRST_PENDING)
            print("  点击结果:", r)
            pg.wait_for_timeout(1500)
            opts = pg.evaluate(JS_HAS_OPTION)
            print("  可见选项:", opts)
            if '总结归纳' in opts:
                print("  ", pg.evaluate(JS_CLICK_OPTION, '总结归纳'))
            elif opts:
                print("  ", pg.evaluate(JS_CLICK_OPTION, opts[0]))
            else:
                # 可能还在第一页，尝试翻页
                print("  翻页:", pg.evaluate(JS_CLICK_NEXT_ARROW))
                pg.wait_for_timeout(1000)
                opts2 = pg.evaluate(JS_HAS_OPTION)
                if opts2:
                    print("  ", pg.evaluate(JS_CLICK_OPTION, opts2[0]))
                else:
                    print("  ! 仍无选项，跳过本轮")
                    continue
            pg.wait_for_timeout(2500)
        else:
            print("达到最大循环次数，退出。")
    finally:
        p.stop()


if __name__ == "__main__":
    main()

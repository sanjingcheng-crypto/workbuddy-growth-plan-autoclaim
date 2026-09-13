# -*- coding: utf-8 -*-
"""
black_cat 黑猫彩蛋 · 夜间自动推进（ACP）
========================================

规则：连续 **3 天**在 **23:00–8:00** 用 **GLM-5.2** 发起对话 → 解锁黑猫彩蛋（0 积分，纯彩蛋）。

实测（2026-09-13）：用 ACP 新建会话 + set_model glm-5.2 + prompt 一条消息，
服务端确实把该账号的 black_cat 从 0/3 推进到 1/3。说明 ACP 的 GLM-5.2 对话计入彩蛋判定。

本脚本带时间窗口守卫：非 23:00–8:00 自动跳过（加 --force 可强制）。
设计成可由每小时定时任务调用 —— 它在窗口内每晚自然触发一次，连续 3 晚即完成。

依赖：acp_autofarm.py（同目录，复用其 ACP 握手 / JSON-RPC）。

用法：
  python black_cat.py            # 仅在 23:00–8:00 窗口内发一条 GLM-5.2 夜间对话
  python black_cat.py --force    # 忽略时间窗口强制发（调试用）
"""
import datetime
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acp_autofarm as A


def in_night_window():
    h = datetime.datetime.now().hour
    return h >= 23 or h < 8


def main():
    force = "--force" in sys.argv
    if not force and not in_night_window():
        print("[black_cat] 当前不在 23:00-8:00 夜间窗口，跳过（加 --force 强制）。")
        return 0

    port, got = A.pick_port(verbose=True)
    if not got:
        print("[black_cat] ! 无可用 ACP 端口（客户端是否在运行？）")
        return 1
    conn, cid, tok = got

    A.rpc(conn, cid, tok, "initialize", {"protocolVersion": 1, "clientCapabilities": {}}, 1, 400, 8)
    rid = 100
    cwd = os.environ.get("TEMP", ".")
    sid, s, b = A.new_session(conn, cid, tok, cwd, rid)
    rid += 2
    if not sid:
        print("[black_cat] ! 建会话失败：%s" % (b[:160]))
        return 1
    s2, _ = A.say(conn, cid, tok, sid, "你好，请用一句话描述夜晚的宁静。", rid, model="glm-5.2")
    rid += 2
    print("[black_cat] GLM-5.2 夜间对话已发送 (new=%s prompt=%s)。需连续 3 晚完成。" % (s, s2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

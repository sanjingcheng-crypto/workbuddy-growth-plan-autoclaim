# -*- coding: utf-8 -*-
"""
WorkBuddy 成长计划 · ACP 零人工自动完成任务
==========================================

原理
----
WorkBuddy 桌面客户端为每个会话启动 sidecar 进程，暴露**本地 ACP 端点**：
    http://127.0.0.1:<port>/api/v1/acp

握手**无需认证** —— GET 时服务端直接下发 `acp-connection-id` 与 `acp-session-token`：
    1) GET  /api/v1/acp   (Accept: text/event-stream) → 拿 cid + token
    2) POST /api/v1/acp   (带 acp-connection-id / acp-session-token 头) → 发 JSON-RPC

已实测可用的 JSON-RPC 方法：
    initialize / session/new / session/set_model / session/set_mode /
    session/set_config_option / session/prompt / session/list / session/delete / session/cancel

已验证的任务触发效果（2026-09-12 实测）
--------------------------------------
- session/new + session/prompt
      → 计入「新建任务并发起对话」类任务
      → 实测：Model_chat_GLM5.2 由 0/1 变为可领，成功领取 **+100 积分 / +5 能量**
- 配合 session/set_model({modelId:"glm-5.2"})
      → 满足 Model_chat_GLM5.2 的「使用 GLM-5.2 模型」要求

局限与安全
----------
- **只对「客户端当前登录的账号」生效**：sidecar 属于当前登录态，奖励记在该账号头上。
- 端口是**会话级、动态**的：从 main.log 提取 `acpEndpoint` 并逐个探活。
- 默认**跳过用户正在使用的会话端口**（避免把测试消息插进他正在看的对话）。
- 本脚本只发「你好」这类无副作用短消息；不会让 agent 执行文件操作。

用法
----
  python acp_autofarm.py            # 只读：列出 ACP 端口、当前登录账号、可自动完成的任务
  python acp_autofarm.py --run      # 执行：对当前登录账号补做 Model_chat_GLM5.2 / chat_5
  python acp_autofarm.py --probe    # 只探测 ACP 端口可用性
"""
import http.client
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LOGFILE = os.path.join(os.environ.get("LOCALAPPDATA", ""), "WorkBuddy", "logs", "main.log")
TIMEOUT = 12


def log_path():
    return LOGFILE if os.path.exists(LOGFILE) else None


def read_log():
    p = log_path()
    if not p:
        return ""
    try:
        return open(p, encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


# ------------------------------------------------------------------ 账号
def current_login_uid():
    """客户端当前登录的账号 uid。
    注意：日志的 message 是 JSON 数组，内部的引号被转义成 \\"，
    所以不能用普通的 "currentUserId":"..." 去匹配。"""
    txt = read_log()
    uids = re.findall(
        r"currentUserId[^0-9a-f]{0,20}"
        r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", txt)
    return uids[-1] if uids else None


# ------------------------------------------------------------------ ACP 端口
def discover_ports():
    """从日志提取候选端口（最近的排前面）。"""
    eps = re.findall(r"acpEndpoint=http://127\.0\.0\.1:(\d+)/api/v1/acp", read_log())
    seen, out = set(), []
    for p in reversed(eps):  # 越靠后越新
        p = int(p)
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def discover_cli_host_ports():
    """CLI host 会话端口 —— 这不是用户正在看的对话，向它发消息不会打扰用户。
    日志样例：
      [Sidecar] Creating session __workbuddy_cli_host__-0-29b357f9 — C:\\...\\WorkBuddy.exe (port=59786)"""
    txt = read_log()
    ps = re.findall(r"__workbuddy_cli_host__[^(]{0,300}?\(port=(\d+)\)", txt)
    seen, out = set(), []
    for p in reversed(ps):
        p = int(p)
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def open_acp(port, wait=5):
    """建 SSE 连接拿 cid/token。返回 (conn, cid, token) 或 None。"""
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=wait)
        c.request("GET", "/api/v1/acp", headers={"Accept": "text/event-stream"})
        r = c.getresponse()
        cid = r.getheader("acp-connection-id")
        tok = r.getheader("acp-session-token")
        if r.status == 200 and cid:
            return c, cid, tok
        c.close()
    except Exception:
        pass
    return None


def pick_port(skip_ports=None, verbose=True, safe=True):
    """挑一个可用的 ACP 端口。
    safe=True（默认）时**只用 CLI host 会话端口** —— 向它发消息不会进用户的对话。
    普通会话端口（可能正是用户正在看的对话）需要 safe=False 才使用。"""
    skip = set(skip_ports or [])
    hosts = [p for p in discover_cli_host_ports() if p not in skip]
    order = list(hosts)
    if not safe:
        order += [p for p in discover_ports() if p not in skip and p not in hosts]
    else:
        # safe 模式优先 cli host（不打扰用户）；若 cli host 端口全部失效（日志格式变化/
        # 旧会话端口过期，discover_cli_host_ports 返回空），回退到 acpEndpoint 端口。
        # session/new 会新建独立会话，消息不会插进用户正在看的对话，安全。
        if not order:
            order += [p for p in discover_ports() if p not in skip]
    for p in order:
        got = open_acp(p)
        if got:
            if verbose:
                if p in hosts:
                    tag = "（CLI host 会话，不打扰用户）"
                elif safe and not hosts:
                    tag = "（cli-host 端口失效，回退 acpEndpoint 端口；新建会话不打扰用户）"
                else:
                    tag = "（⚠️ 普通会话，可能=用户当前对话）"
                print("[acp] 使用端口 %s%s" % (p, tag))
            return p, got
    return None, None


# ------------------------------------------------------------------ JSON-RPC
def rpc(conn, cid, tok, method, params, rid, budget=6000, wait=TIMEOUT):
    body = json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
    c = http.client.HTTPConnection(conn.host, conn.port, timeout=wait)
    c.request("POST", "/api/v1/acp", body=body, headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "acp-connection-id": cid,
        "acp-session-token": tok,
    })
    try:
        r = c.getresponse()
    except Exception as e:
        return -1, "err %r" % e
    buf = b""
    try:
        while len(buf) < budget:
            d = r.read1(16384)
            if not d:
                break
            buf += d
    except Exception:
        pass
    return r.status, buf.decode("utf-8", "replace")


def new_session(conn, cid, tok, cwd, rid):
    s, b = rpc(conn, cid, tok, "session/new", {"cwd": cwd, "mcpServers": []}, rid)
    # 优先取 result.sessionId（真正的响应），避免误取 session/update 通知里的会话 id
    m = re.search(r'"result":\{[^{}]{0,200}?"sessionId":"([0-9a-f-]{36})"', b)
    if m:
        return m.group(1), s, b
    ids = re.findall(r'"sessionId":"([0-9a-f-]{36})"', b)
    return (ids[-1] if ids else None), s, b


def say(conn, cid, tok, sid, text, rid, model=None):
    """（可选设模型）发一条消息。"""
    if model:
        rpc(conn, cid, tok, "session/set_model", {"sessionId": sid, "modelId": model},
            rid, budget=1500, wait=10)
    return rpc(conn, cid, tok, "session/prompt", {"sessionId": sid,
                                                  "prompt": [{"type": "text", "text": text}]},
               rid + 1, budget=2500, wait=25)


# ------------------------------------------------------------------ 任务对接
def growth():
    """取「客户端当前登录账号」的凭据。
    ACP 的奖励只记在当前登录账号头上 —— 绝不能拿别的账号去查/领。"""
    import harvest
    accs = harvest.load_accounts()
    cur = current_login_uid()
    if cur:
        for a in accs:
            if a["key"] == cur:
                return harvest, a
    return harvest, None


def task_progress(harvest, acc, code):
    st, tj = harvest.growth_get(acc, "/v2/activity/growth/tasks")
    if st != 200:
        return None
    for t in (tj.get("data") or {}).get("tasks") or []:
        if t.get("task_code") == code:
            pr = t.get("progress") or {}
            return {"status": t.get("accept_status"),
                    "cur": pr.get("current"), "tgt": pr.get("target")}
    return None


def main():
    argv = sys.argv[1:]
    do_run = "--run" in argv
    only_probe = "--probe" in argv

    ports = discover_ports()
    print("=== ACP 自动完成任务 ===")
    print("候选端口(新→旧): %s" % ports[:10])

    # 找到可用端口
    port, got = pick_port()
    if not got:
        print("! 没有可用的 ACP 端口（客户端是否在运行？）")
        return 1
    conn, cid, tok = got

    # 用户当前会话端口（用日志里最新创建的那个反推）：保守做法是最后一个候选端口
    print("当前登录 uid: %s" % (current_login_uid() or "?"))

    if only_probe:
        s, b = rpc(conn, cid, tok, "initialize", {"protocolVersion": 1, "clientCapabilities": {}}, 1, 400, 8)
        print("initialize -> %s" % s)
        return 0

    harvest, acc = growth()
    if not acc:
        print("! 无法确定客户端当前登录账号（日志里没有 currentUserId，或该账号不在切换器存档里）")
        print("  ACP 只对当前登录账号生效，为避免操作错账号，已中止。")
        return 1
    print("目标账号: %s (%s)" % (acc.get("name") or "?", acc["key"][:8]))

    plan = []
    mp = task_progress(harvest, acc, "Model_chat_GLM5.2")
    print("Model_chat_GLM5.2: %s" % mp)
    if mp and mp["status"] != "claimed" and (mp["cur"] or 0) < (mp["tgt"] or 1):
        plan.append("Model_chat_GLM5.2")

    cp = task_progress(harvest, acc, "chat_5")
    print("chat_5: %s" % cp)
    if cp and cp["status"] != "claimed" and (cp["cur"] or 0) < (cp["tgt"] or 5):
        plan.append("chat_5")

    print("可自动完成: %s" % (plan or "（无）"))
    if not do_run or not plan:
        print("\n（只读模式。加 --run 执行）")
        return 0

    rpc(conn, cid, tok, "initialize", {"protocolVersion": 1, "clientCapabilities": {}}, 1, 400, 8)
    rid = 100
    cwd = os.environ.get("TEMP", ".") 

    if "Model_chat_GLM5.2" in plan:
        sid, s, b = new_session(conn, cid, tok, cwd, rid); rid += 2
        if sid:
            s2, _ = say(conn, cid, tok, sid, "你好", rid, model="glm-5.2"); rid += 2
            print("  [GLM-5.2] session=%s new=%s prompt=%s" % (sid[:8], s, s2))

    if "chat_5" in plan:
        need = max(0, (cp["tgt"] or 5) - (cp["cur"] or 0))
        print("  chat_5 还差 %d 条" % need)
        for i in range(need):
            sid, s, b = new_session(conn, cid, tok, cwd, rid); rid += 2
            if sid:
                s2, _ = say(conn, cid, tok, sid, "你好", rid); rid += 2
                print("    [%d/%d] session=%s prompt=%s" % (i + 1, need, sid[:8], s2))
            time.sleep(0.8)

    print("\n✅ ACP 侧完成。稍等几秒后可跑 harvest.py 领取奖励。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

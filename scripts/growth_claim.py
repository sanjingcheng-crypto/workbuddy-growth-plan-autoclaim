#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WorkBuddy 成长计划 · 自动领奖（无头）
复用同目录 claim_api 的鉴权，扫描成长计划任务，
对"已完成且未领取"的任务自动领奖。

契约要点（已逆向验证）：
  baseURL = https://copilot.tencent.com
  必带请求头 X-Client-Platform: web（缺失 -> 404 page not found）
  其余头: Authorization: Bearer <JWT>, X-User-Id: <sub>, X-Domain: copilot.tencent.com
  GET  /v2/activity/growth/tasks            -> data.tasks[]
  POST /v2/activity/growth/tasks/{code}/claim -> data.{credit,energy,already_claimed}
"""
import os
import sys
import json
import urllib.request
import urllib.error

# 复用 claim_api 的鉴权：优先本目录（自包含），fallback 标准 user-skills 位置
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if "claim_api" not in sys.modules:
    try:
        import claim_api as C  # noqa: E402
    except ImportError:
        sys.path.insert(0, os.path.expanduser(r"~/.workbuddy/skills/workbuddy-growth-plan-autoclaim/scripts"))
        import claim_api as C  # noqa: E402

BASE = "https://copilot.tencent.com"
GROWTH = "/v2/activity/growth"


def _cred():
    c = C.candidates()[0]
    return c["token"], c["uid"]


def _hdr():
    tok, uid = _cred()
    return {
        "Authorization": f"Bearer {tok}",
        "X-User-Id": uid,
        "X-Domain": "copilot.tencent.com",
        "X-Client-Platform": "web",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _op():
    # 绕过环境代理（ProxyHandler({}) 直连，与 claim_api 一致）
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get(path):
    r = _op().open(urllib.request.Request(BASE + path, headers=_hdr()), timeout=20)
    return json.loads(r.read().decode("utf-8", "replace"))


def post(path, body=None):
    data = json.dumps(body if body is not None else {}).encode()
    req = urllib.request.Request(BASE + path, data=data, headers=_hdr(), method="POST")
    try:
        r = _op().open(req, timeout=20)
        return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", "replace"))
        except Exception:
            return e.code, {"code": e.code, "msg": "http_error"}


def is_done(t):
    prog = t.get("progress")
    if not prog:
        return False
    target = prog.get("target", 0)
    return target > 0 and prog.get("current", 0) >= target


def claim_completed():
    tj = get(GROWTH + "/tasks")
    tasks = (tj.get("data") or {}).get("tasks", [])
    out = []
    for t in tasks:
        code = t.get("task_code")
        if not is_done(t):
            continue
        if t.get("accept_status") == "claimed":
            continue
        st, obj = post(f"{GROWTH}/tasks/{code}/claim", {})
        out.append((code, st, obj))
    return tasks, out


def main():
    tasks, results = claim_completed()
    total_credit = 0
    total_energy = 0
    if not results:
        print("[growth] 当前没有'已完成且未领取'的任务，无需领奖。")
    for code, st, obj in results:
        d = (obj or {}).get("data", {}) or {}
        cred = d.get("credit", 0) or 0
        eng = d.get("energy", 0) or 0
        total_credit += cred
        total_energy += eng
        print(f"[growth] CLAIM {code}: HTTP {st} code={obj.get('code')} "
              f"credit=+{cred} energy=+{eng} already_claimed={d.get('already_claimed')}")
    # 概览
    done = [t["task_code"] for t in tasks if is_done(t)]
    unclaimed_done = [t["task_code"] for t in tasks
                      if is_done(t) and t.get("accept_status") != "claimed"]
    print(f"[growth] 已完成任务({len(done)}): {done}")
    print(f"[growth] 其中待领: {unclaimed_done}")
    print(f"[growth] 本次共领: credit=+{total_credit} energy=+{total_energy}")
    try:
        pj = get(GROWTH + "/profile")
        print("[growth] profile:", json.dumps(pj.get("data", {}), ensure_ascii=False))
    except Exception as e:
        print("[growth] profile 读取失败:", e)


if __name__ == "__main__":
    main()

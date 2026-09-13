# -*- coding: utf-8 -*-
"""
WorkBuddy 积分「多账号」无人值守收割脚本 v2
==========================================
修复 v1 的核心缺陷：v1 写死用 candidates()[0]（第一个账号），
而用户会频繁切换账号 —— 导致"聊天做的任务"和"领奖的账号"对不上，领不到。
v2 改为：**以账号为单位遍历**，每个账号独立签到 + 独立收割成长奖励。

凭据来源（按优先级，自动去重）：
  1) WorkBuddy账号切换器存档  %APPDATA%\\WorkBuddyAccountSwitcher\\accounts\\account_*.json
     —— 权威来源：含 uid / 昵称 / 手机号 / accessToken / refreshToken / domain
  2) WorkBuddy 登录态文件（当前登录的那个账号，可能不在切换器里）
  3) 主线程日志兜底

每个账号做的事：
  a) 每日签到   POST {base}{prefix}daily-checkin      （幂等，已领返回 code=10001）
  b) 成长收割   GET  /v2/activity/growth/tasks        （必须带 X-Client-Platform: web）
                POST /v2/activity/growth/tasks/{code}/claim
  c) 派猫旅行   GET  /v2/activity/growth/buddy/travel/status
                POST /v2/activity/growth/buddy/travel/depart {"location_id":1}
                POST /v2/activity/growth/buddy/travel/claim  {}
                （纯白赚：派出去 1~4 小时，回来领 5~10 积分，零成本）

用法：
  python harvest.py                # 全部账号：签到 + 接任务 + 收割 + 派猫/收猫
  python harvest.py --checkin      # 只签到
  python harvest.py --growth       # 只收割成长奖励
  python harvest.py --travel       # 只派猫/收猫
  python harvest.py --list         # 只列账号与任务进度，不领取
  python harvest.py --only 8362    # 只处理 uid/昵称 含该串的账号

环境变量：
  WB_SWITCHER_DIR   覆盖切换器 archive 目录
"""
import os, sys, re, json, time, base64, datetime, urllib.request, urllib.error

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# claim_api 依赖：优先本 skill 目录（自包含，换电脑可用），fallback 旧路径
AUTOCLAIM_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if not os.path.exists(os.path.join(AUTOCLAIM_SCRIPTS, "claim_api.py")):
    # 兜底：同 skill 目录（用户名无关，用 expanduser）
    AUTOCLAIM_SCRIPTS = os.path.join(
        os.path.expanduser("~"), ".workbuddy", "skills",
        "workbuddy-growth-plan-autoclaim", "scripts")
DEFAULT_BASES = ["https://copilot.tencent.com", "https://www.codebuddy.cn"]
PATH_PREFIXES = ["/billing/meter/", "/v2/billing/meter/"]
TIMEOUT = 20
CODE_OK, CODE_ALREADY = 0, 10001
AUTH_BAD = (401, 403, 10085)

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 绕过本地代理


def now():
    return int(time.time())


def _b64url_json(seg):
    pad = "=" * (-len(seg) % 4)
    return json.loads(base64.urlsafe_b64decode(seg + pad))


def jwt_payload(tok):
    try:
        return _b64url_json(tok.split(".")[1])
    except Exception:
        return {}


def _mask(s):
    """脱敏：昵称/手机号只保留可辨识的最小片段。"""
    if not s:
        return "?"
    s = str(s)
    if s.isdigit() and len(s) >= 7:
        return s[:3] + "*" * (len(s) - 7) + s[-4:]
    if len(s) <= 2:
        return s[0] + "*"
    return s[:1] + "*" * (len(s) - 2) + s[-1:]


# ---------------------------------------------------------------- 账号收集
def switcher_dir():
    env = os.environ.get("WB_SWITCHER_DIR")
    if env:
        return env
    appdata = os.environ.get("APPDATA") or ""
    return os.path.join(appdata, "WorkBuddyAccountSwitcher", "accounts") if appdata else ""


def load_accounts():
    """返回 [{key, name, phone, uid, token, refresh, domain, exp, src}]，按 uid 去重。"""
    out, seen = [], set()

    def add(uid, name, phone, token, refresh, domain, src, extra=None):
        if not token or not token.startswith("eyJ"):
            return
        uid = uid or jwt_payload(token).get("sub") or ""
        if not uid or uid in seen:
            return
        exp = jwt_payload(token).get("exp")
        if exp and exp - now() < 3600:
            return  # 剩不到 1 小时视为不可用（除非后续补 refresh）
        seen.add(uid)
        acc = {"key": uid, "name": name or "", "phone": phone or "",
               "uid": uid, "token": token, "refresh": refresh or "",
               "domain": domain or "", "exp": exp, "src": src}
        if extra:
            acc.update(extra)
        out.append(acc)

    # 1) 切换器存档（权威）
    d = switcher_dir()
    if d and os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if not (fn.startswith("account_") and fn.endswith(".json")):
                continue
            try:
                j = json.load(open(os.path.join(d, fn), "r", encoding="utf-8"))
            except Exception:
                continue
            snap = j.get("snapshot") or {}
            auth = snap.get("auth") or {}
            acct = snap.get("account") or {}
            add(j.get("uid") or acct.get("uid"),
                j.get("display_name") or acct.get("nickname"),
                acct.get("phoneNumber"),
                auth.get("accessToken"), auth.get("refreshToken"),
                auth.get("domain"), "switcher")

    # 2) 登录态文件（当前登录账号）
    rel = os.path.join("CodeBuddyExtension", "Data", "Public", "auth", "workbuddy-desktop.info")
    for var in ("LOCALAPPDATA", "APPDATA"):
        base = os.environ.get(var)
        if not base:
            continue
        p = os.path.join(base, rel)
        try:
            j = json.load(open(p, "r", encoding="utf-8"))
        except Exception:
            continue
        a = j.get("auth") or {}
        acct = j.get("account") or {}
        add(acct.get("uid"), acct.get("nickname"), acct.get("phoneNumber"),
            a.get("accessToken"), a.get("refreshToken"), a.get("domain"), "authfile")
        break

    # 3) 日志兜底
    logs = os.path.join(os.path.expanduser("~"), ".workbuddy", "logs")
    tok_re = re.compile(rb"Bearer\s+(eyJ[A-Za-z0-9._\-]{150,})")
    if os.path.isdir(logs):
        found = {}
        for dp, _dn, fns in os.walk(logs):
            for name in fns:
                if not name.lower().endswith(".log"):
                    continue
                fp = os.path.join(dp, name)
                try:
                    if os.path.getsize(fp) > 200 * 1024 * 1024:
                        continue
                    data = open(fp, "rb").read()
                except Exception:
                    continue
                if b"Bearer eyJ" not in data:
                    continue
                mt = os.path.getmtime(fp)
                for m in tok_re.finditer(data):
                    t = m.group(1).decode("ascii", "replace")
                    if t not in found or mt > found[t]:
                        found[t] = mt
        for t, mt in sorted(found.items(), key=lambda kv: kv[1], reverse=True)[:20]:
            add(None, "", "", t, "", "", "log")

    # 有昵称的排前面，输出更可读
    out.sort(key=lambda a: (a["src"] != "switcher", not a["name"], a["key"]))
    return out


# ---------------------------------------------------------------- HTTP
def _http(url, token, uid, domain, method="POST", body=None, extra=None, retries=1):
    data = json.dumps(body if body is not None else {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + token)
    if uid:
        req.add_header("X-User-Id", uid)
    req.add_header("X-Domain", domain or "copilot.tencent.com")
    req.add_header("User-Agent", "WorkBuddy/1.0")
    for k, v in (extra or {}).items():
        req.add_header(k, v)
    delay, attempt = 0.8, 0
    while True:
        try:
            r = _opener.open(req, timeout=TIMEOUT)
            raw = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(raw)
            except Exception:
                return r.status, {"raw": raw[:200]}
        except urllib.error.HTTPError as e:
            txt = e.read().decode("utf-8", "replace")
            try:
                obj = json.loads(txt)
            except Exception:
                obj = {"code": -1, "msg": txt[:200]}
            if e.code >= 500 and attempt < retries:
                attempt += 1
                time.sleep(delay)
                delay *= 2
                continue
            return e.code, obj
        except Exception as e:
            if attempt < retries:
                attempt += 1
                time.sleep(delay)
                delay *= 2
                continue
            return -1, {"code": -1, "msg": "%s: %s" % (type(e).__name__, e)}


def base_list(acc):
    out = []
    dom = (acc.get("domain") or "").replace("https://", "").replace("http://", "").strip("/")
    if dom:
        out.append("https://" + dom)
    for b in DEFAULT_BASES:
        if b not in out:
            out.append(b)
    return out


# ---------------------------------------------------------------- 签到
def do_checkin(acc):
    """每日签到。返回 (状态串, 明细)"""
    for base in base_list(acc):
        for pre in PATH_PREFIXES:
            url = base + pre + "daily-checkin"
            st, obj = _http(url, acc["token"], acc["uid"], acc["domain"] or None)
            code = obj.get("code")
            if st == 404 or st == -1:
                continue
            if code in AUTH_BAD or st in (401, 403):
                return "AUTH_FAIL", "HTTP %s code=%s" % (st, code)
            if code == CODE_OK:
                d = obj.get("data") or {}
                return "OK", "+%s 积分，连续 %s 天" % (d.get("credit", "?"), d.get("streak_days", "?"))
            if code == CODE_ALREADY:
                return "ALREADY", "今日已签到"
            return "FAIL", "HTTP %s code=%s %s" % (st, code, (obj.get("msg") or "")[:80])
    return "FAIL", "所有 base/prefix 组合均不可用"


# ---------------------------------------------------------------- 成长收割
GROWTH_WEB = {"X-Client-Platform": "web"}


def growth_get(acc, path):
    for base in base_list(acc):
        url = base + path
        st, obj = _http(url, acc["token"], acc["uid"], acc["domain"] or None,
                        method="GET", extra=GROWTH_WEB)
        if st in (404, -1):
            continue
        return st, obj
    return 404, {"code": -1, "msg": "growth endpoint unreachable"}


def growth_post(acc, path, body=None):
    for base in base_list(acc):
        url = base + path
        st, obj = _http(url, acc["token"], acc["uid"], acc["domain"] or None,
                        method="POST", body=body, extra=GROWTH_WEB)
        if st in (404, -1):
            continue
        return st, obj
    return 404, {"code": -1, "msg": "growth endpoint unreachable"}


def do_accept(acc, only_list=False):
    """把所有 not_accepted 任务接了 —— 不接任务后端不计数，这是关键前置。
    accept 接口实测 body 必须是 {"task_codes":[...]}（单数 task_code 会 400）。"""
    st, tj = growth_get(acc, "/v2/activity/growth/tasks")
    if st != 200:
        return ["  ! 任务列表拉取失败 HTTP %s" % st]
    tasks = (tj.get("data") or {}).get("tasks") or []
    pending = [t.get("task_code") for t in tasks
               if t.get("accept_status") == "not_accepted"]
    if not pending:
        return ["  · 所有任务均已接/已领，无需 accept"]
    if only_list:
        return ["  · 待接任务 %d 个：%s" % (len(pending), ", ".join(pending))]
    lines, failed = [], []
    for i in range(0, len(pending), 5):
        chunk = pending[i:i + 5]
        cst, obj = growth_post(acc, "/v2/activity/growth/tasks/accept",
                               {"task_codes": chunk})
        if obj.get("code") == 0 or cst == 200:
            lines.append("  ✅ accept %s" % ", ".join(chunk))
        else:
            # 整批失败时逐个重试，定位是哪个任务拒收
            for c in chunk:
                s, o = growth_post(acc, "/v2/activity/growth/tasks/accept",
                                   {"task_codes": [c]})
                if o.get("code") == 0 or s == 200:
                    lines.append("  ✅ accept %s（单发）" % c)
                else:
                    failed.append("%s(HTTP%s)" % (c, s))
    if failed:
        lines.append("  ! 拒收：%s" % ", ".join(failed))
    return lines


def do_growth(acc, claim=True, only_list=False):
    """拉取任务并（可选）领取已完成的任务。返回 (credit, energy, 行列表)"""
    st, tj = growth_get(acc, "/v2/activity/growth/tasks")
    if st != 200:
        return 0, 0, ["  ! 任务列表拉取失败 HTTP %s %s" % (st, (tj.get("msg") or "")[:60])]
    tasks = (tj.get("data") or {}).get("tasks") or []
    lines, credit, energy = [], 0, 0
    for t in tasks:
        code = t.get("task_code")
        status = t.get("accept_status")
        pr = t.get("progress") or {}
        cur, tgt = pr.get("current"), pr.get("target")
        done = cur is not None and tgt is not None and cur >= tgt
        prog = "%s/%s" % (cur, tgt) if cur is not None else "-/-"
        if status == "claimed":
            if only_list:
                lines.append("  ✔ %-22s claimed       %s  %sc" % (code, prog, t.get("reward_credit")))
            continue
        if not done:
            lines.append("  · %-22s %-12s %s  %sc" % (code, status, prog, t.get("reward_credit")))
            continue
        if not claim:
            lines.append("  ✓ %-22s 可领 (+%sc)" % (code, t.get("reward_credit")))
            continue
        cst, obj = growth_post(acc, "/v2/activity/growth/tasks/%s/claim" % code, {})
        res = obj.get("data") or {}
        if obj.get("code") == 0 and (res.get("credit") or 0) > 0:
            cr, en = res.get("credit", 0), res.get("energy", 0)
            credit += cr
            energy += en
            lines.append("  ✅ 领取 %-18s +%s 积分 / +%s 能量" % (code, cr, en))
        elif isinstance(res, dict) and res.get("already_claimed"):
            lines.append("  · %-20s 已领过" % code)
        else:
            lines.append("  ? %-20s HTTP %s %s" % (code, cst, json.dumps(obj, ensure_ascii=False)[:100]))
    return credit, energy, lines


# ---------------------------------------------------------------- 派猫旅行（纯白赚）
TRAVEL_LOCATION = 1  # 咖啡馆；4 个地点奖励一致（5~10 积分），任选


def do_travel(acc, claim=True, only_list=False):
    """派猫猫旅行 + 归来领奖励。零成本，每个账号每天可派。
    depart: POST /v2/activity/growth/buddy/travel/depart  {"location_id": N}
    claim : POST /v2/activity/growth/buddy/travel/claim   {}
    status: GET  /v2/activity/growth/buddy/travel/status
    """
    st, sj = growth_get(acc, "/v2/activity/growth/buddy/travel/status")
    if st != 200:
        return 0, ["  ! 旅行状态拉取失败 HTTP %s" % st]
    d = sj.get("data") or {}
    state = d.get("state")
    arrive = d.get("arrive_at") or 0
    srvnow = d.get("server_now") or 0
    rew = d.get("reward_credit") or 0
    loc = (d.get("location") or {}).get("name") or "-"

    def hhmm(ts):
        try:
            return time.strftime("%H:%M", time.localtime(ts))
        except Exception:
            return "?"

    if state == "idle":
        if d.get("daily_limit_reached"):
            return 0, ["  · 派猫：今日次数已用完"]
        if only_list:
            return 0, ["  ✓ 派猫：可派（idle）"]
        cst, obj = growth_post(acc, "/v2/activity/growth/buddy/travel/depart",
                               {"location_id": TRAVEL_LOCATION})
        dd = obj.get("data") or {}
        if obj.get("code") == 0 or cst == 200:
            lc = dd.get("location") or {}
            return 0, ["  🐾 已派出旅行 → %s，预计 %s 回来（%s 积分）" % (
                lc.get("name") or "?", hhmm(dd.get("arrive_at") or 0),
                dd.get("reward_credit") if dd.get("reward_credit") else "?")]
        return 0, ["  ? 派猫失败 HTTP %s %s" % (cst, json.dumps(obj, ensure_ascii=False)[:100])]

    can_claim = (arrive and srvnow and srvnow >= arrive) or state in (
        "arrived", "claimable", "done", "finished", "settled")
    if not can_claim:
        return 0, ["  🐾 猫在「%s」旅行中，%s 回来（%s 积分）" % (loc, hhmm(arrive), rew)]
    if only_list or not claim:
        return 0, ["  ✓ 派猫：可领取（state=%s，%s 积分）" % (state, rew)]
    cst, obj = growth_post(acc, "/v2/activity/growth/buddy/travel/claim", {})
    dd = obj.get("data") or {}
    if obj.get("code") == 0:
        cr = dd.get("reward_credit") or dd.get("credit") or rew
        return (cr if isinstance(cr, int) else 0), ["  ✅ 收猫奖励 +%s 积分" % cr]
    return 0, ["  ? 收猫失败 HTTP %s %s" % (cst, json.dumps(obj, ensure_ascii=False)[:100])]


# ---------------------------------------------------------------- 主流程
def label(acc):
    nm = acc.get("name") or ""
    ph = _mask(acc.get("phone")) if acc.get("phone") else ""
    bits = [b for b in (nm, ph) if b]
    return "%s（%s）" % (" / ".join(bits), acc["key"][:8]) if bits else acc["key"][:8]


def main():
    argv = sys.argv[1:]
    only_list = "--list" in argv
    # --list 是"只读体检"，等价于同时跑签到+成长两项，只是不真正下发写操作
    do_c = not argv or "--checkin" in argv or only_list
    do_a = not argv or "--accept" in argv or only_list
    do_g = not argv or "--growth" in argv or only_list
    do_t = not argv or "--travel" in argv or only_list
    filt = None
    for a in argv:
        if a.startswith("--only="):
            filt = a.split("=", 1)[1].lower()
        elif a == "--only" and argv.index(a) + 1 < len(argv):
            filt = argv[argv.index(a) + 1].lower()

    accs = load_accounts()
    if not accs:
        print("! 未找到任何可用账号凭据（切换器存档 / 登录态文件 / 日志 均无有效 token）")
        return 1
    if filt:
        accs = [a for a in accs
                if filt in a["key"].lower() or filt in (a["name"] or "").lower()
                or filt in (a["phone"] or "")]

    print("=== WorkBuddy 多账号收割（共 %d 个账号）===\n" % len(accs))
    grand_c = grand_e = 0
    for i, acc in enumerate(accs, 1):
        days = "剩%.0f天" % ((acc["exp"] - now()) / 86400.0) if acc["exp"] else "?"
        print("[%d/%d] %s   来源=%s token%s" % (i, len(accs), label(acc), acc["src"], days))
        if do_c:
            if only_list:
                print("  (--list 模式，跳过签到)")
            else:
                stt, det = do_checkin(acc)
                mark = {"OK": "✅", "ALREADY": "·", "AUTH_FAIL": "🔑", "FAIL": "✗"}[stt]
                print("  签到: %s %s" % (mark, det))
        if do_a:
            for ln in do_accept(acc, only_list=only_list):
                print(ln)
        if do_g:
            c, e, lines = do_growth(acc, claim=not only_list, only_list=only_list)
            grand_c += c
            grand_e += e
            if lines:
                print("\n".join(lines))
            else:
                print("  · 没有可收割的成长任务")
        if do_t:
            tc, tlines = do_travel(acc, claim=not only_list, only_list=only_list)
            grand_c += tc
            for ln in tlines:
                print(ln)
        print()

    if not only_list:
        print("=== 合计本次领取：+%s 积分 / +%s 能量 ===" % (grand_c, grand_e))
    return 0


if __name__ == "__main__":
    sys.exit(main())

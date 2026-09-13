# -*- coding: utf-8 -*-
"""
Buddy 加油站 — 每日积分「API 直连」领取（无头模式，锁屏也能跑）

凭据来源（按优先级）：
  1) WorkBuddy 登录态文件（明文 JSON，首选）
       %LOCALAPPDATA%\\CodeBuddyExtension\\Data\\Public\\auth\\workbuddy-desktop.info
     含 accessToken / refreshToken / domain / expiresAt，命中即用，无需任何解密。
  2) 主线程日志兜底（登录态文件缺失时）
       ~/.workbuddy/logs/<YYYY-MM-DD>/workbuddyMainThread__*.log
     其中 `Bearer eyJ...` 形式的 RS256 JWT 未打码，按 JWT `iat` 降序取最新。

接口（base 与路径前缀都自适应，不写死）：
  查询: POST {base}{prefix}checkin-activity-status
  领取: POST {base}{prefix}daily-checkin     （幂等：已领返回 code=10001）
  余额: POST {base}{prefix}get-user-resource
  base   = https://<登录态文件的 auth.domain>  →  兜底 copilot.tencent.com / www.codebuddy.cn
  prefix = /billing/meter/  →  兜底 /v2/billing/meter/
  请求头: Authorization: Bearer <token> / X-User-Id(<JWT sub>) / X-Domain: www.codebuddy.cn

因为完全不依赖界面，所以桌面锁屏 / WorkBuddy 不在前台时同样能领。

退出码：
  0 = 成功（含"今天已领过"）
  3 = 无法通过 API 完成（无凭据 / 401 / 接口路径变更 / 网络不可达）→ 建议回退 UI
  4 = 接口有明确业务答复但领取不通过（活动未开始/已结束等）→ 重试无意义

注意：`daily-checkin` 在"今天已签到"时是 **HTTP 400 + code=10001**，
      所以成功判定必须以 **业务码** 为准，不能要求 HTTP 200。

用法：
  claim_api.py                 # 领取（今天已领则跳过）
  claim_api.py verify          # 只看状态 + 余额
  claim_api.py --force         # 忽略本地 history 强制走一次
  claim_api.py --diagnose      # 环境体检（凭据/连通性/接口/余额逐项 PASS/FAIL）
  claim_api.py --no-balance    # 少发一次请求，不查余额

环境变量（测试/隔离用）：
  WB_AUTH_INFO    覆盖登录态文件路径
  WB_LOGS_ROOT    覆盖日志根目录
"""
import os
import re
import ssl
import sys
import json
import time
import base64
import datetime
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(HERE, "logs")
HISTORY = os.path.join(HERE, "history.json")

# ---- 端点：base 与路径前缀都不写死，运行时自适应 ----
DEFAULT_BASES = ["https://copilot.tencent.com", "https://www.codebuddy.cn"]
PATH_PREFIXES = ["/billing/meter/", "/v2/billing/meter/"]
X_DOMAIN = "www.codebuddy.cn"          # 服务端当前不强制，但保持与客户端一致
UA = "WorkBuddy/1.0"
TIMEOUT = 20
RETRIES = 2                            # 网络错误 / 5xx 的额外重试次数（指数退避）
MAX_TRIES = 5                          # 最多尝试几个凭据，避免异常时反复打接口

# ---- 业务码 ----
CODE_OK = 0
CODE_ALREADY = 10001                   # "今天已签到，请明天再来"（HTTP 400 返回）
CODE_AUTH_BAD = (401, 403, 10085)      # 鉴权类：换凭据 / 回退 UI

LOGS_ROOT = os.environ.get("WB_LOGS_ROOT") or os.path.join(
    os.path.expanduser("~"), ".workbuddy", "logs")

TODAY = datetime.date.today()
LOG_FILE = os.path.join(LOG_DIR, "claim-%s.log" % TODAY.strftime("%Y-%m-%d"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# ---------------- logging ----------------
def log(msg):
    line = "[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_history():
    try:
        with open(HISTORY, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_history(d):
    try:
        with open(HISTORY, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def record_result(ok, detail, **extra):
    h = load_history()
    rec = {
        "claimed": bool(ok),
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "detail": detail,
        "via": "api",
    }
    rec.update({k: v for k, v in extra.items() if v is not None})
    h[TODAY.isoformat()] = rec
    save_history(h)


# ---------------- 小工具 ----------------
def _ms_to_s(x):
    """毫秒时间戳 → 秒。"""
    try:
        x = float(x)
    except Exception:
        return None
    return int(x / 1000.0) if x > 1e11 else int(x)


def _short(p, width=3):
    """路径缩写：只保留尾部若干段，避免日志里出现完整用户名。"""
    try:
        parts = [x for x in str(p).replace("\\", "/").split("/") if x]
        return ".../" + "/".join(parts[-width:])
    except Exception:
        return str(p)


def _mask(s):
    """打码账号名 / 手机号。"""
    if not s:
        return "?"
    s = str(s)
    if len(s) <= 2:
        return s[0] + "*"
    if len(s) <= 4:
        return s[0] + "*" * (len(s) - 1)
    return s[:3] + "*" * (len(s) - 5) + s[-2:]


def _b64url_json(seg):
    pad = "=" * (-len(seg) % 4)
    return json.loads(base64.urlsafe_b64decode(seg + pad))


def token_exp(tok):
    """解析 JWT：返回 (exp_epoch, payload)；失败 (None, None)。"""
    try:
        payload = _b64url_json(tok.split(".")[1])
        return int(payload.get("exp")), payload
    except Exception:
        return None, None


def _now():
    return int(datetime.datetime.now().timestamp())


# ---------------- 凭据来源 1：登录态文件 ----------------
def auth_info_paths():
    """WorkBuddy 登录态文件候选路径（按优先级）。可用 WB_AUTH_INFO 覆盖。"""
    out = []
    env = os.environ.get("WB_AUTH_INFO")
    if env:
        out.append(env)
    rel = os.path.join("CodeBuddyExtension", "Data", "Public", "auth",
                       "workbuddy-desktop.info")
    for var in ("LOCALAPPDATA", "APPDATA"):
        base = os.environ.get(var)
        if base:
            out.append(os.path.join(base, rel))
    home = os.path.expanduser("~")
    out += [
        os.path.join(home, ".workbuddy", "auth", "workbuddy-desktop.info"),
        os.path.join(home, ".codebuddy", "auth", "workbuddy-desktop.info"),
    ]
    seen, uniq = set(), []
    for p in out:
        k = os.path.normcase(os.path.abspath(p))
        if k not in seen:
            seen.add(k)
            uniq.append(p)
    return uniq


def read_auth_file():
    """读取 WorkBuddy 登录态文件；成功返回 dict，否则 None。不修改文件。"""
    for p in auth_info_paths():
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            continue
        a = d.get("auth") or {}
        tok = a.get("accessToken") or ""
        if not (isinstance(tok, str) and tok.startswith("eyJ")):
            continue
        acct = d.get("account") or {}
        try:
            mt = os.path.getmtime(p)
        except Exception:
            mt = 0
        return {
            "path": p,
            "token": tok,
            "domain": (a.get("domain") or "").strip(),
            "file_exp": _ms_to_s(a.get("expiresAt")),
            "refresh_exp": _ms_to_s(a.get("refreshExpiresAt")),
            "has_refresh": bool(a.get("refreshToken")),
            "uid": acct.get("uid") or "",
            "nickname": acct.get("nickname") or "",
            "phone": acct.get("phoneNumber") or "",
            "mtime": mt,
        }
    return None


# ---------------- 凭据来源 2：主线程日志（兜底） ----------------
_TOKEN_RE = re.compile(rb"Bearer\s+(eyJ[A-Za-z0-9._\-]{150,})")


def log_tokens():
    """扫描日志目录，返回 [(token, mtime)]，按 mtime 降序、去重。"""
    found = {}
    if not os.path.isdir(LOGS_ROOT):
        return []
    for dp, _dn, fn in os.walk(LOGS_ROOT):
        for name in fn:
            if not name.lower().endswith(".log"):
                continue
            fp = os.path.join(dp, name)
            try:
                if os.path.getsize(fp) > 200 * 1024 * 1024:
                    continue
                with open(fp, "rb") as f:
                    data = f.read()
            except Exception:
                continue
            if b"Bearer eyJ" not in data:
                continue
            mt = os.path.getmtime(fp)
            for m in _TOKEN_RE.finditer(data):
                tok = m.group(1).decode("ascii", "replace")
                if tok not in found or mt > found[tok]:
                    found[tok] = mt
    return sorted(found.items(), key=lambda kv: kv[1], reverse=True)


# ---------------- 统一候选 ----------------
def candidates():
    """汇总可用凭据，登录态文件优先，其后日志（按 JWT iat 降序）。

    每项：{token, src, src_detail, mtime, domain, uid, exp, info}
    已过期（剩余 <1h）或无法取到 sub/uid 的会被剔除。
    """
    now = _now()
    out, seen = [], set()

    def add(tok, src, detail, mtime, domain="", uid=""):
        if not tok or tok in seen:
            return
        exp, payload = token_exp(tok)
        if exp is not None and exp - now < 3600:
            return
        payload = payload or {}
        real_uid = uid or payload.get("sub") or ""
        if not real_uid:
            return
        seen.add(tok)
        out.append({
            "token": tok, "src": src, "src_detail": detail, "mtime": mtime,
            "domain": domain, "uid": real_uid, "exp": exp,
            "uname": payload.get("preferred_username") or "",
        })

    af = read_auth_file()
    if af:
        add(af["token"], "authfile", af["path"], af["mtime"],
            af["domain"], af["uid"])

    # 日志兜底：按 iat 降序（缺失则用文件 mtime）
    scored = []
    for tok, mt in log_tokens():
        exp, payload = token_exp(tok)
        if exp is not None and exp - now < 3600:
            continue
        issued = None
        try:
            if payload and payload.get("iat"):
                issued = int(payload["iat"])
        except Exception:
            issued = None
        scored.append((issued if issued else int(mt), tok, mt))
    scored.sort(key=lambda s: s[0], reverse=True)
    for _k, tok, mt in scored:
        add(tok, "log", LOGS_ROOT, mt)
    return out


def describe_cand(c):
    bits = ["来源=%s" % ("登录态文件" if c["src"] == "authfile" else "日志")]
    if c["src"] == "authfile":
        bits.append(_short(c["src_detail"]))
    if c.get("domain"):
        bits.append("domain=%s" % c["domain"])
    if c.get("exp"):
        bits.append("剩余%.1f天" % ((c["exp"] - _now()) / 86400.0))
    u = _mask(c.get("uname"))
    if u != "?":
        bits.append("用户=%s" % u)
    return " | ".join(bits)


# ---------------- HTTP ----------------
_CTX = ssl.create_default_context()
_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),   # 显式绕过系统代理：代理未启动时否则会 ECONNREFUSED
    urllib.request.HTTPSHandler(context=_CTX),
)


_DNS_HINTS = ("getaddrinfo", "Name or service not known", "11001", "11004",
              "no such host", "nodename nor servname")


def _http(url, token, uid, body=None, retries=RETRIES):
    """POST JSON。网络错误 / 5xx 指数退避重试；4xx 不重试。返回 (http_code, obj)。"""
    data = json.dumps(body if body is not None else {}).encode("utf-8")
    delay, attempt = 0.8, 0
    while True:
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", "Bearer " + token)
        if uid:
            req.add_header("X-User-Id", uid)
        req.add_header("X-Domain", X_DOMAIN)
        req.add_header("User-Agent", UA)
        try:
            r = _OPENER.open(req, timeout=TIMEOUT)
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
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
            msg = "%s: %s" % (type(e).__name__, e)
            # DNS 解析失败说明这个域名本身不通，重试无意义，直接换 base
            if any(h.lower() in msg.lower() for h in _DNS_HINTS):
                return -1, {"code": -1, "msg": msg}
            if attempt < retries:
                attempt += 1
                time.sleep(delay)
                delay *= 2
                continue
            return -1, {"code": -1, "msg": msg}


def base_list(cand):
    """候选 base：登录态文件里的 domain 优先，其后已知域名。"""
    out = []
    dom = (cand or {}).get("domain") or ""
    if dom:
        dom = dom.replace("https://", "").replace("http://", "").strip("/")
        if dom:
            out.append("https://" + dom)
    for b in DEFAULT_BASES:
        if b not in out:
            out.append(b)
    return out


def call_meter(op, cand, body=None):
    """调用 /billing/meter/<op>，自动尝试 base × 路径前缀。

    返回 (http_code, obj, url)。
      · 404          → 该前缀不对，继续换组合
      · -1（DNS/连接失败）→ 该 base 不通，继续换 base（key：domain 可能是历史遗留值）
    全部组合失败时返回最后一次的结果。
    """
    last = (404, {"code": -1, "msg": "no endpoint tried"}, None)
    for base in base_list(cand):
        for pre in PATH_PREFIXES:
            url = base + pre + op
            st, obj = _http(url, cand["token"], cand["uid"])
            if st in (404, -1):
                last = (st, obj, url)
                continue
            return st, obj, url
    return last


# ---------------- 业务封装 ----------------
def fetch_status(cand):
    """活动状态（信息展示用）。失败返回 {}。"""
    st, obj, _u = call_meter("checkin-activity-status", cand)
    if st == 200 and obj.get("code") == CODE_OK:
        return obj.get("data") or {}
    return {}


def parse_balance(data):
    """从 get-user-resource 返回中汇总 credits 余额。"""
    try:
        inner = ((data or {}).get("Response") or {}).get("Data") or {}
    except Exception:
        return None
    accts = inner.get("Accounts") or []
    remain = cycle = 0.0
    names, n = [], 0
    for a in accts:
        if not isinstance(a, dict):
            continue
        if (a.get("CapacityUnit") or "").lower() != "credits":
            continue
        n += 1
        for src, acc in ((a.get("CapacityRemain"), "remain"),
                         (a.get("CycleCapacityRemain"), "cycle")):
            try:
                v = float(src)
            except Exception:
                continue
            if acc == "remain":
                remain += v
            else:
                cycle += v
        pn = a.get("PackageName")
        if pn and pn not in names:
            names.append(pn)
    if n == 0:
        return None
    return {"packages": n, "remain": remain, "cycle_remain": cycle,
            "names": names[:6], "total_count": inner.get("TotalCount")}


def fetch_balance(cand):
    st, obj, _u = call_meter("get-user-resource", cand)
    if st == 200 and obj.get("code") == CODE_OK:
        return parse_balance(obj.get("data") or {})
    return None


def balance_line(bal):
    if not bal:
        return "余额: (未取到)"
    return "余额: %.0f credits 可用 / %.0f 本周期剩余（%d 个资源包：%s）" % (
        bal["remain"] or 0, bal["cycle_remain"] or 0,
        bal["packages"], "、".join(bal["names"]))


# ---------------- 主流程 ----------------
def _status_line(d):
    if not d:
        return "状态: (未取到)"
    return ("活动=%s | 今天已领=%s | 连续=%s天 | 今日可得=%s | 活动累计=%s | 周期=%s~%s"
            % (d.get("theme_name"), d.get("today_checked_in"), d.get("streak_days"),
               d.get("today_credit"), d.get("total_credits"),
               d.get("start_time"), d.get("end_time")))


def run_claim():
    log("=== Buddy 加油站 每日领取 (API 直连) 开始 ===")
    argv = sys.argv[1:]
    force = "--force" in argv
    want_balance = "--no-balance" not in argv

    if not force and load_history().get(TODAY.isoformat(), {}).get("claimed"):
        log("今日(%s)历史记录已领取，跳过。" % TODAY.isoformat())
        return 0

    cands = candidates()
    if not cands:
        af = read_auth_file()
        if not af:
            log("未找到登录态文件（候选路径 %d 个均不可用）" % len(auth_info_paths()))
        if not log_tokens():
            log("日志中也没有 Bearer token。")
        log("没有可用凭据，退出码 3（交由 run_claim.bat 回退到 UI 方式）。")
        return 3

    saw_auth_reject = False
    saw_endpoint_gone = False
    network_dead = False
    last_err = None

    for n, c in enumerate(cands[:MAX_TRIES], 1):
        log("尝试凭据 (%d/%d)：%s" % (n, min(len(cands), MAX_TRIES), describe_cand(c)))
        st, obj, url = call_meter("daily-checkin", c)
        code = obj.get("code")
        log("  daily-checkin -> HTTP %s code=%s %s"
            % (st, code, json.dumps(obj, ensure_ascii=False)[:200]))

        # 鉴权类失败：换下一个凭据
        if code in CODE_AUTH_BAD or st in (401, 403):
            saw_auth_reject = True
            log("  -> 凭据被拒，换下一个。")
            continue
        # 端点不存在：换组合（base × 前缀 已在本轮内试完）
        if st == 404:
            saw_endpoint_gone = True
            log("  -> 接口路径不可用(404)，换下一个组合。")
            continue
        # 网络层失败：换凭据也没意义
        if st == -1:
            network_dead = True
            last_err = "%s" % obj.get("msg")
            log("  -> 网络不可达：%s" % last_err)
            break

        # 到这里接口已给出明确业务答复 —— 以业务码判定，不看 HTTP 状态码
        if code in (CODE_OK, CODE_ALREADY):
            already = (code == CODE_ALREADY)
            d = fetch_status(c)
            bal = fetch_balance(c) if want_balance else None
            streak = (d.get("streak_days")
                      if d else (obj.get("data") or {}).get("streak_days"))
            total = d.get("total_credits") if d else None
            gain = (obj.get("data") or {}).get("credit")
            if already:
                log("今天已签到（连续 %s 天），无需再领。" % streak)
            else:
                log("✅ 领取成功。今日 +%s 积分，连续 %s 天，活动累计 %s。"
                    % (gain if gain is not None else (d.get("today_credit") or "?"),
                       streak, total))
            log("  %s" % _status_line(d))
            if want_balance:
                log("  %s" % balance_line(bal))
            record_result(True,
                          ("already checked in; " if already else "api claim ok; ")
                          + "streak=%s total=%s" % (streak, total),
                          src=c["src"],
                          streak=streak,
                          total_credits=total,
                          balance=(bal or {}).get("remain") if bal else None)
            return 0

        last_err = "HTTP %s code=%s msg=%s" % (st, code, obj.get("msg"))
        log("  -> 业务失败：%s" % last_err)
        break   # 明确的业务答复，换凭据也是同样结果

    if saw_endpoint_gone and not (saw_auth_reject or network_dead or last_err):
        log("所有接口组合均 404（接口路径可能已变更），退出码 3（回退 UI）。")
        return 3
    if network_dead:
        log("网络不可达：%s，退出码 3（回退 UI）。" % last_err)
        return 3
    if saw_auth_reject and not last_err:
        log("所有凭据均被拒(401/403)，退出码 3（回退 UI）。")
        return 3
    log("接口调用失败：%s，退出码 4。" % (last_err or "未知原因"))
    record_result(False, "api failed: %s" % (last_err or "unknown"))
    return 4


def verify_only():
    log("=== 仅查询状态 (API verify) ===")
    cands = candidates()
    if not cands:
        if not read_auth_file():
            log("未找到登录态文件。")
        log("没有可用凭据，退出码 3。")
        return 3
    for c in cands[:MAX_TRIES]:
        log("凭据：%s" % describe_cand(c))
        st, obj, url = call_meter("checkin-activity-status", c)
        if obj.get("code") == CODE_OK:
            d = obj.get("data") or {}
            log("端点: %s" % url)
            log(_status_line(d))
            log("最近签到日: %s" % ((d.get("checkin_dates") or [])[:10]))
            if "--no-balance" not in sys.argv[1:]:
                log(balance_line(fetch_balance(c)))
            return 0
        log("  查询失败：HTTP %s code=%s %s"
            % (st, obj.get("code"), obj.get("msg")))
    log("所有凭据均查询失败，退出码 3。")
    return 3


# ---------------- 体检 ----------------
def diagnose():
    log("=== 环境体检 (--diagnose) ===")
    ok_all = True

    def chk(name, ok, detail=""):
        nonlocal ok_all
        ok_all = ok_all and ok
        log("  [%s] %-16s %s" % ("PASS" if ok else "FAIL", name, detail))

    # 1) 登录态文件
    af = read_auth_file()
    if af:
        left = (af["file_exp"] - _now()) / 86400.0 if af["file_exp"] else -1
        chk("登录态文件", True, "%s | domain=%s | 剩余 %.1f 天 | refreshToken=%s | 账号=%s"
            % (_short(af["path"]), af["domain"] or "(空)", left,
               "有" if af["has_refresh"] else "无", _mask(af["nickname"] or af["phone"])))
    else:
        chk("登录态文件", False, "未找到（已探 %d 个路径）" % len(auth_info_paths()))

    # 2) 日志兜底
    lt = log_tokens()
    chk("日志 token", bool(lt), "%s 中找到 %d 枚" % (_short(LOGS_ROOT, 2), len(lt)))

    # 3) 候选汇总
    cs = candidates()
    chk("可用凭据", bool(cs), "%d 个（登录态 %d / 日志 %d）"
        % (len(cs),
           len([x for x in cs if x["src"] == "authfile"]),
           len([x for x in cs if x["src"] == "log"])))

    # 4) 连通性
    for base in base_list(cs[0] if cs else None):
        st, obj = _http(base + PATH_PREFIXES[0] + "checkin-activity-status",
                        (cs[0] if cs else {}).get("token", "") or "x",
                        (cs[0] if cs else {}).get("uid", ""))
        reachable = st != -1
        chk("连通 " + base.replace("https://", ""), reachable,
            "HTTP %s%s" % (st, "" if reachable else " (" + str(obj.get("msg"))[:60] + ")"))

    if not cs:
        log("=> 体检结果：FAIL（无可用凭据，API 路径不可用，将回退 UI）")
        return 1

    c = cs[0]
    # 5) 接口
    st, obj, url = call_meter("checkin-activity-status", c)
    good = st == 200 and obj.get("code") == CODE_OK
    chk("活动状态接口", good, "HTTP %s%s | %s"
        % (st, (" " + url) if good else "",
           _status_line(obj.get("data")) if good else obj.get("msg")))
    ok_all = ok_all and good

    # 6) 余额
    bal = fetch_balance(c)
    chk("余额接口", bool(bal), balance_line(bal))
    ok_all = ok_all and bool(bal)

    # 7) 历史（信息性：全新部署时为空是正常的，不计入 FAIL）
    h = load_history()
    recent = sorted(h.items())[-3:]
    log("  [INFO] %-16s %s" % ("历史记录",
        " | ".join("%s:%s" % (k, "✓" if v.get("claimed") else "✗") for k, v in recent)
        or "(空，尚未运行过)"))

    log("=> 体检结果：%s" % ("PASS" if ok_all else "部分 FAIL"))
    return 0 if ok_all else 1


# ---------------- 入口 ----------------
if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--diagnose" in argv:
        code = diagnose()
    elif "verify" in argv:
        code = verify_only()
    else:
        code = run_claim()
    log("=== 结束 (exit=%s) ===" % code)
    sys.exit(code)

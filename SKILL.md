---
name: workbuddy-growth-plan-autoclaim
version: 6.4.0
description: WorkBuddy 成长计划（成长中心）全自动收割——多账号签到/接任务/领奖/派猫猫旅行；通过本机 ACP 完成对话类任务
  （含黑猫彩蛋夜间 GLM-5.2 对话）；通过 CDP 接管桌面客户端 UI 自动完成
  create_canvas(+300)/template_5(+100)/expert_5 召唤专家/playbook_prompt
  灵感做同款(+100)/Expert_lighthouse 轻量云连接(+100)。 自包含、可移植（换账号/换电脑一键 setup）。
type: automation
agent_created: true
---

# WorkBuddy 成长计划 · 全自动收割（自包含可移植包）

## 换电脑 / 新环境部署清单（5 分钟）
1. **把整个 skill 目录拷过去**（或 git 拉取）：`~/.workbuddy/skills/workbuddy-growth-plan-autoclaim/`
2. **一键装环境**（本目录双击 `setup_env.bat`）：自动探测受管 Python → 建 venv →
   `pip install playwright urllib3` → `playwright install chromium`。
   全部路径用 `%USERPROFILE%` 自适应用户名，**换电脑零改动**。
3. **账号切换器**（多账号必需）：在 WorkBuddy 里安装并登录「账号切换器」（或你自己的多账号方案），
   登录各账号一次 → 生成 `%APPDATA%\WorkBuddyAccountSwitcher\accounts\account_*.json`（脚本自动读它）
4. **验证自包含**：`python scripts/harvest.py --list` —— 应列出所有账号与任务进度
5. **定时任务**：重建 automation（见文末），rrule `FREQ=DAILY;BYHOUR=0..23;BYMINUTE=5`
6. **CDP 自动化**（做画布/模板/召唤专家）：双击本目录 `run_autofarm.bat` 或 `start_workbuddy_debug.bat`

## 自包含性（v6.0.0 变更）
- `claim_api.py` 已复制进本 skill 的 `scripts/`，`harvest.py`/`growth_claim.py` 优先从
  **本目录**导入（不再依赖 `workbuddy-points-autoclaim` skill）
- 全部路径改为：`os.path.dirname(os.path.abspath(__file__))` 或 `%LOCALAPPDATA%` 环境变量
- 两个 bat 启动器（`start_workbuddy_debug.bat` / `run_autofarm.bat`）已收进本目录，
  路径用 `%LOCALAPPDATA%` / `%~dp0` 自适应用户名

## 脚本清单
| 脚本 | 作用 | 是否需要客户端在跑 |
|---|---|---|
| `harvest.py` | 多账号：签到+接任务+领奖+派猫/收猫 | ❌ 纯 HTTP |
| `acp_autofarm.py` | 对话类任务（Model_chat_GLM5.2 / chat_5） | ✅（本机 ACP 端口） |
| `black_cat.py` | 黑猫彩蛋：夜间 GLM-5.2 对话推进（23:00-8:00 守卫） | ✅（本机 ACP 端口） |
| `cdp_autofarm.py` | UI 任务（create_canvas +300 / template_5 +100） | ✅（需 9222 调试端口） |
| `cdp_experts.py` | expert_5 召唤专家（**推荐 `--any N` 按可见卡片召唤**，跨账号通用） | ✅（需 9222） |
| `cdp_expert_dialog.py` | 检查专家对话回复 + 搜索框精确召唤 | ✅（需 9222） |
| `cdp_playbook.py` | **playbook_prompt（+100）**：hover 更多→灵感→点卡片→做同款→发送 | ✅（需 9222） |
| `cdp_lighthouse.py` | **Expert_lighthouse（+100）**：搜「轻量云」→召唤腾讯轻量云专家→发操作请求→点「连接」 | ✅（需 9222） |
| `cdp_appearance.py` | 切浅色/深色主题（`--set dark\|light`），供升级后重测 `Hp_Appearance` | ✅（需 9222） |
| `confirm_pending.py` | 清理「待确认」悬停会话（模板/灵感跑完后用） | ✅（需 9222） |
| `do_tpl_pairs.py` | 跨场景模板补齐（template_5 收尾） | ✅（需 9222） |
| `growth_claim.py` | 单账号成长任务领奖（简单版） | ❌ |
| `claim_api.py` | 每日签到 API（单账号，底层） | ❌ |
| `wb_cdp.py` | CDP 诊断/抓包/点击（开发用） | ✅（需 9222） |
| `setup_env.bat` | 换电脑一键装环境（venv + playwright + chromium） | ❌ |

## 它能做什么
1. **多账号收割**（`harvest.py`）：遍历 WorkBuddy账号切换器里的所有账号
   - 每日签到、批量接任务(accept)、领取已完成任务奖励
   - **派猫猫旅行 + 收取奖励**（纯白赚：出门 1~4 小时，回来领 5~10 积分）
2. **ACP 自动完成对话类任务**（`acp_autofarm.py`）★
   - 通过客户端本机 ACP 端点，程序化「新建会话 + 发消息」，服务端会真实计数
   - 实测可触发：`Model_chat_GLM5.2`（+100）、`chat_5`（+100）
   - **完全隔离**：会话不进用户对话列表，用户无感
3. **CDP 接管客户端 UI**（`cdp_autofarm.py`）★★
   - 客户端带 `--remote-debugging-port=9222` 启动后，用 Playwright 连 CDP 直接操作其 renderer DOM
   - **实测可完成 `create_canvas`（+300）**：新建任务 → 切「设计创意」tab → 输入 prompt → 点发送
     ⚠️ 首次创建画布会弹 **Ardot（腾讯设计）授权面板**：需先勾 `.ardot-auth-agreement-checkbox` 协议框，
     再点「**注册并授权**」（用 WorkBuddy 账号一键注册）→ 授权后重触发画布生成即计入。
     每个账号只需授权一次；授权面板无「确认」按钮时，就是尚未绑定 Ardot。
   - **实测可完成 `template_5`（+100）**：点模板 pill → **必须再补一句文本** → 点发送（5 个不同模板）
   - **实测可完成 `playbook_prompt`（+100）**：hover 侧栏「更多」→「灵感」→点卡片→「做同款」→发送（`cdp_playbook.py`）
   - **实测可完成 `Expert_lighthouse`（+100）**：搜索框过滤「轻量云」→召唤`腾讯轻量云专家`→发「查我的轻量云实例列表」→点「连接」（`cdp_lighthouse.py`）
   - 这是唯一能完成「需客户端功能 UI」任务的路径

##为什么必须是多账号（血泪教训）
用户会**频繁切换 WorkBuddy 账号**。v1 写死用 `candidates()[0]`，结果"在某账号做任务、用另一账号领奖"，
永远领不到还以为接口坏了。**权威凭据源 = 账号切换器存档**（按 uid 存完整登录态）。

## 凭据来源（按优先级，自动按 uid 去重）
1. `%APPDATA%\WorkBuddyAccountSwitcher\accounts\account_*.json` —— **权威**（uid/昵称/手机/token/domain）
2. `%LOCALAPPDATA%\CodeBuddyExtension\Data\Public\auth\workbuddy-desktop.info` —— 当前登录账号
3. `~/.workbuddy/logs/**` 里 `Bearer eyJ...` 正则兜底

token 剩余 < 1 小时的账号会被跳过（不支持自动 refresh）。

## API 契约（已逆向验证）

### HTTP（copilot.tencent.com）
- **必带头 `X-Client-Platform: web`** —— 缺失返回 404 page not found（头号坑）
- 其余头：`Authorization: Bearer <JWT>`、`X-User-Id: <sub>`、`X-Domain: <domain>`
- 任务：`GET /v2/activity/growth/tasks`
- 接任务：`POST /v2/activity/growth/tasks/accept`，body **必须** `{"task_codes":["a","b"]}`（单数会 400）
- 领奖：`POST /v2/activity/growth/tasks/{task_code}/claim`，body `{}`
- 签到：`POST {base}{prefix}daily-checkin`；已签到返回 HTTP 400 + **code=10001**（判定以业务码为准）
- 派猫：`GET .../buddy/travel/status`、`POST .../buddy/travel/depart {"location_id":1}`、`POST .../buddy/travel/claim {}`
- 其他可用：`energy`、`streak`、`lottery/{chances,draw,prizes}`、`buddy/{open,quota,list}`、`redeem/summary`
- **没有任何"完成任务/上报事件"接口** → 服务端只认真实业务事件

### ACP（本机，★关键）
- 端点：`http://127.0.0.1:<port>/api/v1/acp`（端口**会话级、动态**；日志里搜 `acpEndpoint=`）
- **握手无需认证**：`GET`（`Accept: text/event-stream`）→ 响应头给 `acp-connection-id` + `acp-session-token`
- 之后 `POST` 带这两个头，发 JSON-RPC 2.0
- 方法：`initialize` / `session/new` / `session/set_model` / `session/set_mode` /
  `session/set_config_option` / `session/prompt` / `session/cancel` / `session/fork`
- 参数：
  - `session/new` `{"cwd": "...", "mcpServers": []}` → 返回 sessionId
  - `session/set_model` `{"sessionId": ..., "modelId": "glm-5.2"}`
  - `session/prompt` `{"sessionId": ..., "prompt": [{"type":"text","text":"你好"}]}`
- **限制**：只对「客户端当前登录账号」生效；不能切账号；`template_5`（需 5 个不同模板）与
  `create_canvas`（需「设计创意」模式）无法通过 ACP 触发
- **安全（重要）**：ACP 端口是**会话级**的，直连普通端口可能正好是**用户当前正在看的对话**。
  脚本默认 `pick_port(safe=True)` —— **优先用 CLI host 会话端口**（`__workbuddy_cli_host__`，绝不打扰用户）；
  若该端口探测为空（客户端重启后日志格式变化/旧端口失效，v6.2.0 修复的真实 bug），**自动回退到
  `acpEndpoint` 端口**——`session/new` 会新建独立会话，消息不会插进用户当前对话，同样安全。
- **已排除的路子**（2026-09-12 实测）：
  - `_codebuddy.ai/uiControl` / `ui-query`（delegate tool，`provider:"web-ui"`）是 **agent → web-ui** 方向、
    操作的是 CodeBuddy Code Remote Control 页面，**不是 WorkBuddy 的画布/专家/模板 UI**；
    从 agent 侧直调返回 Method not found
  - 让 agent 自行装技能（想触发 `skill_1`）→ agent 只回 session_info_update 且 `phase=idle`，并未真正执行
  - Web 版无这些模块；桌面 `app.asar` 加密（仅 `cli/dist/codebuddy.js` 未加密，无成长业务端点）

### REST API（本机 CodeBuddy HTTP Server，需密码）
- **密码来源**：客户端日志里存有 sidecar 启动输出
  ```
  CodeBuddy Code HTTP Server
    Endpoint http://127.0.0.1:33467
    Web UI   http://127.0.0.1:33467/?password=<40位随机串>
  ```
  正则 `password=([A-Za-z0-9_\-]{20,})` 从 `main.log` 提取；**密码与端口一一对应**（每个 sidecar 一个）。
- **登录**：`POST /api/v1/auth/login {"password":"<pw>"}` → `{"success":true,"token":"<同密码>"}`
- **实测可用**：`/api/v1/info`、`/sessions`（含 `DELETE /sessions/<id>`）、`/plugins`(+enable/disable/uninstall)、
  `/settings`、`/workers`、`/stats`、`/scheduled-tasks`(GET 需 sessionId)、`/fs/*`、`/pty`、`/daemon/*`
- **否定结论**：**无账号切换端点**；**无画布/专家/模板/技能相关端点** → 对完成成长任务无帮助
  （`plugins/marketplaces/browse` 为 404）

### CDP（桌面客户端 UI 操控，★最强）
- 前提：客户端带 `--remote-debugging-port=9222` 启动（用根目录 `start_workbuddy_debug.bat`）
- 连接：`playwright.chromium.connect_over_cdp("http://127.0.0.1:9222")`
- **只有 1 个页面**：`app.asar/renderer/index.html` —— 就是 WorkBuddy 主界面
- 关键 DOM（WorkBuddy 5.2.6 / Electron 37）：
  | 元素 | 选择器 / 定位 |
  |---|---|
  | 新建任务 | 文本「新建任务」（侧栏 tab）|
  | 场景 tab | `[class*="wb-scene-tabs__pill"]`，文本=日常办公/代码开发/设计创意/网站设计/PPT设计/视觉海报 |
  | 输入框 | `div[class*="_editable_"]`（contenteditable，约 724×70）|
  | **发送按钮** | `div[class*="_large_hg7y0_"]`（32×32，**非 `<button>`**）。同类名有**两个**：附件在 x≈900、发送在 x≈1158 —— **必须取最右** |
  | 模板/快速操作 | `[class*="quick-actions__item"]`（文档处理/金融服务/数据分析及可视化/更多）|
  | 模型选择器 | composer 里显示当前模型名的 `button._trigger_*`（如 "GLM-5.3-Flash"）|
  | 任务数 | 侧栏 `任务 (N)`，正则 `任务\s*\((\d+)\)` |
- **模型选择（省钱关键，2026-09-12 实测）**：composer 模型菜单各档计费倍率 ——
  **Hy3 = 0.00x 限时免费**、Deepseek-V4.1 = 0.03x、Hy4 preview = 0.29x(夜间免费)、
  GLM-5.3-Flash = 0.06x、GLM-5.3 = 0.75x、GLM-5.2 = 0.79x。
  画布/模板任务对模型无要求 → 一律用 Hy3 白嫖；仅 `Model_chat_GLM5.2` 任务要求 GLM-5.2。
  注意同名模型菜单里可能有两档（Hy3 0.00x / 0.05x）→ 优先选含 "0.00" 的行。
  脚本入口：`cdp_autofarm.py --model Hy3`（`set_model()` 已实现并实测）。
  模型选择是**持久的**（切一次后续新任务都沿用）。
- **自动确认授权弹框**（`--confirm 连接|暂不`）：某些专家召唤后会弹「是否连接 XX？」授权框。
  脚本会尝试点「连接」。**`Expert_lighthouse`（+100）已实测可全自动打通**（2026-09-14 修正，见下）：
  正确链路 = 搜索框过滤「轻量云」→ 召唤`腾讯轻量云专家` → 对话发「查我的轻量云实例列表」→
  专家弹「是否连接 Lighthouse 运维?」→ 点「**连接**」→ 连接器计数触发 `0/1 → 1/1`。
  计数触发点就是**「连接连接器」这个动作本身**（账号已绑腾讯云时连接即计数）。
  ⚠️ 旧结论（"纯自动化搞不定"）已作废——那是搜索匹配误命中别的专家导致的假失败。
- **黑猫彩蛋 black_cat（v6.2.0 新增自动推进）**：规则——连续 **3 天**在 **23:00–8:00** 用
  **GLM-5.2** 发起对话解锁（0 积分，纯彩蛋）。实测用 ACP 新建会话 + `set_model glm-5.2` + 发一条消息，
  服务端把 black_cat 从 `0/3` 推进到 `1/3`，证明 ACP 的 GLM-5.2 对话计入彩蛋判定。
  新增 `black_cat.py`：带时间窗口守卫，非夜间自动跳过；可由每小时定时任务调用，连续 3 晚自然完成。
  用法：`python scripts/black_cat.py`（强制：`--force`）。
- 完成 `create_canvas` 的确定流程：点「新建任务」→ 点「设计创意」→ 点输入框并 `keyboard.type(prompt)` → 点发送
- **完成 `template_5` 的确定流程（关键坑！）**：点「新建任务」→ 「日常办公」→ 点模板 pill（插入 chip）
  → **必须再 `keyboard.type` 一段真实文本**（只插 chip 时发送键点了完全没反应！）
  → 点发送。每次换一个**不同**模板（任务要求 5 个不同）。
- 模板池：初始 文档处理/金融服务/数据分析及可视化；**点过一次后整行展开**，多出
  个人工作台/幻灯片/深度研究/视频生成/产品管理/最新新闻/帮我写作/日常翻译/生活小知识/工作技巧/旅游攻略。
  展开区的 pill Playwright 视为不可见 → 用 **JS `scrollIntoView()` + `el.click()`**。
- 验证方式：发送前后 `任务 (N)` 计数变化

## 环境坑
- 本机常有 `http_proxy=127.0.0.1:10808` 且代理离线，需 `urllib.request.ProxyHandler({})` 绕过
- 日志 message 是 JSON 数组、内部引号转义为 `\"` → 匹配 `currentUserId` 要用
  `currentUserId[^0-9a-f]{0,20}(<uuid>)`
- `update automation` 时**不传 rrule 会被重置**（改成默认每天一次），必须每次带上
- `FREQ=HOURLY` 在本调度器 nextRunAt 解析异常 → 用 `FREQ=DAILY` + 全天 BYHOUR 列表

## 能力边界（全路径探查结论）
- ✅ 可自动：签到、接任务、领奖、派猫/收猫、抽奖（有次数时）、**对话类任务（ACP）**、
  **`create_canvas`（CDP，+300）**、**`template_5`（CDP，+100）**、
  **`playbook_prompt`（CDP，+100，⚠️ 按账号不一定计数，见下）**
  （`Expert_lighthouse` 已于 5.5.6 失效，见下）
- 🔶 `expert_5`（召唤 5 位**不同**专家）—— 流程：侧栏「专家·技能·连接器」→ 子 tab「专家」→
  **点专家卡片 → 进详情点「召唤 XX」→ 发消息**。
  ⚠️ **关键 DOM 契约（v6.2.0 修正）**：专家**卡片本身没有「召唤」按钮**，召唤键只在详情里；
  且专家列表是**虚拟滚动**，直接按文本等会超时，须先滚动加载。
  ⚠️ **v6.4.0 重大修正（2026-09-14 实测）**：
  - **`--names` 按名字匹配已不可靠**：5.5.6 专家库**按账号重构且列表动态刷新**
    （兰进城=「企鹅教师助手」教育类；羊羊=通用类：采购库存/心理咨询/AI落地/个人IP…），
    硬编码 `DEFAULT_POOL` 名字常匹配不到 → 直接 `nf`。
  - **"小时级滞后"是误判**：羊羊 2/5 历经 1h40m 纹丝不动。dump 侧栏对话列表后发现
    ——之前那几次召唤**根本没创建出对话**，是召唤失败，不是滞后。
  - ✅ **改用 `--any N`**：按**可见卡片索引顺序**召唤 N 个专家，**不依赖专家名**，跨账号通用。
    每次召唤后重进面板重取卡片（列表会刷新），内部用 used 集合去重。
    ```bash
    python cdp_experts.py --any 3 --no-dialog    # 召唤 3 个可见专家
    ```
  - 校验方式：跑完看输出里的 `任务数 A->B` 是否递增；递增才说明对话真的建了。
- ❌ Web 版无这些模块：`skills/templates/canvas/playbook/experts/automation/library` **全部 404**，
  Web 仅有 首页 / 成长中心 / 只读 chat
- ❌ 桌面 app.asar 加密；但 `app.asar.unpacked/cli/dist/codebuddy.js`（21.6MB）未加密，仅含 CLI 端点

## 客户端版本与任务解锁（2026-09-14）
部分成长任务依赖**较新客户端版本**才有对应功能/埋点：
- `Hp_Appearance`（和平精英主题）：需 **5.5.3+**。5.2.6 用户菜单虽有浅色/深色切换、**切换真的生效**
  （`html.class` light→dark、body bg 变），但服务端**无事件埋点** → harvest 恒 `0/1`。
- `Library_read`：5.2.6 已穷举 **6 条路径**（乐享面板预览/iframe 滚动/对话引用 KB/本地 .md 阅读器/`@`提及/OAuth 本身）
  全不计数，疑同样需更高版本才有"读文档"埋点。

**取最新安装包直链（可复用）**——官网 SPA 的下载链接是客户端动态从官方接口拉的（历史版本页只归档到 5.1.x，不含最新）：
```bash
GET https://www.workbuddy.cn/v2/update?platform=workbuddy-win32-x64-user
# → {"url":"https://download.codebuddy.cn/workbuddy/saas/win32-x64-user/WorkBuddy-win32-x64-user-<ver>-<hash>.exe", ...}
# Mac: platform=workbuddy-darwin-arm64-user / -x64-user
curl -L -o WorkBuddy-<ver>.exe "<url>"      # 约 507 MB；只下载、不安装
```

> ⚠️ **铁律**：绝不主动 `taskkill`/重启用户的 WorkBuddy。安装由**用户本人双击 exe**完成；
> 需要 CDP 9222 时也由用户双击 `start_workbuddy_debug.bat`，脚本只轮询端口，不代拉进程。
> 升级到 5.5.3+ 后，用 `cdp_appearance.py`（切主题）+ `cdp_library_read.py`（开文档）重测这两个任务是否解锁。

## 用法
```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
# 以下用 $HOME（= C:/Users/<你>），换电脑无需改动；也等价于 setup_env.bat 装好的 venv 路径
PY="$HOME/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
SK="$HOME/.workbuddy/skills/workbuddy-growth-plan-autoclaim/scripts"

"$PY" "$SK/harvest.py"              # 多账号：签到+接任务+领奖+派猫/收猫
"$PY" "$SK/harvest.py" --list       # 只读体检
"$PY" "$SK/harvest.py" --travel     # 只派猫/收猫
"$PY" "$SK/harvest.py" --only 8362  # 只处理 uid/昵称/手机 含该串的账号

"$PY" "$SK/acp_autofarm.py"         # ACP 只读：列出端口/当前登录账号/可自动完成的任务
"$PY" "$SK/acp_autofarm.py" --run   # ACP 执行：补做对话类任务
"$PY" "$SK/acp_autofarm.py" --probe # 只测 ACP 端口可用性

"$PY" "$SK/black_cat.py"            # 黑猫彩蛋：夜间 GLM-5.2 对话推进（带时间守卫，可 --force）
"$PY" "$SK/cdp_autofarm.py" --check          # 检查 CDP（需 9222）
"$PY" "$SK/cdp_autofarm.py" --canvas         # 自动完成 create_canvas（+300）
"$PY" "$SK/cdp_autofarm.py" --templates 4    # 自动使用 4 个不同模板（template_5）
"$PY" "$SK/cdp_autofarm.py" --explore out.json --canvas --templates 3 --wait 150
                                             # 一键：等端口+探查+画布+模板
"$PY" "$SK/cdp_experts.py" --any 3 --no-dialog
                                             # 召唤 3 个可见专家（expert_5）；跨账号通用，勿用 --names（名字按账号变化）
"$PY" "$SK/cdp_playbook.py"                  # playbook_prompt（+100）：灵感做同款（可 --index N）
"$PY" "$SK/cdp_lighthouse.py"                # Expert_lighthouse（+100）：搜轻量云→召唤→点连接
"$PY" "$SK/cdp_appearance.py" --set dark     # 切深色（--set light 切回）；用于重测 Hp_Appearance
"$PY" "$SK/confirm_pending.py"               # 清理「待确认」悬停会话
"$PY" "$SK/wb_cdp.py" --list                 # CDP 诊断
```

**换电脑一键装环境**：双击 `setup_env.bat`（自动建 venv + 装 playwright + chromium）
**一键全自动**（双击即用）：
- `start_workbuddy_debug.bat` — 仅带调试端口重启客户端
- `run_autofarm.bat` — 重启客户端 → 等 CDP → 自动画布+模板 → 多账号收割
  （路径已用 `%USERPROFILE%` 自适应用户名，换电脑直接可用）

## 换账号说明
- **HTTP 部分**（签到/领奖/派猫）：**无需任何操作**，脚本读切换器存档里所有账号
- **ACP 部分**（含 black_cat）：只对「客户端当前登录的账号」生效 —— **你切到哪个账号，下一个定时周期它自动补做**
- **CDP 部分**（画布/模板/召唤专家/灵感做同款/轻量云连接）：同上，只对当前登录账号生效
- 新增账号：在账号切换器里登录一次，脚本自动发现
- **切换顺序建议**：每个账号 → 双击 `start_workbuddy_debug.bat`(开 9222) → 跑 `cdp_autofarm.py`(画布+模板)
  → `cdp_playbook.py`(灵感) → `cdp_lighthouse.py`(轻量云) → `cdp_experts.py`(召唤专家) → `harvest.py`(领奖)

## 定时任务
- `WorkBuddy 多账号积分自动收割（签到+接任务+领奖+派猫+ACP自动完成+黑猫）`（`automation-1789213157881`）
  `FREQ=DAILY;BYHOUR=0..23;BYMINUTE=5` → 每小时依次：
  1. `black_cat.py`（非夜间窗口自动跳过，连续 3 晚完成彩蛋）
  2. `acp_autofarm.py --run`（补做对话类任务）
  3. `harvest.py`（领奖 + 派猫/收猫，并兜底计入滞后的 expert_5 等）
- 换电脑后重建 automation，prompt 里写明上面三条命令，**rrule 每次更新都要带上**（不传会被重置）

## 推荐工作模式
**你什么都不用做**。脚本每小时自动：黑猫（仅夜间）→ 补做对话类任务 → 领奖 → 派猫/收猫。
CDP 类（画布/模板/召唤专家/**灵感做同款**/**轻量云连接**）：双击 `run_autofarm.bat` 一次（画布+模板），
再依次跑 `cdp_playbook.py` / `cdp_lighthouse.py` / `cdp_experts.py`，即可完成当前账号的全部可做 UI 任务；
`expert_5` 跑完先看输出里 `任务数 A->B` 是否递增（递增=对话真创建了），再由定时任务兜底领取。
**8 个"无自动化"任务的实际结论（2026-09-14 CDP 实测，详见 `AUTOCOMPLETE.md` 第八节）**：
- ✅ **新增可自动化（2 个）**：
  - `playbook_prompt`：hover「更多」→「灵感」→点卡片→「做同款」→发送（脚本 `cdp_playbook.py`，兰进城实测领取 +100c）
    ⚠️ **按账号表现不一致（2026-09-14 实测）**：羊羊上对话**确实已创建且助手完成**
    （"已处理 10m36s"+含构建完成），但服务端 `progress` 始终 `{current:0,target:1}`，
    POST claim 返回 **HTTP 400 `task not completed`**。→ 非必成，跑完务必用 `--list` 复核，别默认算成功。
- ❌ `Expert_lighthouse`：**5.5.6 起永久不可自动**（原路线失效）
  - 根因：5.5.6 **专家库重构**，「腾讯轻量云专家」**已下架**，全部专家换成教育/通用类。
    搜索「轻量云 / 腾讯云 / Lighthouse」均返回 **0 个专家**，原 `cdp_lighthouse.py` 无目标可点。
  - （5.2.6 老路线记录：搜索框过滤「轻量云」→点 `腾讯轻量云专家`→召唤→发「查我的轻量云实例列表」
    →弹「是否连接 Lighthouse 运维?」→点「连接」→计数 0/1→1/1。仅对旧版本/该专家仍存在的账号有效）
- ⚠️ 定义未确认：`Expert_team_use_3`（"专家团"无明确可召唤目标）
- ❌ **实测不可自动化（事件未埋点）**：`Library_read`（已穷举 **6 条路径**：乐享面板单/双击打开、iframe 内滚动、对话引用 KB、本地 .md 内置阅读器、`@` 提及文件、OAuth 授权本身 —— 全部不计数）、
  `Hp_Appearance`（用户菜单 `button.user-menu-theme-option` 浅色/深色**切换真的生效**但 harvest 仍 0/1；设置页无「外观/主题」项。详见 `cdp_appearance.py`）
- ❌ 当前版本无入口（5.5.6 最终确认）：`Buddy_App` / `Buddy_App_QQ`
  - 实测：点顶部「发现应用」(`wb-button` x≈158,y≈42) → 进应用市场 → 点「企鹅教师助手」/
    「构建打工人小账本」等应用，harvest 仍 `0/1`。需桌面深链 `workbuddy://home?openBuddySwitcher`，
    网页/CDP 无入口。（某账号显示 claimed 属历史遗留/手动完成，非 CDP 攻克）
- ❌ 绝不自动：`Expert_Philanthropy`（真实捐款，涉及真实支付）
- `black_cat` 已可脚本化（只需客户端在夜间开着并触发定时任务）。

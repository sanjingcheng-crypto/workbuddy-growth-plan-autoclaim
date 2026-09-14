# 成长计划 · 自动完成版 架构设计（workbuddy-growth-plan-autoclaim）

> 目标：在「选项 2」下，做一个能真正把成长计划任务「跑完并领奖」的自动化版本，
> 而不只是领「已手动完成」的奖励（growth_claim.py 只做后者）。

## 一、已验证的事实（A 路线逆向结论，实测通过）

### 1. growth 接口契约
- **baseURL**：`https://copilot.tencent.com`（www.workbuddy.cn 同网关也通）
- **必带头**（缺 `X-Client-Platform` 直接返回 `404 page not found`，这是早期一直 404 的根因）：
  ```
  Authorization: Bearer <桌面 accessToken>
  X-User-Id: <JWT.sub>
  X-Domain: copilot.tencent.com
  X-Client-Platform: web
  Content-Type: application/json
  ```
- **端点**：
  - `GET  /v2/activity/growth/tasks` → 任务清单 + 每个任务状态（task_code / accept_status / progress{current,target} / reward_credit / reward_energy / locked）
  - `POST /v2/activity/growth/tasks/{task_code}/claim` → 领奖（未完成返回 `400 task not completed`；已领返回 `already_claimed:true credit:0`）
  - `POST /v2/activity/growth/tasks/accept` → 去完成（body 字段尚未 100% 确认，曾返回 `invalid request`，疑似 `{code}` 或 `{task_code}`）
  - `GET  /v2/activity/growth/profile` → 总进度/等级/积分
- **关键机制**：前端**只有 accept / claim 两个接口，没有「完成/上报」接口**。任务完成态由**服务端真实事件**判定（对话、建画布、用模板、召唤专家、装技能、设自动化、读资料库等）。

### 2. 两个铁律
1. **必须先 `accept`（网页点「去完成」）后端才为该任务计数** —— 当前 16 个待完成任务全是 `not_accepted`，progress 为 null。
2. **纯 API 无法伪造完成** —— 之前用 `automation_update` 建了真实本地自动化任务，`automation_1` 仍不被标记完成（progress=null）。完成事件来自云端业务服务，不是本地 db。

## 二、自动完成核心思路
> 既然完成态依赖「真实客户端事件」，那么「无头自动完成」= **直接调用客户端用的云端业务 API 触发该事件**（聊天 API、画布 API、模板 API、专家 API、技能 API、自动化 API、资料库 API…），
> 比 Playwright 点按钮更稳、锁屏也能跑，且天然产生真实后端事件（不会被判定为伪造上报）。

## 三、18 个任务分类（按「触发方式」）

| 任务 | 标题 | jump_url | 触发方式 | 自动化可行性 |
|---|---|---|---|---|
| create_canvas | 设计创意模式 | workbuddy://chat | 建 1 个画布 | 网页 Playwright / 画布 API |
| playbook_prompt | 探索灵感 | workbuddy://playbook | 灵感做同款 1 次 | 网页 Playwright / 灵感 API |
| RichMeow_Chat | 桌面端对话1次 | workbuddy://chat | **已完成 claimed** | — |
| Library_read | 资料库 | workbuddy://library | 读完 1 篇文档 | **实测不可自动化（5.2.6 阅读事件不触发，见 §8）** |
| Expert_lighthouse | 轻量云专家 | workbuddy://expert | 召唤+对话+外部 Lighthouse 跳转 | 受限（外部活动页） |
| Expert_Philanthropy | 公益专家 | workbuddy://expert | 召唤+**捐款**（花钱） | 不建议自动（涉及真实支付） |
| Hp_Appearance | 和平精英主题 | workbuddy://settings/appearance | 切主题（需 5.5.3+） | 桌面特有，网页难覆盖 |
| Buddy_App | 发现应用 | workbuddy://home?openBuddySwitcher | 进任意 Buddy 应用 | 桌面特有 |
| Buddy_App_QQ | 企鹅教师助手 | workbuddy://home?templateId=cb_… | 进指定模板应用（限时） | 桌面特有 |
| Model_chat_GLM5.2 | GLM-5.2 模型 | workbuddy://chat | 用该模型对话 1 次 | 网页 Playwright / 聊天 API 指定模型 |
| black_cat | 夜猫子 | workbuddy://chat | 23-8 点 GLM-5.2 对话，累计 3 天 | 时段限定，需跨 3 天 |
| Expert_team_use_3 | 召唤3次专家团 | workbuddy://experts | 召唤 3 个不同专家团 | 网页 Playwright / 专家团 API |
| first_buddy | 领取 Buddy | workbuddy://chat | **已完成 claimed** | — |
| chat_5 | 和 AI 聊天 5 次 | workbuddy://chat | 对话累计 5 次 | 网页 Playwright / 聊天 API |
| skill_1 | 尝鲜热门技能 | workbuddy://skills | 装 1 技能并用 | 网页 Playwright / 技能 API |
| expert_5 | 召唤 5 次专家 | workbuddy://expert | 召唤 5 位不同专家并对话 | 网页 Playwright / 专家 API |
| template_5 | 使用 5 个模板 | workbuddy://templates | 用 5 个不同模板对话 | 网页 Playwright / 模板 API |
| automation_1 | 设置自动化 | workbuddy://automation | 设 1 个云端定时任务 | 网页 Playwright / 云端自动化 API |

### 可行性分级
- **P0 网页可全自动化**（覆盖约 9 个，约 900 积分 + 45 能量）：
  `chat_5, Model_chat_GLM5.2, template_5, skill_1, create_canvas, playbook_prompt, expert_5, Expert_team_use_3, automation_1`
- **P1 需特定条件**（部分可自动）：
  `black_cat`（需 23:00–08:00 触发、跨 3 天）、`Library_read`（需真实阅读行为）
- **P2 桌面/外部特有，自动化难/不建议**：
  `Hp_Appearance, Buddy_App, Buddy_App_QQ`（桌面深链）、`Expert_lighthouse`（外部活动页）、`Expert_Philanthropy`（真实捐款，不建议自动）

## 四、技术方案（两阶段）

### 阶段 A：accept + 轮询 + claim（已具备）
见 `growth_claim.py`：拉取 tasks → 找出 `accept_status=claimed & has_reward & 未领` → 逐个 claim。
补充：`accept` 需在跑任务前批量调用（先 accept 再触发事件，否则不计分）。

### 阶段 B：触发真实业务事件（选项 2 主体，待 POC）
两种实现，二选一或结合：

**B1（推荐，先验证）：Playwright 驱动网页端 www.workbuddy.cn**
- 打开网页，把桌面 `accessToken` 注入 `sessionStorage`（web 端读 `sessionStorage['growth-center-token']` 之类的 key，需抓包确认；如不通则走 cookie 登录）
- 按任务清单依次在网页做真实动作，并用 Playwright 的 `page.on('request')` 拦截，精确记录每个动作对应的业务 API（聊天 / 画布 / 模板 / 专家 / 技能 / 自动化）
- 每个动作后轮询 `GET /v2/activity/growth/tasks` 看 `progress.current` 是否 +1
- 优点：最稳、能产生真实后端事件、同时白盒拿到 API 契约
- 缺点：依赖 chromium 下载、需网页端登录态

**B2（B1 收敛后）：纯 API 无头触发**
- 用 B1 抓到的业务 API 契约，直接 urllib/requests 调，不再依赖浏览器
- 比 UI 点按钮更脆？不——反而更稳、锁屏可跑、可定时
- 这是最终形态，但必须以 B1 抓到的确切端点为前提

## 五、风控（必须遵守）
- 官方反刷量：同一账号每任务仅 1 次，刷量/多号套利会回收奖励 + 限号。本方案只「帮用户把本就会做的动作自动跑完」，不伪造、不刷量。
- `Expert_Philanthropy` 涉及真实支付，默认跳过、绝不自动捐款。
- `black_cat` 需严格在 23:00–08:00 触发，跨 3 个自然日。
- 桌面深链类（Hp_Appearance / Buddy_App / Buddy_App_QQ）若网页端无对应入口，标记为「需手动」，不强行自动化。

## 六、下一步（本会话）
1. 等 Playwright + chromium 安装完成（后台 task MUFumN）。
2. 写 `growth_autocomplete.py`：用 Playwright 打开网页 → accept 全部可自动化任务 → 依次触发真实动作 → 轮询进度 → claim。
3. 先以 `chat_5` 做最小 POC：验证「网页真实对话能否让 progress 从 0→5、再 claim 领 100 积分」。
4. POC 通过后再扩展到 P0 全部任务。

---

## 八、CDP 方案实测结论（2026-09-13/14，WorkBuddy 5.2.6，账号 绵羊～）

> 本节是**用 CDP 直连桌面客户端**（而非网页端 Playwright）对上述 8 个任务的实际探针结论。
> 结论与第三节（基于网页端的推演）**有出入**——CDP 能碰到网页端碰不到的桌面 UI。

| 任务 | CDP 实测结论 | 自动化可行性 |
|---|---|---|
| `playbook_prompt` | ✅ **已打通并领取 +100c**。链路：hover 侧栏「更多」(103,263) → 点「灵感」(333,447) → 点灵感卡片 → 弹 `dc-detail-overlay` → 点「做同款」→ 输入框(`div[class*=_editable_]`)自动预填提示词 → 点最右 `div[class*="_large_"]` 发送 | ✅ 可全自动 |
| `Expert_team_use_3` | 搜「专家团」返回 4 位（描述匹配，名字不含"团"）；「我的专家」里的"XX专家团/XX团队"是**已召唤历史**，非可召唤目标；召唤「深度研究团队」失败 | ⚠️ 定义未确认 |
| `Library_read` | **6 条路径全实证都不计数**：①乐享面板预览（真实 locator 点行/双击，iframe 已加载）②乐享 iframe 内滚动 ③对话式引用 KB（助手确认检索 `lexiang-knowledge-base` 但 0/1）④「我的文件」本地 `.md` 内置阅读器打开 ⑤对话 `@` 提及文件（无选择器弹出）⑥ima/乐享 OAuth 授权动作本身。OAuth 阻塞已解除（乐享已授权、7 篇示例文档已列出），但 5.2.6 客户端**无任何可自动化交互能触发该事件** | ❌ 5.2.6 实测不可自动化 |
| `Expert_lighthouse` | ✅ **已打通并领取 +100c**（2026-09-14 实跑，账号 绵羊～）。搜「轻量云」过滤→`腾讯轻量云专家`→召唤→发「查我的轻量云实例列表」→专家弹「是否连接 Lighthouse 运维?」→点「连接」→**连接器计数触发 0/1→1/1** | ✅ 可全自动（需账号已绑腾讯云，连接即计数） |
| `Expert_Philanthropy` | 搜「公益」有多个公益专家；任务 **progress=null**；需真实捐款 | ❌ 绝不自动（真实支付） |
| `Hp_Appearance` | 设置页左侧导航**无「外观/主题」**（仅"个性化"=风格语调/欢迎语/自定义指令）；用户菜单项 `div.user-menu-item`（容器带 `--disabled` 但内部按钮可点）含 `button.user-menu-theme-option` **浅色(172,517) / 深色(226,517)**。**实测切换成功**（`html.class` `light cb-light`→`dark cb-dark`、body bg `255,255,255`→`24,24,24`、ACTIVE 移位）**但 harvest 始终 0/1**（切深等12s + 切回浅等8s 均不计数），已恢复浅色界面 | ❌ 5.2.6 事件未埋点（真实功能需 5.5.3+ 主题皮肤）；脚本 `cdp_appearance.py` |
| `Buddy_App` | 首页无「发现应用/应用切换」入口；深链 `workbuddy://home?openBuddySwitcher=true` 无法触发 | ❌ 当前版本无入口 |
| `Buddy_App_QQ` | 同上 | ❌ 当前版本无入口 |

### 新增 DOM 契约（5.2.6 实测）

**专家卡片（重要，本次修了 bug）**：
```
div.ec-card-main              ← 卡片根，点击目标
  ├─ .ec-card-head
  ├─ .ec-card-body
  │    ├─ .ec-card-title-row   （专家名）
  │    └─ .ec-card-subtitle
  ├─ .ec-card-desc
  └─ .ec-card-tags
```
> ⚠️ 旧选择器 `div[class*=card]` 会**先命中 `ec-card-head` 等子元素**，点子元素不触发卡片点击，
> 导致召唤**静默失败**（`card not found` / `sent=False`）。**必须优先 `div.ec-card-main`**。
> `cdp_experts.py` 的 `JS_CARD` 已按此修正。

**设置 / 用户菜单**：
- 用户区点击 `(130,686)` → 弹出用户菜单（体验版 / 积分余额 / 成长计划 / 设置 / 外观 / 帮助与反馈）
- 「设置」`(154,473)` → `#settings/settings`；左侧导航：账户管理/智能体邮箱/系统设置/智能体设置/快捷键/记忆/模型/助理设置/个性化/数据管理/安全中心/帮助与反馈
- 「个性化」`(231,371)` → `#settings/personalization`
- 用户区点击同时会弹出**成长中心面板**（积分余额 / 每日可领 / 连登 / Buddy加油站）

**侧栏「更多」**：hover `(103,263)` 展开 `wb-dropdown__label` 菜单：
我的文件 / 腾讯文档 / ima知识库 / 乐享知识库 / 灵感（灵感 `(333,447)`）

**灵感卡片**：`dc-playbook-grid` / `dc-card-cover|info|title-row|footer`；
点卡片弹 `dc-detail-overlay.is-open`（含「做同款」按钮）

### hash 路由（重要限制）
存在 `#settings/settings`、`#settings/personalization`、`#playbook`、`#automation` 等 hash 路由，
但 **直接 `location.hash = 'xxx'` 不触发 React 渲染**（路由由点击驱动）。
→ **不能**用改 hash 做通用跳转，必须点 UI。

### 渲染进程 Electron API
```js
window.workbuddyDesktop.invoke() / .app.consumePendingOpenUrls()
window.workbuddyDesktop.opener.openUrl(url)   // ❌ 不支持 workbuddy://（Unsupported external URL）
window.__workbuddyDeepLinkBuffer = { url, token, lastUpdatedAt, listeners }
```

### 环境坑
venv 混入 `_greenlet.cp314-win_amd64.pyd`（3.14 编译）而 venv 是 3.13 →
Playwright 报 `No module named 'greenlet._greenlet'`。
修复：`pip install --force-reinstall --no-cache-dir greenlet`。
**始终用 venv 的 python**（`...\envs\default\Scripts\python.exe`）跑 pip。

---

## 九、客户端版本升级路径（解锁 5.5.3+ 任务，2026-09-14）

5.2.6 下 `Hp_Appearance` / `Library_read` 卡在"功能有、事件未埋点"。要真正解锁需升级客户端到 **5.5.3+**。

**取最新安装包直链**（官网 SPA 的下载链接是动态拉的；历史版本页只归档到 5.1.x）：
```bash
curl -s "https://www.workbuddy.cn/v2/update?platform=workbuddy-win32-x64-user"
# → {"url":"https://download.codebuddy.cn/workbuddy/saas/win32-x64-user/WorkBuddy-win32-x64-user-<ver>-<hash>.exe", ...}
# Mac: platform=workbuddy-darwin-arm64-user（或 -x64-user）
```
实测返回最新稳定版 **5.5.6.38337834**（`WorkBuddy-win32-x64-user-5.5.6.38337834-5f969292.exe`，507 MB）。
**只下载、不安装**（约 507 MB）；安装由用户本人双击 exe 完成 —— 遵守"绝不主动重启 WorkBuddy"铁律。

**升级后重测清单**：
- `cdp_appearance.py --set dark|light` → 复查 `Hp_Appearance` 是否 `0/1→1/1`
- `cdp_library_read.py` → 复查 `Library_read` 是否计数
- 若仍不计数，则确认为"需真实业务行为"，非 UI 可自动化。

## 七、登录机制实测更正（重要）
- 网页端 www.workbuddy.cn **不能**靠注入 sessionStorage 无头登录：`CopilotLoginInfo` 只存 `{time,loginType}`，**不含 token**；登录态在 **Keycloak(copilot realm) Oauth 的 httpOnly cookie**。
- 点「登录」跳 `/login/?platform=website&...&product=workbuddy`，后端 `/auth/realms/copilot/protocol/openid-connect/...`。**必须用户在弹窗扫码/验证码登录一次**，Playwright 才能拿到 cookie。
- 结论：选项 2 第一次运行需要**用户手动配合登录一次**（headless=False 开窗口扫码）；之后 cookie 存 `.wb_cookies.json` 可复用（Keycloak session 有时效，过期需重登）。
- POC 脚本 `poc_chat5.py`：开浏览器→用户登录→进 /chat 发 5 条真实消息→拦截网络抓取聊天 API 端点（copilot.tencent.com 网关，与 growth 同源）。抓到端点后即可收敛为「纯 API 无头触发」（B2），锁屏可跑。

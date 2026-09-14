# workbuddy-growth-plan-autoclaim

WorkBuddy 成长中心（成长计划）积分全自动收割 Skill。

- **多账号**：签到 / 接任务 / 领奖 / 派猫猫旅行（纯 HTTP，无需客户端）
- **对话类任务**（Model_chat_GLM5.2 / chat_5 等）：通过本机 ACP 自动完成
- **UI 类任务**（create_canvas +300 / template_5 +100 / expert_5 召唤专家 /
  playbook_prompt 灵感做同款 +100 / Expert_lighthouse 轻量云连接 +100）：通过 CDP 接管桌面客户端
- **黑猫彩蛋**（black_cat）：连续 3 晚 23:00–8:00 用 GLM-5.2 对话，脚本化自动推进
- 自包含、可移植：**换账号 / 换电脑都能直接用**

> 完整契约、DOM 选择器、账号发现机制、模型价目表见 [`SKILL.md`](./SKILL.md)。

## 安装（换电脑 / 新环境）

1. 克隆本仓库到 WorkBuddy 的 skill 目录：

   ```bash
   git clone https://github.com/sanjingcheng-crypto/workbuddy-growth-plan-autoclaim \
     "$HOME/.workbuddy/skills/workbuddy-growth-plan-autoclaim"
   ```

2. **双击 `setup_env.bat`** —— 一键建好受管 Python venv + 安装 `playwright` / `urllib3` + `playwright install chromium`（路径全部 `%USERPROFILE%` 自适应，零手动改路径）。

3. 在 WorkBuddy 桌面客户端里，用「账号切换器」登录一次各账号
   → 脚本自动发现 `%APPDATA%\WorkBuddyAccountSwitcher\accounts\account_*.json`。

4. 重建每小时定时任务（命令与 rrule 见 `SKILL.md` 文末）即可无人值守运行。

## 手动使用

```bash
PY="$HOME/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
SK="$HOME/.workbuddy/skills/workbuddy-growth-plan-autoclaim/scripts"

$PY "$SK/harvest.py" --list          # 列出所有账号与任务进度
$PY "$SK/acp_autofarm.py" --run      # ACP 补做对话类任务（需客户端在跑）
$PY "$SK/black_cat.py"               # 黑猫彩蛋（带 23:00-8:00 时间守卫）
```

UI 类（画布/模板/召唤专家）：双击 `run_autofarm.bat`（需客户端带 `--remote-debugging-port=9222` 启动）。

## 限制

- ACP / CDP 类任务只对客户端**当前登录账号**生效；HTTP 部分（签到/领奖/派猫）多账号全覆盖。
- 仍依赖人工的项：`Expert_Philanthropy`（真实捐款，绝不自动）。
- 当前版本（5.2.6）实测**不可自动**（事件未埋点/无入口，需 5.5.3+）：`Library_read`、`Hp_Appearance`、
  `Buddy_App`、`Buddy_App_QQ`；`Expert_team_use_3` 定义未确认。详见 `AUTOCOMPLETE.md` §8。

## 目录结构

```
SKILL.md              技能定义（主文档，含全部契约）
AUTOCOMPLETE.md       参数补全说明
README.md             本文件
setup_env.bat         新环境一键装 Python/playwright/chromium
run_autofarm.bat      一键：重启客户端→CDP→画布+模板→多账号收割
start_workbuddy_debug.bat  仅带调试端口重启客户端
scripts/
  harvest.py          多账号签到/接任务/领奖/派猫
  acp_autofarm.py     ACP 对话类任务
  cdp_autofarm.py     CDP 画布/模板
  cdp_experts.py      CDP 召唤专家（expert_5）
  cdp_playbook.py     CDP「灵感·做同款」（playbook_prompt，2026-09-14 新增）
  cdp_lighthouse.py   CDP「轻量云专家连接」（Expert_lighthouse，2026-09-14 新增）
  cdp_appearance.py   CDP 切浅色/深色主题（重测 Hp_Appearance 用，2026-09-14 新增）
  cdp_library_read.py CDP 打开知识库/本地文档（重测 Library_read 用，2026-09-14 新增）
  cdp_expert_dialog.py 专家对话检查
  confirm_pending.py  清理「待确认」悬停会话（模板/灵感跑完后用）
  do_tpl_pairs.py     跨场景模板补齐（template_5 收尾）
  black_cat.py        黑猫彩蛋夜间推进
  claim_api.py        底层签到/领奖 API
  growth_claim.py     单账号成长领奖
  wb_cdp.py           CDP 诊断（开发用）
```

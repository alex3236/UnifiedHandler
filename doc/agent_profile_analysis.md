**中文** | [`English`](agent_profile_analysis_en.md)

# 借助 AI Agent 分析和编写 Profile

如果手动排查耗时过长，可以让 AI agent 帮你分析服务端日志，诊断 UnifiedHandler 的问题，并给出建议。

## 准备工作

为了获得一份干净的日志供 AI 分析，建议单独跑一次排查流程：

- **关闭 MCDR**（`stop` 或 ^C）

- 在 MCDR 实例根目录的 `config.yml` 中启用日志记录：
  
  ```yaml
  write_server_output_to_log_file: true
  ```

- 在 `config/unified_handler/config.yml` 中设置 `debug: true`

- **启动 MCDR**，然后按照 [Handler 工作状态验证指南](handler_troubleshooting.md) 逐一完成所有测试（`!!MCDR`、普通玩家发言、带前缀玩家发言等）。**不要进行正常游戏**——仅做排查指南中的测试，完成后即关闭 MCDR

这样 `logs/MCDR.log` 中只有这一轮测试的输出。然后让 agent 进入你的 MCDR 实例目录，将以下提示词发给 agent：

```text
You are troubleshooting a **MCDR (MCDReforged)** handler issue. The server uses the **UnifiedHandler** plugin (YAML-profile-driven log parsing). Reply in **Chinese**.

Repos: MCDR https://github.com/MCDReforged/MCDReforged | UnifiedHandler https://github.com/alex3236/UnifiedHandler

**Files to read**:
- `logs/MCDR.log` — tail 1000 lines; look for lines containing `[unified_handler]` (plugin status and debug output). Debug lines appear in the format `[unified_handler]: <event>: ...` (e.g. `startup_done: matched (base)`, `player_msg: "name" "msg" (base)`)
- `config.yml` — MCDR main config (rcon enabled? handler type?)
- `config/unified_handler/config.yml` — UnifiedHandler settings (base handler, features)
- `config/unified_handler/profile.schema.json` — full profile field reference
- `config/unified_handler/profiles/` — list directories, then read enabled feature YAML files
- Optionally `server.properties` — check `enable-rcon` if rcon matters

**Lifecycle report** (printed when MCDR stops):
- Critical: `server_version` (determines tellraw format), `startup_done`
- `server_address` and `server_stopping` are low priority
- `rcon_started` only matters if BOTH MCDR config has `rcon: true` AND `server.properties` has `enable-rcon=true` — otherwise ignore it

**Player detection**: normal chat should produce `player_msg: "name" "msg" (base)`. If players with title/team prefixes cannot use `!!MCDR` commands, the parser is not extracting their name from prefixed log lines.

**Give analysis and proceed**:
- If an existing feature can fix the issue: tell the user which feature to enable, and ask whether they need help completing the config change.
- If writing a new profile can fix it: tell the user what kind (feature or base), and ask whether they want you to write it now.
- If a new profile cannot fix it either: tell the user why, and explain whether this needs to be reported to the UnifiedHandler author or is a different kind of issue.
- If you need more information before analyzing: ask the user to provide it first.
```

agent 会分析日志和配置，给出建议。例如：

https://github.com/user-attachments/assets/e977baa4-3e23-408d-9183-2bb9256ae66e


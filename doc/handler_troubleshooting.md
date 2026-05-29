**中文** | [`English`](handler_troubleshooting_en.md)

# Handler 工作状态验证指南

配置好 UnifiedHandler 之后，建议跑一遍本文档的检查流程来确认一切正常。如果发现任何问题，本文档也覆盖了对应的解决方法。

## 0. 开始之前：Debug 时机

**重要**：如果希望看到完整的生命周期报告，必须在启动 MCDR **之前**就开启 debug 模式，并且在整个运行期间**不要重载此插件**（`!!uh reload` 会重置追踪数据）。

在 `config/unified_handler/config.yml` 中设置：

```yaml
debug: true
```

然后启动 MCDR。

## 1. 启动时确认

启动服务器，观察 MCDR 日志中是否有这些行：

```
[unified_handler]: 配置文件已加载
[unified_handler]: 基础处理器：forge_handler    （或 vanilla_handler / bukkit_handler 等）
[unified_handler]: 功能特性：chat_prefixes       （或你启用的 feature 列表）
[unified_handler]: UnifiedHandler 注册成功
```

如果注册成功但日志里没有你预期的内容，用 `!!uh status` 确认当前配置是否正确。

## 2. 验证玩家检测

### 2.1 普通玩家发言

以普通玩家身份在游戏里说一句话。在 debug 模式下，控制台应出现：

```
player_msg: "玩家名" "消息内容" (base)
```

### 2.2 验证命令传递

使用 MCDR 自带的 `!!MCDR` 命令（无需权限），在游戏内执行：

```
!!MCDR status
```

**在游戏内执行**此命令，应收到 tellraw 消息。如果有响应，说明 `send_message_command` 工作正常。

如果游戏内无响应，检查：

- `server_version` 是否检测到（见第 3 节）——版本号决定了 tellraw 的格式
- base handler 配置是否与服务端匹配

### 2.3 带前缀的玩家（称号 / Team 前缀）

如果你的服务器使用了以下任何功能，则应当测试带前缀的玩家能否正常使用 MCDR 命令：

| 场景 | 举例 |
|---|---|
| 计分板 Team 前缀 | `<[Red]玩家名> message` |
| 称号插件（DCSTitleManager 等） | `[Rcon][Owner][Admin] <玩家名> message` |
| 代理端子服前缀 | `[hub] <玩家名> message` |

**操作**：让带前缀的玩家在游戏里执行 `!!MCDR`。

- **预期**：玩家应收到回复。说明 parser 正确识别了该玩家。

- **如果无响应**：说明 handler 未能从带前缀的消息行中提取出玩家名。

按以下步骤处理：

1. **确认问题**：在游戏内启用 `!!uh debug on`，让该玩家发言，观察控制台。如果看到 `player_msg` 行且玩家名正确 → parser 正常工作，问题在其他地方。如果没有出现 `player_msg` 行或玩家名错误 → parser 未正确解析。

2. **启用 chat_prefixes feature**：在 `config.yml` 中启用 `chat_prefixes` feature。它内置了对 Team 前缀和常见称号前缀的支持：

   ```yaml
   features:
     - chat_prefixes
   ```

   然后 `!!uh reload` 重载插件，再次测试。

3. **如果仍不行**：你的服务端可能有特殊的日志格式。参见 [自定义 Profile 指南](custom_profile.md) 编写自己的 feature profile。通常只需要加几行正则（`pre_parse.regex_substitutions` 去除前缀、或 `player_message.patterns` 适配解析格式）。

### 2.4 命令方块 / 函数（commandblock feature）

如果启用了 `commandblock` feature：

| 测试场景 | 操作 | 预期 |
|---|---|---|
| 命令方块 | 放置命令方块，执行任意命令 | 控制台出现 `[Server]` 或 `[@]` 开头行；debug 显示 `pseudo_player: "!commandblock"` |
| 函数 | 运行包含 `/say` 的函数 | debug 显示 `pseudo_player: "!function"` |

## 3. 验证服务器生命周期

MCDR 停止时（`!!MCDR stop` 或自然停止），UnifiedHandler 会输出类似这样的清单：

```
=== Lifecycle Status ===
  server_version:     √
  server_address:     √
  startup_done:       √
  rcon_started:       √
  server_stopping:    √
  send_msg (profile): used 5 time(s)
======================
```

### 各项重要性

| 项目 | 重要程度 | 说明 |
|---|---|---|
| `server_version` | **关键** | MCDR 用版本号判断 tellraw 指令格式。如果此项未检测到，请自行验证 MCDR 的 RText 输出是否存在问题。 |
| `server_address` | 中等 | MCDR 用于显示服务器 IP 端口，不影响指令转发 |
| `startup_done` | **重要** | MCDR 需要此信号判断服务器已就绪；若始终不触发则 MCDR 无法知晓服务器启动完成 |
| `rcon_started` | 低 | 若需要使用 RCON，则需考虑此项 |
| `server_stopping` | 低 | 未检测到通常不影响使用 |
| `send_msg / broadcast` | — | 显示 profile 中自定义的模板被调用了多少次；仅在使用 profile 覆写模板时有意义 |

**如果有任何项目是 ×**：请参见下一节。

## 4. 各项未检测到的处理

如果生命周期报告中有 ×，按以下顺序排查：

1. 确认 MCDR 主配置中的 `handler` 与你的服务端类型一致（如 NeoForge 用 `forge_handler`、Paper 用 `bukkit_handler`）
2. 查看 debug 日志中是否有对应的 debug 行（如 `server_version: "..." (base)`、`startup_done: matched (base)`），确认是 base handler 本身未检测到、还是 profile 未检测到
3. **如果是 base handler 未检测到**：你的服务端日志格式可能与 MCDR 内置的 handler 不兼容。参见 [自定义 Profile 指南](custom_profile.md) 编写 base profile 覆写对应字段。
4. **如果是 profile 未检测到**：检查你启用的 profile 文件中的正则是否正确。可以暂时禁用 feature 单独测试 base handler

## 5. 快速排错检查清单

- [ ] **启动前** `config.yml` 中设置 `debug: true`，启动后**不要 reload 插件**
- [ ] `!!uh status` 显示的 handler 和 features 列表正确
- [ ] `!!MCDR status` 在游戏内有响应（验证 tellraw 正常）
- [ ] 普通玩家发言有 `player_msg` 输出
- [ ] **带前缀的玩家**能正常使用 `!!MCDR` 命令（如果不通则启用 `chat_prefixes` feature，还不行则编写自定义 feature）
- [ ] 服务器停止后生命周期报告中关键项（`server_version`、`startup_done`）为 √
- [ ] 有 × 的项目 → 参考第 4 节，必要时参考 [自定义 Profile 指南](custom_profile.md)

> [!TIP]
> 手动排查太慢？用 AI agent 帮你分析：[借助 AI Agent 分析和编写 Profile](agent_profile_analysis.md)


**中文** | [`English`](custom_profile_en.md)

# 自定义 Profile 指南

如果你使用的服务端不在内置支持列表中，或是想调整某个解析行为——来对地方了，写个 profile 就好。

> [!TIP]
> 不想手动写？让 AI agent 帮你分析日志并编写 profile：[借助 AI Agent 分析和编写 Profile](agent_profile_analysis.md)

## 概念速览

Profile 是一个 YAML 文件，告诉 Unified Handler 如何解析你服务端的日志输出。

分两种类型：

| 类型 | 目录 | 说明 |
|------|------|------|
| **Base** | `base/` | 定义「这是什么服务端」——全量描述或继承已有 handler |
| **Feature** | `features/` | 定义「额外要什么功能」——只写你要增强的部分 |

## 文件位置

- **内置 profiles**（插件自带）：`resources/builtin_profiles/`，首次加载自动释放到 config 目录
- **你的 profiles**：`config/unified_handler/profiles/`，在这里随意增改

注意：内置 profiles 在插件更新时可能有新版。如果你改过，建议换个文件名（比如 `my_server.yml`），这样更新不会冲突。

## JSON Schema

插件的根目录下有 [`profile.schema.json`](../profile.schema.json)。把它配置到你的编辑器里，就能获得：

- 字段自动补全
- 格式合法性检查
- 每个字段的说明提示

大多数支持 YAML 的编辑器（VS Code、JetBrains 系列）都能识别内联 `$schema` 引用。你也可以在 profile 文件顶部加一行：

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/alex3236/UnifiedHandler/main/profile.schema.json
```

## 快速上手：写一个 Feature

假设你的服务端有个特殊的登录提示，想把它识别为玩家加入事件。新建一个文件：

`config/unified_handler/profiles/features/my_server_join.yml`：

```yaml
name: "my_server_join"
version: "1.0.0"
description: "识别我服务端的特殊登录提示"

player_joined:
  patterns:
    - '(?P<name>[^\]]+) jumped into the world'
```

然后在 `config.yml` 的 `features` 列表里加上 `my_server_join` 就完成了。

就是这么简单——你只写了需要修改的部分，其他所有行为都原封不动。

> [!TIP]
> Feature 和 Base 有同一个字段时怎么处理？
>
> - **列表类字段**（`patterns`、`regex_substitutions`、`pseudo_players` 等）——**追加**。Feature 的内容会加在 Base 的内容后面，两边都生效。比如 Base 和 Feature 各写了一条 `player_joined` 的 `patterns`，两条都能检测到。
> - **标量类字段**（`name_validation`、`strip_ansi`、`message_format` 等）——**覆盖**。Feature 的值会替换 Base 的值。比如 Feature 里写了 `name_validation`，Base 的那个就失效了。多个 Feature 同时存在时，`config.yml` 里靠后的说了算。

## 写一个 Base Profile

Base profile 有两种写法：

### 继承模式（Derived）

如果你的服务端基于某个已有的 handler（比如 Forge），只需要覆写差异：

```yaml
name: "my_forge_tweak"
version: "1.0.0"
extends: "forge_handler"      # 👈 关键：声明继承自谁
description: "在 Forge handler 基础上微调"

# 以下只写你要覆写的部分
log_format:
  pattern: '你的自定义日志格式正则...'

player_joined:
  patterns:
    - '你的自定义加入检测...'
```

不写的字段会自动沿用 `extends` 指向的 handler 的行为。

> [!TIP]
> 你写在 profile 里的字段和父 handler（比如 `forge_handler`）的关系：
>
> - **列表类字段**（`patterns`、`regex_substitutions` 等）——**追加在父 handler 之后**。比如你写了一条 `player_joined` 的 `pattern`，它会和 `forge_handler` 自带的加入检测一起生效，不是替换。这对于适配那些「大部分日志格式和原版一样、只有个别行不同」的服务端分支特别方便——十几行 YAML 就够。
> - **标量类字段**（`name_validation`、`message_format` 等）——**覆盖父 handler**。你写了就以你的为准，父 handler 的值不再使用。
>
> 如果还启用了 Feature，Feature 会在这之上继续叠加（和上文「写一个 Feature」一节的规则相同）。

### 完整模式（Full Profile）

如果服务端日志格式和所有已知 handler 都不同，那就从零定义：

```yaml
name: "my_custom_server"
version: "1.0.0"
description: "我的自定义服务端完整适配"
# 注意：没有 extends 字段 = 完整模式

log_format:
  pattern: '\[(?P<hour>\d+):(?P<min>\d+):(?P<sec>\d+)\] ...'

player_message:
  patterns:
    - '...'

player_joined:
  patterns:
    - '...'

# ……以此类推，按需填写
```

完整模式下，所有 13 个 handler 方法都由 profile 驱动。留空的字段使用默认行为（通常是不做处理）。

## 完整字段参考

以下是 profile 中所有可用的字段。括号里标注了适用的 profile 类型。

### 基本信息

```yaml
name: "my_profile"           # 唯一标识，也是文件名（不含 .yml）
version: "1.0.0"            # 语义化版本，用于检测内置 profile 更新
changelog: "v1.0.0: ..."    # 更新日志，内置 profile 升级时展示给用户
description: "简短描述"
extends: "forge_handler"    # 【仅 Base】父 handler 名称，有它 = 继承模式，没有 = 完整模式
```

### `log_format` — 日志行解析

【Base、Feature】

把原始日志行解析为结构化字段。在涉及日志格式适配时必须设置。

```yaml
log_format:
  # 单条正则
  pattern: '\[(?P<hour>\d+):(?P<min>\d+):(?P<sec>\d+)\] \[(?P<thread>[^\]]+)/(?P<logging>[^\]]+)\]: (?P<content>.*)'

  # 或按顺序尝试多条正则（先匹配到的生效）
  patterns:
    - '正则一...'
    - '正则二...'
```

必需命名捕获组：`hour`、`min`、`sec`、`logging`、`content`。

### `pre_parse` — 解析前预处理

【Base、Feature】

对每一行原始日志，在正式的 handler 解析之前应用文本变换。

```yaml
pre_parse:
  strip_ansi: true             # 去掉 ANSI 转义序列（颜色码之类）
  strip_control_chars: true    # 去掉 ASCII 控制字符
  control_chars_except:        # 保留哪些控制字符（每个元素是单个字符）
    - '\n'
    - '\t'
  regex_substitutions:         # 按顺序应用的 regex → replacement 列表
    - pattern: '^某正则'
      replacement: '替换成'
      stop_on_match: false     # 命中后是否停止后续替换，默认 false
```

### `player_message` — 玩家消息检测

【Base、Feature】

```yaml
player_message:
  patterns:
    # 按顺序尝试，先匹配到的生效
    # 必需命名捕获组：name；可选：message（不写则保留 info.content）
    - '(\[Not Secure\] )?<(?P<name>[^>]+)> (?P<message>.*)'
  name_validation: '[a-zA-Z0-9_]{3,16}'   # 校验玩家名合法性的正则
  quote_player_names: false               # 用双引号包裹玩家名（BDS 必需）
  ignore_content_prefixes:                # 以这些前缀开头的消息直接清空
    - /
  extra_fields:                           # 把捕获组的值附带在 Info 对象上
    subserver: subserver                  #   capture_group_name: attribute_name
  regex_substitutions:                    # 对玩家消息内容的 regex → replacement
    - pattern: '^!!VMCDR(\s|$)'
      replacement: '!!MCDR\1'
      stop_on_match: true                 # 命中后停止，防止双向映射互相撤销
```

### `parse_server_stdout` — 伪玩家

【Base、Feature】

把特定日志模式映射到虚拟玩家名——比如命令方块、函数、子服。

```yaml
parse_server_stdout:
  pseudo_players:
    - pattern: '\[(?P<name>@)\] (?P<message>.*)'    # 必需：pattern + player_name
      player_name: '"!commandblock"'                 # 含空格的名字用引号包裹
```

### `player_joined` / `player_left` — 加入 / 离开检测

【Base、Feature】

```yaml
player_joined:
  patterns:
    - 'Player Spawned: (?P<name>.+) xuid: \d+'

player_left:
  patterns:
    - 'Player disconnected: (?P<name>.+), xuid: \d+'
```

必需命名捕获组：`name`。在 wrapper 模式下这些 pattern 是基 handler 的补充；在 full_profile 模式下是唯一检测来源。

### `server_version` / `server_address` — 版本 / 地址检测

【Base、Feature】

```yaml
server_version:
  pattern: 'Version:? (?P<version>.+)\(.*\)'    # 必需：pattern，含命名组 version

server_address:
  pattern: 'IPv4 supported, port: (?P<port>\d+)'   # 必需：pattern，含命名组 port
                                                    # 可选：ip（默认 127.0.0.1）
  detection_mode: first_only                  # "all"（默认）或 "first_only"（BDS 用）
```

### `server_startup_done` / `rcon_started` / `server_stopping` — 状态检测

【Base、Feature】

```yaml
server_startup_done:
  patterns:
    - 'Server started\.'

rcon_started:
  enabled: false                     # 设为 false 彻底禁用 RCON 检测（如 BDS）
  # pattern: 'RCON running on...'    # 不写 enabled: false 时使用此正则

server_stopping:
  patterns:
    - 'Stopping server\.\.\.'
```

### `commands` — 服务端控制命令

【Base、Feature】

```yaml
commands:
  stop: 'stop'                       # 关闭服务端的命令
  send_message:
    template: 'tellraw {target} {message}'          # {target} 替换为玩家名
                                                    # {message} 替换为格式化消息
  broadcast:
    template: 'tellraw @a {message}'                # {message} 替换为格式化消息
  message_format: 'java_json'        # "java_json"（默认）或 "bedrock_rawtext"
```

## 测试你的 Profile

写好 profile 后，可以参考 `tests/` 目录下的测试用例来验证。每个内置 profile 都有对应的完整测试文件。

基本思路：

```python
from unified_handler.profile_loader import load_yaml_profile, compile_full_profile
from unified_handler.handler import UnifiedHandler
from mcdreforged.handler.impl.forge_handler import ForgeHandler

profile = load_yaml_profile('config/unified_handler/profiles/base/my_server.yml')
compiled = compile_full_profile(profile)
handler = UnifiedHandler(ForgeHandler(), compiled, mode='wrapper')

info = handler.parse_server_stdout(...)
assert info.player == 'ExpectedPlayer'
```

## 调试小贴士

- 正则写错了？运行 `!!uh reload`，日志里会告诉你哪个 profile 加载失败
- 玩家检测不到？检查 `name_validation` 正则是否能匹配玩家名
- 继承模式的某字段没生效？确认 `extends` 的 handler 名称拼写正确，大小写敏感
- 不确定 profile 是否被加载？用 `!!uh` 或 `!!uh status` 查看

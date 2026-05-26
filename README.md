**中文** | [`English`](README_en.md)

# Unified Handler

一个用于 MCDReforged 的服务端处理器插件——用 YAML 驱动的 profile 来适配各种 Minecraft 服务端，再也不用为了不同服务端装一堆 handler 插件啦。

## 为什么需要它？

MCDR 的插件 handler 机制有个不小的遗憾：

- **同一时间只有一个插件 handler 能生效**。如果服务器插件 A 提供了「命令方块执行 MCDR 命令」的功能，插件 B 提供了「称号前缀解析」的功能——你只能选一个。
- **插件 handler 无法优雅地继承当前 handler**。如果你想提供一个提供增强的 handler，需要做一些不优雅的检测。

Unified Handler 用一套简单的 **Base ⊕ Features** 架构解决这两个问题。

## 怎么做到的？

```
Handler = Base（服务端类型，选一个）⊕ Features（额外功能，随便叠）
```

- **Base** 决定"这是什么服务端"。内置支持 Vanilla / Forge / Bukkit / Velocity / Bedrock BDS，还包括 Cleanroom、Leaves 等特殊分支的适配。
- **Features** 提供可叠加的增强——**多个 Feature 可以同时启用、自由组合**。命令方块识别、称号前缀解析、子服消息路由……像搭积木一样需要哪个就加哪个。

所有行为都由 **YAML profile** 定义——清晰可读、易于修改、升级无忧。

### 为什么不采用 Hook / Mixin 模式？

起初此项目考虑过开放钩子，让其他插件在消息处理时插入逻辑。但最终没有走这条路：

- **效率更高。** Profile 在加载时一次性编译为预处理的 regex 结构，运行时无需在插件间来回跳转、动态查找回调。每条日志行直接匹配，没有额外的分发开销。

- **更容易上手。** 写 YAML 比写 Python 门槛低得多。不需要懂编程、不需要了解 MCDR API——只要照着日志写几行正则就能适配自己的服务端。内置 profile 就是最好的例子：Cleanroom 和 Leaves 的适配都只用了十几行 YAML。

- **一个 handler 就够了。** MCDR 本身只允许一个插件 handler 生效。Base ⊕ Features 的组合已经能覆盖绝大多数场景。与其让多个插件在运行时互相协调，不如把功能收敛到一处，在早期阶段解决问题。

## 快速开始

### 📦 安装

1. 把插件放进 MCDR 的 `plugins/` 目录
2. 启动或重载 MCDR，UnifiedHandler 将自动生成 `config/unified_handler/config.yml` 并释放内置 profiles
3. 按需编辑配置
4. `!!uh reload` 重载

## ⚙️ 配置

编辑 `config/unified_handler/config.yml`

**情况一：MCDR 自带的 handler 能处理你的服务端**

如果由 [MCDR 自带的 handler](https://docs.mcdreforged.com/zh-cn/latest/configuration.html#handler) 能覆盖大部分情况，而你只需要一些扩展（比如处理 Team 前缀）：

1. 保留 MCDR 配置文件中原有的 `handler` 字段
2. 把 `base_handler` 设为 `"auto"`
3. 在 `features` 中添加你需要的功能

```yaml
base_handler: "auto"

features:
  - chat_prefixes     # 支持 Team 前缀和称号前缀的玩家消息
  - commandblock      # 可以多加几个，随意组合
```

**情况二：MCDR 自带的 handler 无法处理你的服务端**

比如 BDS、Leaves 等，使用本插件内置的 profile：

1. 把 `base_handler` 设为对应的 profile 名称
2. 按需添加 `features`

```yaml
base_handler: "bedrock_bds"    # 详见“内置 Profile”一节

features:
  - commandblock
```

如果内置 profile 还不够用，你也可以[自己写一个](doc/custom_profile.md)：

```yaml
base_handler: "my_custom_server"
```

其他配置项：

```yaml
command_prefix: "!!uh"
admin_permission: 3
```

## 内置 Profile

UnifiedHandler 内置了一些常见的处理情景。感谢这些开发者的付出。

### Base

| 名称 | 文件 | 适用于 | 原始作者 |
|------|------|--------|----------|
| `cleanroom` | `base/cleanroom.yml` | Cleanroom MC | [`Cmmmmmm`](https://github.com/CmmmmmmLau/CleanroomHandler) |
| `leaves` | `base/leaves.yml` | LeavesMC | [`Mooling0602`](https://github.com/Mooling0602/LeavesHandler-MCDR) |
| `lbs_subserver` | `base/lbs_subserver.yml` | Velocity 子服消息识别 | [`Ra1ny_Yuki`](https://github.com/Lazy-Bing-Server/LBSVelocityHandler-MCDR) |
| `bedrock_bds` | `base/bedrock_bds.yml` | Bedrock Dedicated Server | [`Elec glacier`](https://github.com/Elec-Glacier/liteloader_handler), `jiangyan` |

### Features

| 名称 | 文件 | 作用 | 原始作者 |
|------|------|------|----------|
| `commandblock` | `features/commandblock.yml` | `[@]` 和 `[Server]` 消息也能触发 MCDR 命令 | [`Dainsleif`](https://github.com/Dainsleif233/MCDR-Commandblock-Handler) |
| `chat_prefixes` | `features/chat_prefixes.yml` | 解析 `<[Team]Name>` 格式和称号前缀 | [`DCS`](https://github.com/ayuan94/TitlePrefixHandler), [`Mooling0602`](https://github.com/Mooling0602/VanillaTeamHandler-MCDR) |

## 自定义 Profile

想适配自己的服务端？只需要写几行 YAML。我们有完整的 [JSON Schema](profile.schema.json) 帮你自动补全和校验。详见 [自定义 Profile 指南](doc/custom_profile.md)。

## 命令

| 命令            | 作用                         |
| ------------- | -------------------------- |
| `!!uh`        | 查看当前使用的 Base 和启用的 Features |
| `!!uh status` | 同上                         |
| `!!uh reload` | 重载配置和 profiles             |

## 兼容性

- MCDReforged >= 2.13.0
- 零 MCDR 核心修改

## 许可

[FreeBSD License](LICENSE)

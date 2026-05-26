# Unified Handler

A profile-driven server handler plugin for MCDReforged. One plugin, all server types. No more juggling a dozen handler plugins.

[中文版](README.md)

## What problem does it solve?

MCDR's plugin handler system has a couple of quirks:

- **Only one plugin handler can be active at a time.** If plugin A adds "command block support" and plugin B adds "chat prefix parsing" — you have to pick one.
- **Plugin handlers can't elegantly extend the current handler.** Want to tweak just one thing on top of ForgeHandler? You'd have to copy the entire thing.

Unified Handler fixes both with a simple **Base ⊕ Features** architecture.

## How it works

```
Handler = Base (server type, pick one) ⊕ Features (extras, stack as many as you like)
```

- **Base** tells the plugin what kind of server you're running. Built-in support for Vanilla, Forge, Bukkit, Velocity, Bedrock BDS, plus community forks like Cleanroom and Leaves.
- **Features** are stackable enhancements. Command block recognition, chat prefix parsing, subserver message routing — mix and match like building blocks.

Everything is defined in **YAML profiles** — readable, editable, and upgrade-safe.

## Quick Start

<details>
<summary>📦 Installation</summary>

1. Drop the plugin into MCDR's `plugins/` directory
2. Start MCDR — it auto-generates `config/unified_handler/config.yml` and deploys built-in profiles
3. (Optional) Tweak the config to your liking
4. `!!uh reload` to apply

</details>

<details>
<summary>⚙️ Configuration</summary>

`config/unified_handler/config.yml`:

**Case 1: MCDR's built-in handler covers your server**

[MCDR's built-in handlers](https://docs.mcdreforged.com/en/latest/configuration.html#handler) (Vanilla / Forge / Bukkit / Velocity, etc.) handle most cases. You just need some extensions (like Team prefix handling):

1. Keep the `handler` field in your MCDR config file
2. Set `base_handler` to `"auto"`
3. Add the features you want

```yaml
base_handler: "auto"

features:
  - chat_prefixes     # parse team/rank prefixes in player chat
```

**Case 2: MCDR's built-in handler can't handle your server**

For servers like BDS, Leaves, etc. — use the plugin's built-in profiles:

1. Set `base_handler` to the matching profile name
2. Add features as needed

```yaml
base_handler: "bedrock_bds"    # built-in options: bedrock_bds, cleanroom_fix, leaves_fix, lbs_subserver

features:
  - commandblock
```

If the built-in profiles aren't enough, you can always [write your own](doc/custom_profile_en.md):

```yaml
base_handler: "my_custom_server"
```

Other config fields:

```yaml
command_prefix: "!!uh"
admin_permission: 3
```

</details>

## Built-in Profiles

### Base (server adaptation)

| Name | File | For |
|------|------|-----|
| `cleanroom_fix` | `base/cleanroom_fix.yml` | Cleanroom MC (extends forge_handler) |
| `leaves_fix` | `base/leaves_fix.yml` | Leaves fork (extends bukkit_handler) |
| `lbs_subserver` | `base/lbs_subserver.yml` | Velocity subserver routing (extends velocity_handler) |
| `bedrock_bds` | `base/bedrock_bds.yml` | Bedrock Dedicated Server (standalone full profile) |

> Other server types (Vanilla, Forge, Bukkit, Velocity, etc.) use MCDR's built-in handlers. Set `base_handler: "auto"` and you're done.

### Features (stackable add-ons)

| Name | File | Does |
|------|------|------|
| `commandblock` | `features/commandblock.yml` | `[@]` and `[Server]` output can trigger MCDR commands |
| `chat_prefixes` | `features/chat_prefixes.yml` | Parse `<[Team]Name>` and rank prefix chat formats |

## Custom Profiles

Need to adapt a custom server? Just write a few lines of YAML. We provide a full [JSON Schema](profile.schema.json) for autocompletion and validation. Check out the [Custom Profile Guide](doc/custom_profile_en.md).

## Commands

| Command | Does |
|---------|------|
| `!!uh` | Show current Base and active Features |
| `!!uh status` | Same as above |
| `!!uh reload` | Reload config and profiles |

## Compatibility

- MCDReforged >= 2.13.0
- Zero MCDR core modifications

## License

[FreeBSD License](LICENSE)

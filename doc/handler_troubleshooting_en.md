[`中文`](handler_troubleshooting.md) | **English**

# Handler Verification Guide

After configuring UnifiedHandler, run through this guide's checks to confirm everything works. If any issues are found, this document also covers how to resolve them.

## 0. Before You Start: Debug Timing

**Important**: To see the complete lifecycle report, you must enable debug mode **before** starting MCDR and **do not reload this plugin** during the session (`!!uh reload` resets all tracking data).

Set in `config/unified_handler/config.yml`:

```yaml
debug: true
```

Then start MCDR.

## 1. Verify Startup

Check the MCDR console for these lines at startup:

```
[unified_handler]: ...
[unified_handler]: Base handler: forge_handler    (or vanilla_handler / bukkit_handler)
[unified_handler]: Features: chat_prefixes         (or your enabled features)
[unified_handler]: Unified handler registered successfully
```

If registration succeeded but something looks off, use `!!uh status` to check the current configuration.

## 2. Verify Player Detection

### 2.1 Normal Player Chat

Chat as a regular player in-game. With debug mode on, the console shows:

```
player_msg: "PlayerName" "message" (base)
```

### 2.2 Verify Command Forwarding

Use MCDR's built-in `!!MCDR` command (no permission required). Run it in-game:

```
!!MCDR status
```

**If run in-game**, you should receive a tellraw message. A response means `send_message_command` works correctly.

No in-game response? Check:

- Whether `server_version` was detected (see Section 3) — the version determines the tellraw format
- Whether your base handler config matches your server type

### 2.3 Prefixed Players (Titles / Team Prefixes)

If your server uses any of the following, you should test whether prefixed players can use MCDR commands:

| Scenario | Example |
|---|---|
| Scoreboard team prefix | `<[Red]PlayerName> message` |
| Title plugins (DCSTitleManager etc.) | `[Rcon][Owner][Admin] <PlayerName> message` |
| Proxy sub-server prefix | `[hub] <PlayerName> message` |

**Action**: Have a prefixed player run `!!MCDR` in-game.

- **Expected**: The player should receive a response. This means the parser correctly identified them.

- **No response?** The handler failed to extract the player name from the prefixed log line.

Troubleshoot as follows:

1. **Confirm the issue**: Enable `!!uh debug on` in-game, have the player chat, watch the console. If a `player_msg` line appears with the correct name → the parser works; the issue is elsewhere. If no `player_msg` line or wrong name → the parser is failing.

2. **Enable chat_prefixes feature**: In `config.yml`:

   ```yaml
   features:
     - chat_prefixes
   ```

   Then `!!uh reload` and test again. This feature includes built-in support for team prefixes and common title prefixes.

3. **If still broken**: Your server may have a unique log format. See [Custom Profile Guide](custom_profile_en.md) to write your own feature profile. Usually just a few regex lines (`pre_parse.regex_substitutions` to strip prefixes, or `player_message.patterns` to adapt parsing).

### 2.4 Command Blocks / Functions (commandblock feature)

If you enabled the `commandblock` feature:

| Scenario | Action | Expected |
|---|---|---|
| Command block | Place a command block, run any command | Console shows `[Server]` or `[@]` line; debug shows `pseudo_player: "!commandblock"` |
| Functions | Run a function containing `/say` | Debug shows `pseudo_player: "!function"` |

## 3. Verify Server Lifecycle

When MCDR stops (`!!MCDR stop` or natural shutdown), UnifiedHandler prints a summary:

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

### Item Importance

| Item | Priority | Why |
|---|---|---|
| `server_version` | **Critical** | MCDR uses the version to determine the tellraw format. If undetected, verify MCDR's RText output manually. |
| `server_address` | Medium | Display only. Does not affect command forwarding |
| `startup_done` | **Important** | MCDR needs this signal to know the server is ready. Without it, MCDR cannot detect server startup |
| `rcon_started` | Low | Only relevant if you use RCON |
| `server_stopping` | Low | Missing detection is usually harmless |
| `send_msg / broadcast` | — | Shows how many times a profile-defined template was used. Only meaningful when your profile overrides templates |

**If any item shows ×**: see the next section.

## 4. Handling Missing Detections

If the lifecycle report shows any ×, troubleshoot in this order:

1. Verify MCDR's main config `handler` matches your server type (e.g., NeoForge → `forge_handler`, Paper → `bukkit_handler`)
2. Check debug logs for corresponding lines (`server_version: "..." (base)`, `startup_done: matched (base)`) to determine whether the base handler or a profile is failing
3. **If the base handler failed**: Your server's log format may not be compatible with MCDR's built-in handler. See [Custom Profile Guide](custom_profile_en.md) to write a base profile with overridden fields.
4. **If a profile failed**: Check the regex in your enabled profile. Try disabling features temporarily to test the base handler alone.

## 5. Quick Checklist

- [ ] **Before starting MCDR**: set `debug: true` in `config.yml`. **Do not reload the plugin** during the session
- [ ] `!!uh status` shows the correct handler and features
- [ ] `!!MCDR status` gets a response in-game (verifies tellraw works)
- [ ] Normal player chat produces `player_msg` output
- [ ] **Prefixed players** can use `!!MCDR` commands (if not, enable `chat_prefixes` feature; if still broken, write a custom feature)
- [ ] After server stop, lifecycle report shows √ for critical items (`server_version`, `startup_done`)
- [ ] Items with × → see Section 4; if needed, refer to [Custom Profile Guide](custom_profile_en.md)

> [!TIP]
> Manual troubleshooting too slow? Use an AI agent: [AI-Assisted Profile Analysis and Authoring](agent_profile_analysis_en.md)

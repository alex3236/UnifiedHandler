[`中文`](agent_profile_analysis.md) | **English**

# AI-Assisted Profile Analysis and Authoring

If manual troubleshooting takes too long, you can have an AI agent analyze the server logs, diagnose UnifiedHandler issues, and give recommendations.

## Preparation

To produce a clean log for the AI, do the troubleshooting in a dedicated session:

- **Shut down MCDR** (`stop` or ^C)
- Enable logging in MCDR's `config.yml` at the instance root:

  ```yaml
  write_server_output_to_log_file: true
  ```

- Set `debug: true` in `config/unified_handler/config.yml`
- **Start MCDR**, then follow the [Handler Verification Guide](handler_troubleshooting_en.md) and complete every test (`!!MCDR`, normal player chat, prefixed player chat, etc.). **Do not play normally** — only perform the tests from the guide, then shut down MCDR

This gives you a `logs/MCDR.log` containing only the test output. Then point the agent to your MCDR instance directory and use the following prompt:

```text
You are troubleshooting a **MCDR (MCDReforged)** handler issue. The server uses the **UnifiedHandler** plugin (YAML-profile-driven log parsing).

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

The agent will analyze the logs and config, give recommendations. For example:

https://github.com/user-attachments/assets/e977baa4-3e23-408d-9183-2bb9256ae66e

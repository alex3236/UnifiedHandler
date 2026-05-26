[`中文`](custom_profile.md) | **English**

# Custom Profile Guide

If your server isn't in the built-in list, or you want to tweak a parsing behavior — you're in the right place. Just write a profile.

## The big picture

A profile is a YAML file that tells Unified Handler how to parse your server's log output.

Two flavors:

| Type | Directory | Purpose |
|------|-----------|---------|
| **Base** | `base/` | Defines "what server is this" — either fully, or by extending an existing handler |
| **Feature** | `features/` | Defines "what extra behavior do I want" — only write the parts you're adding |

## Where files live

- **Built-in profiles** (shipped with the plugin): `resources/builtin_profiles/`, auto-deployed to the config dir on first load
- **Your profiles**: `config/unified_handler/profiles/` — add or edit freely here

Note: built-in profiles may get updates when the plugin upgrades. If you've customized one, consider giving it a different filename (like `my_server.yml`) to avoid conflicts.

## JSON Schema

A [`profile.schema.json`](../profile.schema.json) lives at the plugin root. Wire it up in your editor and you'll get:

- Field autocompletion
- Format validation
- Inline descriptions for every field

Most YAML-aware editors (VS Code, JetBrains) pick up `$schema` references automatically. You can also add to the top of your profile:

```yaml
# yaml-language-server: $schema=../../profile.schema.json
```

## Quick start: write a Feature

Say your server has a special login message you want to recognize as a join event. Create:

`config/unified_handler/profiles/features/my_server_join.yml`:

```yaml
name: "my_server_join"
version: "1.0.0"
description: "Recognize my server's special login message"

player_joined:
  patterns:
    - '(?P<name>[^\]]+) jumped into the world'
```

Then add `my_server_join` to the `features` list in `config.yml`. That's it.

You only wrote what you needed to change. Everything else stays as-is.

> [!TIP]
> What if a Feature and the Base define the same field?
>
> - **List fields** (`patterns`, `regex_substitutions`, `pseudo_players`, etc.) — **appended**. The Feature's content is added after the Base's. Both take effect. For example, if both the Base and Feature define `player_joined` patterns, both are checked.
> - **Scalar fields** (`name_validation`, `strip_ansi`, `message_format`, etc.) — **overwritten**. The Feature's value replaces the Base's. For example, writing `name_validation` in a Feature invalidates the Base's version. When multiple Features set the same field, the one listed last in `config.yml` wins.

## Writing a Base Profile

Two ways to write one:

### Derived mode

If your server is based on an existing handler (e.g., Forge), just override what's different:

```yaml
name: "my_forge_tweak"
version: "1.0.0"
extends: "forge_handler"      # 👈 this is the key line
description: "A small tweak on top of ForgeHandler"

# Only write what you're overriding here
log_format:
  pattern: 'your custom log format regex...'

player_joined:
  patterns:
    - 'your custom join detection...'
```

Fields you leave out will keep the behavior from `extends`.

> [!TIP]
> How fields in your profile interact with the parent handler (e.g., `forge_handler`):
>
> - **List fields** (`patterns`, `regex_substitutions`, etc.) — **appended after the parent handler**. If you write a `player_joined` pattern, it runs alongside `forge_handler`'s built-in join detection — it doesn't replace it. This is what makes adapting server forks so efficient: when most log lines look standard but a handful differ, you only need a dozen lines of YAML.
> - **Scalar fields** (`name_validation`, `message_format`, etc.) — **overwrite the parent handler**. Whatever you set takes priority, and the parent's value is discarded.
>
> If Features are also enabled, they layer on top following the same rules explained in the "Writing a Feature" section above.

### Full Profile mode

If your server log format is completely different from any known handler, define everything from scratch:

```yaml
name: "my_custom_server"
version: "1.0.0"
description: "Full adaptation for my custom server"
# No extends field = Full Profile mode

log_format:
  pattern: '\[(?P<hour>\d+):(?P<min>\d+):(?P<sec>\d+)\] ...'

player_message:
  patterns:
    - '...'

player_joined:
  patterns:
    - '...'

# … and so on. Fill in what you need.
```

In Full Profile mode, all 13 handler methods are driven by the profile. Omitted fields use default behavior (usually no-op).

## Full field reference

Here's every field you can use. Parentheses indicate which profile type it applies to.

### Metadata

```yaml
name: "my_profile"           # Unique ID, also the filename (without .yml)
version: "1.0.0"            # SemVer, used to detect built-in profile updates
changelog: "v1.0.0: ..."    # Changelog, shown to user on built-in profile upgrade
description: "Brief description"
extends: "forge_handler"    # [Base only] Parent handler name. Present = derived, absent = full
```

### `log_format` — log line parsing

[Base, Feature]

Parses raw log lines into structured fields. Required when adapting log formats.

```yaml
log_format:
  # Single regex
  pattern: '\[(?P<hour>\d+):(?P<min>\d+):(?P<sec>\d+)\] \[(?P<thread>[^\]]+)/(?P<logging>[^\]]+)\]: (?P<content>.*)'

  # Or multiple regexes tried in order (first match wins)
  patterns:
    - 'first regex...'
    - 'second regex...'
```

Required named groups: `hour`, `min`, `sec`, `logging`, `content`.

### `pre_parse` — pre-parse transformations

[Base, Feature]

Text transformations applied to every log line BEFORE the handler parses it.

```yaml
pre_parse:
  strip_ansi: true             # Strip ANSI escape sequences (color codes, etc.)
  strip_control_chars: true    # Strip ASCII control characters
  control_chars_except:        # Characters to KEEP (each is a single char)
    - '\n'
    - '\t'
  regex_substitutions:         # Ordered list of regex → replacement
    - pattern: '^some regex'
      replacement: 'replace with'
      stop_on_match: false     # Stop after this match? Default: false
```

### `player_message` — player chat detection

[Base, Feature]

```yaml
player_message:
  patterns:
    # Tried in order, first match wins
    # Required named group: name; optional: message (keeps info.content if omitted)
    - '(\[Not Secure\] )?<(?P<name>[^>]+)> (?P<message>.*)'
  name_validation: '[a-zA-Z0-9_]{3,16}'   # Regex to validate extracted player names
  quote_player_names: false               # Wrap names in double quotes (required for BDS)
  ignore_content_prefixes:                # Lines starting with these are blanked
    - /
  extra_fields:                           # Attach capture groups to the Info object
    subserver: subserver                  #   capture_group_name: attribute_name
  regex_substitutions:                    # Regex → replacement on player message content
    - pattern: '^!!VMCDR(\s|$)'
      replacement: '!!MCDR\1'
      stop_on_match: true                 # Prevent bidirectional mappings from undoing each other
```

### `parse_server_stdout` — pseudo players

[Base, Feature]

Map specific log patterns to virtual player names — command blocks, functions, subservers.

```yaml
parse_server_stdout:
  pseudo_players:
    - pattern: '\[(?P<name>@)\] (?P<message>.*)'    # Required: pattern + player_name
      player_name: '"!commandblock"'                 # Wrap names with spaces in quotes
```

### `player_joined` / `player_left` — join / leave detection

[Base, Feature]

```yaml
player_joined:
  patterns:
    - 'Player Spawned: (?P<name>.+) xuid: \d+'

player_left:
  patterns:
    - 'Player disconnected: (?P<name>.+), xuid: \d+'
```

Required named group: `name`. In wrapper mode these supplement the base handler; in full_profile mode they're the only detection source.

### `server_version` / `server_address` — version / address detection

[Base, Feature]

```yaml
server_version:
  pattern: 'Version:? (?P<version>.+)\(.*\)'    # Required: pattern with named group version

server_address:
  pattern: 'IPv4 supported, port: (?P<port>\d+)'   # Required: pattern with named group port
                                                    # Optional: ip (defaults to 127.0.0.1)
  detection_mode: first_only                  # "all" (default) or "first_only" (BDS needs this)
```

### `server_startup_done` / `rcon_started` / `server_stopping` — state detection

[Base, Feature]

```yaml
server_startup_done:
  patterns:
    - 'Server started\.'

rcon_started:
  enabled: false                     # Set false to always return False (e.g., BDS has no RCON)
  # pattern: 'RCON running on...'    # Used when enabled is not false

server_stopping:
  patterns:
    - 'Stopping server\.\.\.'
```

### `commands` — server control commands

[Base, Feature]

```yaml
commands:
  stop: 'stop'                       # Command to gracefully stop the server
  send_message:
    template: 'tellraw {target} {message}'          # {target} → player name
                                                    # {message} → formatted message
  broadcast:
    template: 'tellraw @a {message}'                # {message} → formatted message
  message_format: 'java_json'        # "java_json" (default) or "bedrock_rawtext"
```

## Testing your profile

Once you've written a profile, check out the test files under `tests/` for examples. Every built-in profile has a corresponding test file.

The basic pattern:

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

## Debugging tips

- Regex not working? Run `!!uh reload` — the log will tell you which profile failed to load
- Player not detected? Check that `name_validation` can match your player names
- Derived profile not doing what you expect? Verify the `extends` handler name is spelled correctly (case-sensitive)
- Not sure if your profile is loaded? Use `!!uh` or `!!uh status` to see

# AGENTS.md

This file provides guidance to agents when working on the project.

See CLAUDE.md for the full project conventions. This file covers agent-specific constraints.

## Naming convention

- In Chinese translations (`lang/zh_cn.yml`), refer to this plugin as **`UnifiedHandler`** (the project name), not "统一处理器" or any translated description. The plugin name is a proper noun and should remain in English.
- The generic term "handler" / "处理器" (the MCDR concept) may still be used in Chinese text when referring to the underlying server handler mechanism, not this plugin.

## Logger output

- **Never add `[UnifiedHandler]` or similar prefixes** to `server.logger` calls. MCDR's logger automatically prepends `[unified_handler]: ` — adding a manual prefix results in a redundant double prefix.
- For debug/log output, use `RText` with `color=RColor.gold` and call `.to_colored_text()`: `server.logger.info(RText(msg, color=RColor.gold).to_colored_text())`. This makes debug messages visually distinct in the console.

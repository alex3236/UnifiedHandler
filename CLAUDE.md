# CLAUDE.md

This file provides guidance to agents when working on the project.

## Documentation style

- Keep it warm and friendly, but not cutesy. Avoid over-stylization.
- Use emoji sparingly — only when it genuinely helps scan a page. Never use bold or emoji for emphasis inside paragraphs.
- Be concise. Every sentence should earn its place.
- Chinese is the default language. English translations should be maintained alongside, with cross-links between them.

## What to update when making changes

1. **Handler behavior changed** → update `handler.py`, then check if `profile_loader.py` needs corresponding compiled data (new fields, changed regex structures).
2. **Profile field added or changed** → update `profile.schema.json`. If a definition is shared between sections, use `$defs`.
3. **New profile feature** → add tests. Every built-in profile has its own test file.
4. **Existing profile behavior changed** → run the full test suite (`python -m pytest tests/ -v`).
5. **Configuration changes visible to users** → update both `README.md` and `README_en.md`, and the custom profile docs (`doc/custom_profile.md`, `doc/custom_profile_en.md`) if relevant.
6. **User-facing strings added** → both `server.logger` messages and `server.reply` / `src.reply` output must go through i18n (`lang/zh_cn.yml` + `lang/en_us.yml`). Don't hardcode user-visible strings in Python — use the translation API. The two lang files must have matching key structures.

## Key conventions

- `stop_on_match` in `regex_substitutions`: when true, stops processing further substitutions after this one changes the text. This prevents bidirectional mappings (like `!!VMCDR ↔ !!MCDR`) from undoing each other.
- `name_validation` in `player_message`: a regex used to reject spurious player detections. In wrapper mode it runs after the base handler has already run; in full_profile mode it's the only gate.
- `extra_fields` in `player_message`: maps named capture groups to attributes on the `Info` object. Useful for injecting subserver names or other metadata.
- `extends` in base profiles: references an MCDR handler class name (e.g., `forge_handler`), not a profile filename.
- The `features` list in `config.yml` is ordered — later features can override earlier ones and the base.

## Pre-commit checklist

- [ ] All tests pass: `python -m pytest tests/ -v`
- [ ] Schema changes are reflected in `profile.schema.json`
- [ ] New profile fields are documented in `doc/custom_profile*.md` (both languages) if user-facing
- [ ] README is updated if the change affects the getting-started flow
- [ ] Both Chinese and English docs are updated

## Commit messages

Use Conventional Commits. Use English (US). No emojis.

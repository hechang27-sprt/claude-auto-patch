# claude-auto-patch

Configurable auto-patch system for Claude Code. Applies binary patches on session startup and provides a skill for creating new patches.

## Project Structure

```
hooks/
  auto-patch.py           - SessionStart hook: applies enabled patches
  auto-patch-config.json  - Toggle individual patches on/off
skills/
  create-patch/           - Skill for creating new patch definitions
    SKILL.md              - Skill instructions
    scripts/              - Helper scripts for code analysis
    references/           - Patching best practices guide
```

## Key Concepts

- **Equal-length replacement**: Patches must be exactly the same byte length as original code
- **Three-state detection**: Each patch has `target_re` (unpatched), `patched_re` (patched), and implicit "unknown"
- **Cache mechanism**: Uses file mtime to skip re-scanning unchanged binaries
- **Platform handling**: Windows rename-swap for running exe, macOS codesign

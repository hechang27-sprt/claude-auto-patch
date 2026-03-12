# claude-auto-patch

**[English](#english) | [中文](#中文)**

---

<a id="english"></a>

## English

A configurable auto-patch system for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Automatically applies binary patches before Claude starts and survives updates.

### Features

- **Auto-patch before startup** — Shell wrapper runs patches before Claude launches, avoiding file-lock issues
- **Configurable** — Enable/disable individual patches via JSON config
- **Smart caching** — Skips re-scanning unchanged binaries (uses file mtime)
- **Cross-platform** — Windows (PowerShell), macOS/Linux (Bash/Zsh)
- **Zero-copy install** — Clone once, `git pull` to update. No files copied to `~/.claude/`
- **Create patches with AI** — `/create-patch` skill guides Claude through the entire patch creation workflow

### Quick Start

```bash
git clone https://github.com/Cedriccmh/claude-auto-patch.git ~/.claude-auto-patch
cd ~/.claude-auto-patch && python install.py
```

Restart your shell. Done!

### Update

```bash
cd ~/.claude-auto-patch && git pull
```

### Uninstall

```bash
cd ~/.claude-auto-patch && python install.py --uninstall
```

### Other Commands

```bash
python install.py --status    # Check installation status
python install.py --dry-run   # Preview changes without modifying files
```

### How It Works

The installer injects a shell wrapper function into your profile (`$PROFILE` for PowerShell, `.bashrc`/`.zshrc` for Bash/Zsh):

```
You type "claude"
  -> Shell wrapper function runs
  -> No claude process running? -> python auto_patch.py
    -> Load config (which patches are enabled)
    -> Find claude binary / cli.js in PATH
    -> Check cache (file mtime + enabled patches)
    -> If unchanged: skip (< 1ms)
    -> If changed: apply patches (equal-length byte replacement)
  -> Launch the real claude binary
```

### Install Skill (Optional)

To use the `/create-patch` skill for AI-assisted patch creation:

```bash
cp -r ~/.claude-auto-patch/skills/create-patch ~/.claude/skills/
```

### Configuration

Edit `auto-patch-config.json` to toggle patches:

```json
{
  "toolsearch": true
}
```

Set a patch to `false` to disable it. Remove the cache file to force re-evaluation:

```bash
rm ~/.claude/.auto-patch-cache.json
```

### Built-in Patches

| Patch | Description | Default |
|-------|-------------|---------|
| `toolsearch` | Remove Tool Search domain restriction | Enabled |

### Creating New Patches

#### Using the Skill (Recommended)

Use `/create-patch` in Claude Code and describe what you want to patch. The AI will:

1. Search the npm version of `cli.js` for relevant code
2. Analyze the minified JavaScript logic
3. Design an equal-length binary replacement
4. Register the patch definition and update config
5. Test the patch

#### Manual

Add a `PatchDef` to `auto_patch.py`:

```python
"your_patch": PatchDef(
    name="your_patch",
    description="What this patch does",
    target_re=re.compile(rb'regex matching original code'),
    patched_re=re.compile(rb'regex matching patched code'),
    build_replacement=lambda m: _equal_length_replace(
        b"replacement_prefix", b"replacement_suffix", m
    ),
),
```

Then add the toggle to `auto-patch-config.json`:

```json
{
  "toolsearch": true,
  "your_patch": true
}
```

### Equal-Length Replacement

Patches must be exactly the same byte length as the original code. This is achieved by using JavaScript comments (`/* */`) as padding:

```
Original: return["api.anthropic.com"].includes(Xe)}catch{return!1}
Patched:  return!0/*                          */}catch{return!0}
```

### Three-State Detection

Each patch has two regexes:
- `target_re` matches unpatched code -> safe to apply
- `patched_re` matches patched code -> already done, skip
- Neither matches -> version incompatible, do not touch

### Requirements

- Python 3.10+
- Claude Code (bun binary or npm install)

---

<a id="中文"></a>

## 中文

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) 的可配置自动补丁系统。在 Claude 启动前自动应用补丁，更新后自动恢复。

### 功能

- **启动前自动补丁** — Shell wrapper 在 Claude 启动前运行补丁，避免文件锁问题
- **可配置** — 通过 JSON 配置文件启用/禁用单个补丁
- **智能缓存** — 跳过未变更的二进制文件（基于 mtime），< 1ms
- **跨平台** — Windows（PowerShell）、macOS/Linux（Bash/Zsh）
- **零拷贝安装** — clone 一次，`git pull` 即更新。无需复制文件到 `~/.claude/`
- **AI 辅助创建补丁** — `/create-patch` skill 引导 Claude 完成补丁创建全流程

### 快速开始

```bash
git clone https://github.com/Cedriccmh/claude-auto-patch.git ~/.claude-auto-patch
cd ~/.claude-auto-patch && python install.py
```

重启终端即可！

### 更新

```bash
cd ~/.claude-auto-patch && git pull
```

### 卸载

```bash
cd ~/.claude-auto-patch && python install.py --uninstall
```

### 其他命令

```bash
python install.py --status    # 查看安装状态
python install.py --dry-run   # 预览变更，不修改文件
```

### 工作原理

安装器将一个 shell wrapper 函数注入到你的 profile 中（PowerShell 的 `$PROFILE`、Bash 的 `.bashrc`、Zsh 的 `.zshrc`）：

```
你输入 "claude"
  -> Shell wrapper 函数运行
  -> 没有 claude 进程在运行？ -> python auto_patch.py
    -> 加载配置（哪些补丁已启用）
    -> 在 PATH 中查找 claude 二进制或 cli.js
    -> 检查缓存（文件 mtime + 已启用补丁列表）
    -> 未变更：跳过（< 1ms）
    -> 已变更：应用补丁（等长字节替换）
  -> 启动真正的 claude 二进制
```

### 安装 Skill（可选）

使用 `/create-patch` skill 进行 AI 辅助补丁创建：

```bash
cp -r ~/.claude-auto-patch/skills/create-patch ~/.claude/skills/
```

### 配置

编辑 `auto-patch-config.json` 切换补丁开关：

```json
{
  "toolsearch": true
}
```

设为 `false` 禁用。删除缓存文件可强制重新检测：

```bash
rm ~/.claude/.auto-patch-cache.json
```

### 内置补丁

| 补丁 | 说明 | 默认 |
|------|------|------|
| `toolsearch` | 解除 Tool Search 域名限制 | 启用 |

### 创建新补丁

#### 使用 Skill（推荐）

在 Claude Code 中使用 `/create-patch`，描述你想补丁的内容。AI 将自动：

1. 在 npm 版 `cli.js` 中搜索相关代码
2. 分析 minified JavaScript 逻辑
3. 设计等长二进制替换
4. 注册补丁定义并更新配置
5. 测试补丁

#### 手动添加

在 `auto_patch.py` 中添加 `PatchDef`：

```python
"your_patch": PatchDef(
    name="your_patch",
    description="补丁说明",
    target_re=re.compile(rb'匹配原始代码的正则'),
    patched_re=re.compile(rb'匹配补丁后代码的正则'),
    build_replacement=lambda m: _equal_length_replace(
        b"替换前缀", b"替换后缀", m
    ),
),
```

然后在 `auto-patch-config.json` 中添加开关：

```json
{
  "toolsearch": true,
  "your_patch": true
}
```

### 等长替换

补丁必须与原始代码完全等长。通过 JavaScript 注释（`/* */`）填充实现：

```
原始: return["api.anthropic.com"].includes(Xe)}catch{return!1}
补丁: return!0/*                          */}catch{return!0}
```

### 三态检测

每个补丁有两个正则表达式：
- `target_re` 匹配未补丁代码 -> 可安全应用
- `patched_re` 匹配已补丁代码 -> 跳过
- 都不匹配 -> 版本不兼容，不操作

### 环境要求

- Python 3.10+
- Claude Code（bun 二进制或 npm 安装）

## License / 许可证

MIT

---
name: create-patch
description: >
  为 Claude Code 的 bun 二进制或 npm cli.js 创建补丁。
  使用场景：(1) 绕过 Claude Code 中的特定检查或限制，
  (2) 通过补丁修改 Claude Code 行为，(3) 创建新的 auto-patch 规则。
  触发条件："/create-patch"、"创建补丁"、"patch Claude Code"、
  "绕过...检查"、"禁用 Claude Code 的..."。
---

# 为 Claude Code 创建补丁

为 Claude Code 的 minified JS 代码（bun 二进制或 npm cli.js）创建等长二进制补丁。

## 工作流程

### 1. 定位 npm cli.js

查找 npm 全局安装的 `@anthropic-ai/claude-code` 包用于分析（npm 版是文本文件，适合代码探索）。

```
npm root -g  -->  <root>/node_modules/@anthropic-ai/claude-code/cli.js
```

如果未找到，向用户询问：

> npm 版 Claude Code 未安装，分析代码需要它作为参考。是否执行 `npm install -g @anthropic-ai/claude-code` 来安装？

确认 cli.js 可用后再继续。

### 2. 搜索目标代码

运行 `scripts/search_target.py` 查找相关代码片段：

```bash
python scripts/search_target.py <cli.js路径> "<关键词>"
```

脚本返回匹配的代码片段及其字节偏移和上下文。

如果用户描述模糊，搜索多个相关关键词。常见搜索策略：
- 域名限制：搜索域名字符串（如 `api.anthropic.com`）
- Feature flags：搜索 flag 名称
- 错误消息：搜索错误文本
- API 调用：搜索 endpoint 路径

### 3. 分析代码

搜索到的片段是 minified JS。需要心理展开还原：

```
# Minified
return["api.anthropic.com"].includes(Xe)}catch{return!1}

# 展开后
try {
  return ["api.anthropic.com"].includes(Xe);
} catch {
  return !1;  // false
}
```

对于复杂片段，可以创建格式化副本进行深入分析：

```bash
npx prettier --write <临时副本.js>
```

需要识别：
- **代码做了什么**（正在执行的检查/限制）
- **期望的行为是什么**（补丁应该把它改成什么）
- **最小替换方案**（实现目标的最简替换）

### 4. 设计等长替换

**关键约束：替换后的字节长度必须与原始代码完全一致。**

用 JS 注释（`/* */`）吸收多余字节：

```
原始: return["api.anthropic.com"].includes(Xe)}catch{return!1}
补丁: return!0/*                          */}catch{return!0}
      ^--- 同样长度，合法 JS，不同行为 ---^
```

运行 `scripts/validate_patch.py` 验证：

```bash
python scripts/validate_patch.py \
  --target-re 'return\["api\.anthropic\.com"\]\.includes\([A-Za-z_$][A-Za-z0-9_$]*\)\}catch\{return!1\}' \
  --patched-re 'return!0/\* *\*/\}catch\{return!0\}' \
  --replacement-prefix 'return!0/*' \
  --replacement-suffix '*/}catch{return!0}' \
  --file "<cli.js 路径>"
```

脚本检查：正则是否匹配、长度是否一致、替换是否有效。

### 5. 注册补丁

读取项目的 `hooks/auto-patch.py`，在 `PATCHES` 字典中添加新的 `PatchDef` 条目：

```python
"patch_name": PatchDef(
    name="patch_name",
    description="补丁说明",
    target_re=re.compile(rb'...'),
    patched_re=re.compile(rb'...'),
    build_replacement=lambda m: _equal_length_replace(
        b"prefix", b"suffix", m
    ),
),
```

更新 `hooks/auto-patch-config.json`，添加新补丁（默认启用）：

```json
{
  "existing_patch": true,
  "patch_name": true
}
```

### 6. 测试

运行 auto-patch hook 验证：

```bash
# 清除缓存强制重新检测
rm -f ~/.claude/.auto-patch-cache.json
python hooks/auto-patch.py
```

预期输出：`[auto-patch] claude.exe: applied patch_name`

## 规则

- **禁止改变字节长度** — 用 `/* */` 注释填充
- **正则必须容忍变量名变化** — JS 标识符用 `[A-Za-z_$][A-Za-z0-9_$]*` 匹配
- **三态检测** — 每个补丁需要 `target_re`（未补丁）、`patched_re`（已补丁），以及隐含的 "unknown"（都不匹配）
- **unknown = 不操作** — 都不匹配说明版本不兼容，静默跳过
- **替换结果必须是合法 JS** — 语法错误会导致 Claude Code 启动崩溃

详细补丁原理参见 [references/patching-guide.md](references/patching-guide.md)。

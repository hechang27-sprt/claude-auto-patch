# 补丁指南

## Bun 二进制结构

Claude Code 的 bun 二进制 = 原生外壳 + 内嵌的 minified JS bundle。
JS 代码经过 minify（短变量名、无空格），但字符串字面量保留原样。
内容与 npm 版 `cli.js` 完全一致。

## 等长替换

二进制有固定偏移量。改变字节长度会导致后续所有内容错位损坏。

### 技术：注释填充

```python
prefix = b'return!0/*'
suffix = b'*/}catch{return!0}'

def build_replacement(original_length):
    padding = original_length - len(prefix) - len(suffix)
    assert padding >= 0
    return prefix + (b' ' * padding) + suffix
```

### 常见替换模式

| 原始模式 | 替换 | 效果 |
|---------|------|------|
| `return!1` | `return!0` | false -> true |
| `return!0` | `return!1` | true -> false |
| `if(check){action}` | `if(!1   ){action}` | 跳过 action |
| `condition&&action` | `!1       &&action` | 禁用 action（空格填充） |

## 正则设计

### 容忍变量名变化

Minifier 每次构建都会重命名变量。绝不硬编码变量名：

```python
# 正确：匹配任意 JS 标识符
rb'\.includes\(([A-Za-z_$][A-Za-z0-9_$]*)\)'

# 错误：硬编码变量名
rb'\.includes\(Xe\)'
```

### 锚定稳定字符串

字符串字面量、属性名和结构模式在 minify 后仍然保留：

- `"api.anthropic.com"` — 字符串字面量
- `.includes(` — 方法调用
- `}catch{` — 控制流结构
- `return!1` / `return!0` — 布尔返回

### 正则结构

```python
target_re = re.compile(
    rb'<稳定前缀>'
    rb'(<可变部分>)'
    rb'<稳定后缀>'
)
```

## 三态检测

每个补丁需要两个正则：

1. `target_re` — 匹配未补丁代码（原始代码）
2. `patched_re` — 匹配已补丁代码（替换后的代码）

状态判断逻辑：
- `target_re` 匹配 -> "unpatched" -> 可安全应用
- `patched_re` 匹配 -> "patched" -> 跳过
- 都不匹配 -> "unknown" -> **不操作**（版本不兼容）

## 平台注意事项

### Windows
- 运行中的 `.exe` 不能覆写但**可以**重命名
- 用 `os.replace()` 而非 `os.rename()`（后者在 Windows 上目标存在时报错）
- 流程：写入 tmp -> replace exe 为 old -> replace tmp 为 exe

### macOS
- 修改后的二进制需要 ad-hoc 重签名：`codesign --force --sign - <binary>`
- 不重签名会被 Gatekeeper 拦截

## 发现补丁目标的流程

### 在 cli.js 中搜索

```bash
# 按关键词搜索并显示上下文
python search_target.py <cli.js> "keyword"

# 多关键词搜索扩大范围
python search_target.py <cli.js> "api.anthropic.com"
python search_target.py <cli.js> "isAllowedDomain"
```

### 格式化后分析

```bash
cp cli.js /tmp/cli-formatted.js
npx prettier --write /tmp/cli-formatted.js
# 格式化后按行号读取特定段落
```

### 测试正则是否匹配

```bash
python validate_patch.py \
  --target-re '<regex>' \
  --file <cli.js>
```

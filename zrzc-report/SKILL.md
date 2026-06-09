---
name: zrzc-report
description: 生成准入准出报告。自动提取项目上下文、TAPD 信息，通过 GitNexus 分析代码变更影响范围，按规则识别各类改动，填充模版并输出飞书文档 Markdown。触发词：准入准出、ZRZC、变更分析报告。
---

# 准入准出报告生成

## 前置条件

以下依赖在 **Step 0（环境检查与自动安装）** 中自动检测并尽可能自动配置。首次运行时 Step 0 会引导完成全部设置，后续运行若检测通过则快速跳过。

- Git 仓库环境（当前工作区或用户提供的目标仓库）
- Node.js v22 / npm / npx — 自动检测，缺失时**强制安装**（锁定 v22，不得安装其他版本）
- GitNexus CLI v1.6.5（`npx gitnexus`）— **强制安装**（锁定版本，依赖 Node.js v22）
- MCP 服务：`user-gitnexus`、`user-tapd` — 不可用时引导用户配置或降级
- `lark-feishu` skill + 飞书凭证 — 自动安装并使用内置默认凭证（可选，用于上传）
- `config.json` — 不存在时自动从 `config.example.json` 生成

## 工作流总览

```
Task Progress:
- [ ] Step 0: 环境检查与自动安装
- [ ] Step 1: 读取配置
- [ ] Step 2: 提取项目上下文
- [ ] Step 3: 用户输入 PRD 链接与需求标题
- [ ] Step 4: 用户确认参数
- [ ] Step 4b: 多工程识别与确认
- [ ] Step 5: 变更分析（对每个工程：建 GitNexus 索引 → Git 收窄 → GitNexus 分析 → 合并多工程结果；降级时用 Cursor 本地分析）
- [ ] Step 6: 规则识别与分类
- [ ] Step 6b: 收窄自检（commit 归属 + 文件范围验证，不通过则阻塞）
- [ ] Step 7: 填充模版
- [ ] Step 8: 输出飞书文档 Markdown
- [ ] Step 9: （可选）上传飞书 / 上报结果
```

---

## Step 0: 环境检查与自动安装

> 首次运行执行完整检查；后续运行若所有探测通过则快速跳过（目标 < 5 秒）。
> **Node.js 和 GitNexus CLI 是必需依赖**——安装失败时必须循环重试或引导用户手动安装，**不得跳过**。只有 MCP 服务探测和 lark-feishu 安装失败时才允许降级处理。

### 0a. 基础环境（Git + Python + Node.js）

**并行**执行：

```bash
git --version
python3 --version
node --version 2>/dev/null || echo "NODE_MISSING"
npx --version 2>/dev/null || echo "NPX_MISSING"
```

- Git 或 Python 任一缺失 → 报错终止，提示用户安装。
- Node.js / npx 缺失 → 进入**强制安装流程**（见下方）。**安装成功才能继续**，不得跳过。

#### Node.js 自动安装流程（强制）

> **版本要求**：必须安装 **Node.js v22**（与 gitnexus@1.6.5 的 `engines.node >=22.0.0` 要求保持一致）。

当 `node` 或 `npx` 命令不可用、或 `node --version` 主版本不是 22 时，按以下优先级尝试自动安装：

**策略 1：nvm（推荐，跨平台通用）**

> 本步骤依赖 Node.js / npx。如果 Step 0a 标记 `NODE_AVAILABLE=false`，直接标记 `GITNEXUS_CLI=false` 并跳过。

```bash
if command -v nvm &>/dev/null; then
  nvm install 22
  nvm use 22
fi
```

如果 `nvm` 本身也不存在，先安装 nvm 再安装 Node.js v22：

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm install 22
nvm use 22
```

**策略 2：Homebrew（macOS）**

```bash
if command -v brew &>/dev/null; then
  brew install node@22
  brew link --overwrite node@22
fi
```

**策略 3：系统包管理器（Linux）**

```bash
# 使用 NodeSource 安装指定版本
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
```

**安装后验证**

每次安装尝试后，必须重新验证版本号满足要求：

```bash
node --version    # 必须为 v22.x
npx --version
```

若验证通过，继续后续步骤。

**若所有自动安装策略均失败 → 阻塞流程**，使用 AskQuestion 向用户报告并**循环等待**：

```
⛔ Node.js 是 GitNexus 分析的必需依赖，无法跳过。
自动安装未成功，请手动安装 Node.js v22：

  • 推荐：curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash && nvm install 22
  • macOS：brew install node@22
  • 下载：https://nodejs.org/en/download/ （选择 v22）

安装完成后输入「重试」。
```

用户回复「重试」后重新执行验证。**不提供「跳过」选项**——Node.js 缺失将导致 GitNexus 完全不可用，必须安装。

### 0b. GitNexus CLI（强制安装，锁定版本）

> Node.js v22 已在 Step 0a 中确认可用，本步骤安装 **gitnexus@1.6.5**（与包声明的 `engines.node >=22.0.0` 保持一致）。
> **禁止安装其他版本**——其他版本未经验证，可能存在兼容性问题。

**检测是否已安装且版本正确**：

```bash
INSTALLED_VERSION=$(npx gitnexus --version 2>/dev/null)
if [ "$INSTALLED_VERSION" = "1.6.5" ]; then
  echo "GITNEXUS_OK"
else
  echo "GITNEXUS_NEED_INSTALL"
fi
```

如果输出 `GITNEXUS_NEED_INSTALL`（未安装 或 版本不是 1.6.5），执行全局安装：

```bash
npm install -g gitnexus@1.6.5
```

安装后重新验证版本：

```bash
npx gitnexus --version    # 必须输出 1.6.5
```

**若安装失败**（网络不通等），**不得跳过**，使用 AskQuestion 向用户报告并循环等待：

```
⛔ GitNexus CLI 安装失败，这是代码分析的必需工具，无法跳过。

请检查网络连接后手动执行：
  npm install -g gitnexus@1.6.5

安装完成后输入「重试」。
```

用户回复「重试」后重新执行验证。**安装成功才能继续**。

> **栈溢出防护**：后续所有 `npx gitnexus analyze` 命令必须附加 `NODE_OPTIONS` 增大栈空间（见 Step 5b 及 GitNexus CLI 速查表）。

### 0c. MCP 服务探测

对以下三个 MCP server **逐个**发送轻量探测调用，判断可用性：

| MCP Server | 探测方式 | 必需？ |
|-----------|---------|--------|
| `user-gitnexus` | `CallMcpTool: user-gitnexus / list_repos` | 是（核心分析工具） |
| `user-tapd` | `CallMcpTool: user-tapd / get_api_story_getTapdStory`（测试关键词探测） | 否（可降级到脚本/推断） |

**探测结果处理**：

- **可用** → 标记 `MCP_XXX=true`，继续
- **不可用**（连接失败 / server 未配置） → 使用 AskQuestion 向用户说明：

```
检测到 MCP server「{server_name}」未配置或不可用。
该服务用于 {用途说明}。

如果你已有该 MCP server 的配置信息，请提供：
- server 类型（command / sse / streamable-http）
- 启动命令或 URL

如果暂时没有，可跳过——后续步骤会自动降级处理。
输入「跳过」继续。
```

- 用户提供配置 → 指导用户添加到 MCP 配置文件（Cursor: `.cursor/mcp.json`；Claude Desktop: `claude_desktop_config.json`），然后重新探测
- 用户选择跳过 → 标记 `MCP_XXX=false`，记录在环境状态中，后续步骤按降级路径处理

**关键约束**：`user-gitnexus` 不可用时**不阻塞**流程启动——Step 5b 会尝试通过 CLI (`npx gitnexus`) 建索引后重新探测。但应向用户明确警告分析质量可能受限。

### 0d. lark-feishu skill 检测与安装

按优先级查找 `feishu_doc_api.py`：

```bash
for path in \
  ~/.cursor/skills/lark-feishu/scripts/feishu_doc_api.py \
  .cursor/skills/lark-feishu/scripts/feishu_doc_api.py \
  ; do
  [ -f "$path" ] && echo "FOUND:$path" && break
done
```

**未找到** → 尝试自动安装：

```bash
# 定位 agent-skills 仓库中的安装脚本
INSTALLER="$(dirname "$(dirname "$(dirname "$(dirname "$(cd "$(dirname "$0")" && pwd)")")")")/scripts/install.sh"
if [ -f "$INSTALLER" ]; then
  bash "$INSTALLER" lark-feishu
fi
```

如果无法自动安装（安装脚本不存在、不在 agent-skills 仓库中等），使用 AskQuestion 提示：

```
lark-feishu skill 未安装。该 skill 用于将报告上传到飞书 wiki。

请通过以下方式安装：
  bash /path/to/agent-skills/scripts/install.sh lark-feishu

或输入「跳过」— 报告将只在本地生成，不上传飞书。
```

安装后验证：

```bash
python3 "<found-lark-feishu-root>/scripts/feishu_doc_api.py" --help
```

记录 `LARK_FEISHU_ROOT` 供 Step 8 使用。

### 0e. 飞书凭证配置

使用 `config.example.json` 中的内置默认凭证（`feishu_app_id` / `feishu_app_secret`），自动设置环境变量：

```bash
export FEISHU_APP_ID=cli_a826a4642939d013
export FEISHU_APP_SECRET='jZmklxffRqKpcia2xJLMfIEVZokKYavJ'
```

如果 `<skill-root>/config.json` 中有自定义的 `feishu_app_id` / `feishu_app_secret`（非空且不等于示例值），优先使用自定义值。

无需询问用户——凭证已内置在配置中。

### 0f. config.json 生成

```bash
[ -f "<skill-root>/config.json" ] && echo "CONFIG_EXISTS" || echo "CONFIG_MISSING"
```

**如果缺失** → 从 example 复制：

```bash
cp "<skill-root>/config.example.json" "<skill-root>/config.json"
```

无需询问用户——默认值足以运行。用户可在 Step 4 参数确认时覆盖特定值。

### 0g. 获取用户邮箱

```bash
git config user.email
```

如果输出为空，使用 AskQuestion 询问用户：

```
未检测到 Git 邮箱配置。请提供你的邮箱地址（用于上报结果通知）：
```

记录 `USER_EMAIL` 供 Step 9 使用。

### 0h. 环境状态汇总

完成所有检查后，**仅当有非 OK 项时**向用户展示环境状态摘要：

```
环境检查完成：
 ✓ Git / Python
 ✓ Node.js v22 / npx
 ✓ GitNexus CLI v1.6.5
 ✓ MCP: user-gitnexus
 ⚠ MCP: user-code-change-analysis（未配置，非 EC 项目将降级处理）
 ✓ MCP: user-tapd
 ✓ lark-feishu skill
 ✓ 飞书凭证
 ✓ config.json
 ✓ 用户邮箱: xxx@xxx.com

继续执行 Step 1...
```

全部通过时不展示摘要，直接进入 Step 1（保持快速）。

---

## Step 1: 读取配置

读取 `<skill-root>/config.json`。如果文件不存在，使用 `<skill-root>/config.example.json` 的默认值。

> `<skill-root>` 指本 SKILL.md 所在目录。

配置结构：

```json
{
  "api_base_url": "https://test-indo-zrzc.fintopia.tech",
  "swim_lane_id": "",
  "default_upload_to_feishu": true,
  "default_send_notify": true,
  "default_parallel": true,
  "feishu_app_id": "cli_a826a4642939d013",
  "feishu_app_secret": "jZmklxffRqKpcia2xJLMfIEVZokKYavJ"
}
```

记录以下变量供后续步骤使用：

| 变量 | 来源 |
|------|------|
| `API_BASE_URL` | `api_base_url` |
| `SWIM_LANE_ID` | `swim_lane_id` |
| `UPLOAD_TO_FEISHU` | `default_upload_to_feishu` |
| `SEND_NOTIFY` | `default_send_notify` |
| `PARALLEL` | `default_parallel` |
| `FEISHU_APP_ID` | `feishu_app_id` |
| `FEISHU_APP_SECRET` | `feishu_app_secret` |

---

## Step 2: 提取项目上下文

在当前工作区根目录**并行**执行以下 Shell 命令：

```bash
git remote get-url origin          # 远程仓库 URL
git branch --show-current          # 当前分支
git branch -a --list '*master' '*main' 2>/dev/null  # base branch 候选
git status --porcelain             # 未提交变更检查
```

### 解析 repo 名称与 Git URL 格式化

| URL 格式 | 示例 | 提取规则 |
|---------|------|---------|
| HTTPS | `https://github.com/org/repo-name.git` | 取最后一段路径，去掉 `.git` |
| SSH | `git@github.com:org/repo-name.git` | 取 `:` 后最后一段路径，去掉 `.git` |

### 确定 base_branch

优先 `master`；`master` 不存在则 `main`。

### 记录未提交状态

`git status --porcelain` 有输出时标记 `HAS_UNCOMMITTED=true`。

---

## Step 3: 用户输入 PRD 链接与需求标题

本步骤不再自动提取 TAPD 信息，改为**由用户主动提供 PRD 链接**作为需求来源。

### 3a. 要求用户提供 PRD 链接

使用 AskQuestion 或直接向用户请求以下信息：

```
请提供本次需求的 PRD 链接（飞书 docx/wiki 链接均可）。
如已知需求标题，也请一并提供；未提供时将在读取 PRD 后自动提取标题。
```

记录：

- `PRD_LINK`
- `TITLE`（若用户已直接提供）

### 3b. 读取 PRD 内容

拿到 `PRD_LINK` 后，读取文档正文，提取：

1. 需求标题
2. 需求背景 / 目标
3. 功能点
4. 涉及的工程、服务、页面或模块

### 3c. 提取需求标题

如果用户未直接提供标题，则按以下优先级确定：

1. PRD 文档标题
2. PRD 正文中的一级标题
3. 分支名转换为可读标题（如 `feature/add-loan-check` → `add loan check`）

---

## Step 4: 用户确认参数

### 必须确认的场景

- `HAS_UNCOMMITTED=true`（有未提交代码，分析范围可能不准确）
- 用户未提供 PRD 链接
- 从 PRD 中未能稳定提取需求标题

使用 AskQuestion 或直接向用户展示参数清单请求确认：

```
准入准出参数确认：
- 仓库名称 (repo): {repo}
- 当前分支 (branch): {branch}
- 基准分支 (base_branch): {base_branch}
- PRD 链接 (prd_link): {prd_link}
- 需求标题 (title): {title}
- 上传飞书: {upload_to_feishu}
- 发送通知: {send_notify}
- 并行执行: {parallel}

⚠️ {提示未提交代码、PRD链接缺失或标题不确定的原因}

请确认以上参数是否正确，或提供修改。
```

### 用户覆盖规则

| 用户指令 | 行为 |
|---------|------|
| "不上传飞书" / "不用发通知" | `upload_to_feishu=false` / `send_notify=false` |
| "只分析不上传" | `upload_to_feishu=false` + `send_notify=false` |
| "上传但不通知" | `upload_to_feishu=true`, `send_notify=false` |
| 用户直接给出 PRD 链接或标题 | 优先使用用户指定的值 |

### 无歧义快速通过

当同时满足以下条件时，可跳过交互确认，但仍需在执行前向用户展示将要使用的参数：

- 已提供唯一 PRD 链接
- 无未提交代码
- 标题已成功获取

---

## Step 4b: 多工程识别与确认

> 一个需求通常涉及多个工程（如主服务 + 依赖服务 + 前端）。本步骤识别所有相关工程并为每个工程准备分析上下文。

### 4b-1. 识别关联工程

按以下来源识别本次需求涉及的所有工程：

1. **PRD 需求描述**：从 PRD 标题、正文描述中提取涉及的服务名（如 `loan-service`、`user-api`、`admin-frontend`）
2. **用户主动提供**：用户在 Step 4 确认参数时可能提供多个工程路径或分支
3. **Git 提交关联**：检查 commit message 中是否引用了其他仓库的分支或 MR
4. **代码依赖推断**：从 pom.xml / build.gradle / package.json 中识别内部依赖的变更

### 4b-2. 用户确认工程列表

使用 AskQuestion 向用户确认本次需求涉及的工程清单：

```
本次需求涉及以下工程（已自动识别）：

| # | 工程名 | 本地路径 | 变更分支 | 状态 |
|---|--------|---------|---------|------|
| 1 | {当前工程} | {PROJECT_ROOT} | {BRANCH} | ✓ 已在工作区 |
| 2 | {推断的关联工程} | ? | ? | ⚠ 需确认路径 |

请确认：
- 是否还有其他涉及的工程？请提供工程名和本地路径。
- 对已识别的工程，请补充本地路径和变更分支（如与主工程不同）。
- 输入「仅当前工程」跳过多工程分析。
```

### 4b-3. 记录多工程上下文

确认后记录 `REPO_LIST`：

```
REPO_LIST = [
  {repo: "project-a", path: "/path/to/project-a", branch: "feature/xxx", base_branch: "master"},
  {repo: "project-b", path: "/path/to/project-b", branch: "feature/xxx", base_branch: "master"},
  ...
]
```

- 第一个工程为**主工程**（当前工作区），后续为**关联工程**
- 如果用户选择「仅当前工程」，`REPO_LIST` 只包含当前工程，后续步骤按单工程执行

---

## Step 5: 变更分析

> **模版中「二、技术方案」部分保持原样留空白，由人工填写。不做任何自动填充。**
> 
> **多工程模式**：当 `REPO_LIST` 包含多个工程时，Step 5b～5c **对每个工程分别执行**，最后在 Step 5f 中合并所有工程的分析结果。GitNexus 为每个工程分别建索引后，`impact` 查询会自动关联已索引的其他工程（跨仓库依赖追踪）。

### 5a. 判断项目类型

判断是否为 EC 项目：

- 仓库名包含 `ec`（如 `ec`、`ec-api`、`ec-admin`、`ec-core`）
- 或远程 URL 路径中包含 `/ec.git` 或 `/ec/`

| 项目类型 | 分析工具 |
|---------|---------|
| EC 项目 | **仅 GitNexus** |
| 非 EC 项目 | **GitNexus**（主路径，降级时用 Cursor 本地分析） |

### 5a-git. 分析顺序（强制，所有项目）

> **⚠️ 绝对禁止跳过**：无论变更多么简单（哪怕只改一行配置），都**必须**按以下顺序执行完整流程。不得因"变更简单"、"调用链清晰"、"手动分析更快"等理由跳过 GitNexus 尝试步骤。agent 不具备自行判断是否需要 GitNexus 的权限——流程合规性优先于效率。

对**所有项目**，必须按以下顺序执行：

1. **GitNexus 索引**：`list_repos` → 若当前目标仓库不在列表中，则必须在**该仓库本地根目录** `${PROJECT_ROOT}` 执行建索引（见 5b），完成后再次确认；不得因「未索引」直接跳过 GitNexus 进入本地分析。
2. **Git 收窄（共同前提）**：执行 **5b-git**，得到 `FEATURE_COMMIT_LIST` 和 `CORE_SYMBOLS`。
3. **GitNexus 主分析**：在 Git 收窄完成且索引已建立或已按 5b 尽力建立的前提下，执行 **5c（GitNexus `impact`/`context`）**。
4. **降级（Step 5e）**：仅当 **已尝试建索引**（含 `npx gitnexus analyze` / 必要时加 `--force`）**且 GitNexus 分析确认失败或无有效结果**时，才允许以 Cursor 本地分析作为**主要依据**。

#### GitNexus 语言支持与已知限制

| 语言 | 支持状态 | 说明 |
|------|---------|------|
| Java | ✓ 完全支持 | 经验证可正常建索引和分析 |
| Go | ✓ 完全支持 | gitnexus@1.6.5 起支持 Go 语言 AST 解析 |
| TypeScript/JavaScript | ✓ 完全支持 | 经验证可正常建索引和分析 |
| Python | ✓ 支持 | 官方支持列表中 |
| Kotlin/C#/Rust/PHP/Ruby/Swift/C/C++/Dart | ✓ 支持 | 官方支持列表中，功能覆盖程度各异 |

> **即使遇到未知语言项目，也必须执行 `npx gitnexus analyze` 并记录结果**，不得预判跳过。

### 5b. GitNexus 索引检查与自动重建（所有项目通用）

**对 `REPO_LIST` 中的每个工程**，必须先检查索引状态，确保分析前索引可用且覆盖当前分支的变更。多个工程的索引检查可**并行执行**。

> 当 `REPO_LIST` 仅包含一个工程时，按单工程流程执行即可。

1. 调用 GitNexus MCP `list_repos` 查看已索引仓库列表：

```
CallMcpTool: user-gitnexus / list_repos
```

2. 判断当前仓库是否在列表中且索引未过时

3. 如果**未索引** → 必须在**目标仓库根目录** `${PROJECT_ROOT}`（用户克隆下来的代码所在路径）运行 CLI **新建索引**，**禁止**在未执行本步骤的情况下认定「GitNexus 不可用」并降级：

```bash
cd ${PROJECT_ROOT}
NODE_OPTIONS='--stack-size=65536' npx gitnexus analyze   # 首次增量索引
```

建索引完成后，**再次**调用 `list_repos`（或 `npx gitnexus status` / `npx gitnexus list`）确认本仓库已出现在索引列表中；若仍未出现，排查路径是否指向正确仓库根目录、CLI 是否报错并重试。

4. **索引完整性验证**（关键步骤）：即使仓库已索引，索引可能基于旧 commit，不包含当前分支新增的类/方法。执行以下验证：

   a. 从 git diff 中提取本次变更**新增的核心类名**（非测试类）
   b. 对每个新增类调用 `impact` 或 `context` 查询
   c. 如果返回 `"Target not found"`，说明本地代码不包含这些符号，**必须先拉取代码再建增量索引**：

```bash
cd ${PROJECT_ROOT}

# 第一步：拉取最新代码，确保本地包含变更分支的内容
git fetch origin ${BRANCH}
git checkout ${BRANCH} 2>/dev/null || git checkout -b ${BRANCH} origin/${BRANCH}
git pull origin ${BRANCH}

# 第二步：拉取完成后，建增量索引即可（无需全量重建）
NODE_OPTIONS='--stack-size=65536' npx gitnexus analyze
```

   d. 重建完成后，重新验证符号是否可查到
   e. 如果重建后仍找不到，标记 `GITNEXUS_INCOMPLETE=true`；**仅针对这些符号**可在 Step 5e 中做补充，**不得**因此跳过 **5d（CCA）**。

5. 如果索引建立**失败**（CLI 报错、权限、磁盘等）→ 记录警告，标记 `GITNEXUS_AVAILABLE=false`。降级到 Step 5e Cursor 本地分析。

> **注意**：
> - 当目标项目不在当前工作区时（如分析远程仓库），需要 `cd` 到项目本地路径。路径可从 `list_repos` 返回的 `path` 字段获取。
> - 拉取代码前先 `git stash` 保存本地未提交的变更，索引完成后 `git stash pop` 恢复。
> - 如果只需要索引而不想切换本地分支，可用 `git fetch origin ${BRANCH}` + `git merge origin/${BRANCH}` 将远程变更合入当前分支后再重建索引。

### 5b-git. Git 收窄（GitNexus 分析的**前提**，必须先执行）

Git 收窄是 **GitNexus 分析（5c）** 的前置步骤。**必须先在本地用 Git 限定「本次需求」涉及的文件与核心符号**，收窄结果用于：
- GitNexus：对收窄后的 `CORE_SYMBOLS` 逐个调用 `impact` / `context`

> **核心原则**：测试分支（test/\*）、集成分支（develop/\*）等常合入多个需求的 commit。**每次分析都必须强制执行 commit 级过滤**，只保留与当前 TAPD 需求相关的提交，再基于过滤后的 commit 列表计算变更文件。**禁止**直接用分支全量 diff 作为分析输入。

1. **拉取远程并计算合并基线**（在 `${PROJECT_ROOT}` 下）：

```bash
git fetch origin ${BASE_BRANCH}
git fetch origin ${BRANCH}
MERGE_BASE=$(git merge-base origin/${BASE_BRANCH} origin/${BRANCH})
```

2. **强制 commit 过滤（每次必须执行）**：

   列出分支上全部 commit（不含 merge commit），然后按需求关键词过滤：

```bash
ALL_COMMITS=$(git log --oneline --no-merges "${MERGE_BASE}..origin/${BRANCH}")
```

   **2a. 构建过滤关键词**：从以下来源提取关键词（大小写不敏感），取并集：

   - TAPD 需求标题中的核心业务词（如「ShopeePay」「打款」「payout」）
   - TAPD 需求 ID（如 `1153182677001336710`）
   - 分支名中的业务标识（如 `shopeepay-code`）

   **2b. 过滤 commit**：

```bash
FEATURE_COMMITS=$(git log --oneline --no-merges "${MERGE_BASE}..origin/${BRANCH}" \
  --grep="<关键词1>" --grep="<关键词2>" --all-match)
```

   若 `--all-match` 过严（结果为空），改为**任一匹配**（去掉 `--all-match`）：

```bash
FEATURE_COMMITS=$(git log --oneline --no-merges "${MERGE_BASE}..origin/${BRANCH}" \
  -i --grep="<关键词1>\|<关键词2>\|<关键词3>")
```

   **2c. 验证过滤结果**：

   - 过滤后 commit 数 > 0 → 继续。
   - 过滤后 commit 数 = 0（关键词无法匹配到任何 commit）→ 使用 AskQuestion 向用户展示全部 commit 列表，要求用户手动确认哪些 commit 属于本次需求。
   - 过滤后 commit 数 = 全部 commit 数（即无过滤效果）→ 向用户确认「分支上所有 commit 均属于本次需求」，用户确认后继续，否则要求用户指定。

   **2d. 输出**：将过滤后的 commit hash 列表记为 `FEATURE_COMMIT_LIST`，最老和最新 commit 分别记为 `OLDEST_FEATURE_COMMIT` 和 `NEWEST_FEATURE_COMMIT`。

3. **基于过滤后的 commit 列表计算变更文件**：

```bash
git diff --name-only ${OLDEST_FEATURE_COMMIT}^..${NEWEST_FEATURE_COMMIT}
```

   > **禁止**使用 `${MERGE_BASE}...origin/${BRANCH}` 全量 diff 作为最终文件列表——该命令会包含分支上所有 commit（含其他需求合入的变更），导致分析范围膨胀。仅在步骤 2 过滤确认「分支上所有 commit 均属于本次需求」时，才可使用全量 diff。

4. **过滤噪声路径**（默认排除，不参与「核心符号」提取）：

   - `**/src/test/**`、`**/*Test.java`、`**/generated/**`、`**/specs/**`（SDD 文档目录）等。

5. **从剩余文件中提炼核心符号清单**（控制在约 **5～20 个**，优先）：

   - 新增/大改的 **public class** 名；
   - 带 `@RestController` / 映射注解的 **Controller** 类；
   - 实现 `IAppResourceParamResolve`、`*FilterRuleProcessor` 等与入口链相关的类。

   将清单记为 `CORE_SYMBOLS`，后续 **只对 `CORE_SYMBOLS` 逐个调用 GitNexus**，不要对整份 `detect_changes` 返回逐条展开。

6. **可选**：在范围已极小时，可额外调用一次 `detect_changes`（`compare`）与 Git 文件列表**交叉校验**是否漏文件；**禁止**在未收窄的情况下依赖「整包 `detect_changes` 输出」填写报告。

### 5c. EC 项目分析（仅 GitNexus）

1. **以 Git 收窄结果为主**：对 **5b-git** 得到的 `CORE_SYMBOLS` 中每个符号，**逐个**分析影响范围（`impact` 为主；`detect_changes` 不作为必填输入）。

```
CallMcpTool: user-gitnexus / impact
  target: "${symbol_from_CORE_SYMBOLS}"
  direction: "upstream"
  maxDepth: 5
  includeTests: false
  repo: "${REPO}"
```

2. **获取关键符号上下文**（对高风险、或 `impact` 结果不完整的核心符号）：

```
CallMcpTool: user-gitnexus / context
  name: "${symbol_name}"
  repo: "${REPO}"
```

3. **`detect_changes`（compare）的使用方式**（可选，非默认主路径）：

   - 仅当 Git 收窄后文件很少、或需要与图数据库结论对账时使用。
   - 调用方式：

```
CallMcpTool: user-gitnexus / detect_changes
  scope: "compare"
  base_ref: "${BASE_BRANCH}"
  repo: "${REPO}"
```

   - **必须**在本地已 `checkout` 到 `${BRANCH}` 且与 `origin/${BRANCH}` 一致（或索引已覆盖该分支），否则对比范围可能错位、返回无关变更。
   - 若返回体过大：**不要全文解析**；仅与 **5b-git** 的文件列表对照是否遗漏，或直接跳过，以 `impact(CORE_SYMBOLS)` 为准。

4. 汇总所有 `impact` 结果，按 depth 分组，并映射到「变更入口」规则（仅接口 / 定时任务 / 中间件，见 Step 5e / Step 6）：
   - d=1 → 直接影响（在入口定义下）
   - d=2～5 → 间接影响（调用链层级上限 5 层）

### 5d. 多工程结果合并

> 当 `REPO_LIST` 仅包含一个工程时跳过本步骤。

对 `REPO_LIST` 中每个工程分别执行 5b-git（Git 收窄）和 5c（GitNexus 分析）后，将各工程的分析结果合并：

1. **合并 `CORE_SYMBOLS`**：各工程的核心符号列表取并集，标注来源工程
2. **合并 `impact` 结果**：
   - GitNexus 在多仓库已索引时会**自动返回跨仓库影响**（如工程 A 的方法被工程 B 调用）
   - 对跨仓库影响，标注调用方所属工程
3. **去重**：同一入口（接口/Job/MQ Consumer）如从多个工程分析到，只保留一条，标注关联的变更工程
4. **分类**：合并后仍按直接影响/间接影响分类

合并后输出统一的影响范围结果，供 Step 6 规则识别和 Step 7 填充模版使用。

### 5e. Cursor 本地分析降级

本节是**最后手段**，仅当 **GitNexus 主路径已尽力**（含在 `${PROJECT_ROOT}` 执行 `npx gitnexus analyze`，必要时加 `--force`，仍无法得到足够符号级结论或 `GITNEXUS_AVAILABLE=false`）时，才允许**主要依赖**本节完成准入准出中的「变更入口 / 调用链」类结论。

> **⚠️ 再次强调**：以下任何理由都**不构成**跳过 GitNexus 尝试步骤而直接使用本节的正当理由：
> - "变更很简单，只改了几行"
> - "调用链手动就能追踪清楚"
> - "手动分析效率更高"
> - "已知该语言可能不支持"
>
> **必须先执行 `npx gitnexus analyze`，确认失败后才能进入本节。**

**允许使用本节作为主要依据的触发条件**：

1. **索引已尝试建立**：已在目标仓库根目录执行过 `npx gitnexus analyze`（及按需 `--force`），仍无法覆盖分析所需符号或 GitNexus 工具持续不可用。
2. **合并判断**：在上述尝试之后，仍无法从 GitNexus 结果中归纳出变更入口与影响范围。

**不属于降级、不得跳过硬性步骤的情形**：

- `list_repos` 中暂无目标仓库 → 应先在 `${PROJECT_ROOT}` **新建索引**（5b），而非直接本节。
- GitNexus 索引成功但部分符号 not found → 应优先以 GitNexus `impact`/`context` 已有结果为主撰写报告。
- 变更简单 / 调用链清晰 → **不构成**跳过理由，必须走完整流程。

**补充性使用（可与主路径并存）**：对个别 `Target not found` 的符号，在 GitNexus 已跑完的前提下，可用本节**补充**单点调用链，但不替代 5b～5c 的必选流程。

#### 第一步：获取变更 diff

```bash
git diff ${BASE_BRANCH}...HEAD --name-only
git diff ${BASE_BRANCH}...HEAD
```

#### 第二步：提取变更方法

从 diff 中提取所有变更的方法签名（Java: 方法定义行；JS/TS: function/class；Python: def/class）。

#### 第三步：调用链路分析（最多 5 层）

对每个变更方法，使用 Cursor 的代码搜索能力（Grep/SemanticSearch/Read）**向上追踪调用链**，逐层寻找调用者，直到找到**入口层**或达到 5 层上限。

**入口层定义**（仅以下三类算作入口）：

| 入口类型 | 识别特征 |
|---------|---------|
| **接口（API）** | `@RequestMapping`、`@GetMapping`、`@PostMapping`、`@PutMapping`、`@DeleteMapping`、`@RestController`、Dubbo `@Service` 暴露方法、Feign 接口定义 |
| **定时任务（Job）** | `@Scheduled`、`@XxlJob`、`XXL-Job handler`、`ScheduledExecutorService`、Quartz Job |
| **中间件（MQ Consumer）** | `@KafkaListener`、`@RabbitListener`、`MessageListener`、Kafka Consumer、RocketMQ Consumer |

#### 第四步：确定影响范围

对找到的每个入口，**向下分析该入口的完整调用链路**（最多 5 层），标注本次变更方法在链路中的位置，构成影响范围。

#### 第五步：分类直接/间接影响

| 类型 | 定义 |
|------|------|
| **直接影响入口** | 变更方法本身就是入口（接口/定时任务/中间件），或变更方法没有更上层的调用者 |
| **间接影响入口** | 变更方法通过中间层被某个入口间接调用 |

---

## Step 6: 规则识别与分类

读取 `<skill-root>/change-analysis-rules.md`，按照其中定义的规则对 Step 5 的分析产物进行逐项识别和分类。

### 识别清单

| 识别维度 | 对应规则章节 | 模版目标位置 |
|---------|------------|------------|
| MySQL 数据库改动 | 3.1 | 三-1. 配置变更表 → MySQL 行 |
| Redis 缓存改动 | 3.2 | 三-1. 配置变更表 → Redis 行 |
| Kafka 消息队列改动 | 3.3 | 三-1. 配置变更表 → Kafka 行 |
| 定时任务 Job 改动 | 3.4 | 三-1. 配置变更表 → 并发控制行（酌情） |
| 配置改动 | 3.5 | 三-1. 配置变更表 → 配置项行 |
| 接口改动 | 3.6 | 三-4. 变更入口（直接/间接） |
| 配置类改动（⚠️ 双重影响） | 3.7 | 三-1/3/4/5 多处（需全链路追踪） |

### 直接影响 vs 间接影响分类

| 类型 | 定义 | 来源 |
|------|------|------|
| **直接影响入口** | 变更方法本身就是入口（接口/定时任务/中间件），或变更方法无更上层调用者 | GitNexus depth=1；CCA 一级调用者；Cursor 本地分析 |
| **间接影响入口** | 变更方法通过中间层被入口间接调用 | GitNexus depth=2+；CCA 多级调用链；Cursor 向上追踪 |

> **入口仅包含三类**：接口（API）、定时任务（Job）、中间件（MQ Consumer）。不要列举中间方法，只列举最终的入口。调用链路最多分析 5 层。

### 3.7 配置类改动特别处理

当变更涉及以下类型时，**必须**进行配置流全链路检查：

- `*Config`、`*Payload`、`*Setting` 类
- `*Request`、`*DTO` 请求体类
- `*VO`、`*Response` 响应体类
- 配置枚举类
- `Model`/`Entity`/`Record` 数据库映射类

检查路径：配置时影响（管理后台模块）→ 存储 → 运行时影响（核心业务模块/定时任务/消息消费），避免遗漏跨模块影响。

---

## Step 6b: 收窄自检（填充模版前必须通过）

> 本步骤是**强制关卡**，在所有分析完成、准备填充模版之前执行。自检不通过则**禁止**进入 Step 7。

### 检查项 1：commit 过滤是否已执行

确认 5b-git 步骤 2 已执行，且存在有效的 `FEATURE_COMMIT_LIST`：

- `FEATURE_COMMIT_LIST` 非空 → 通过
- `FEATURE_COMMIT_LIST` 为空或未定义 → **阻塞**，回退到 5b-git 步骤 2 执行 commit 过滤

### 检查项 2：提交记录归属验证

逐条审查 `FEATURE_COMMIT_LIST` 中的每个 commit message，判断是否**全部**与当前 TAPD 需求相关：

1. 列出 `FEATURE_COMMIT_LIST` 全部 commit（`git log --oneline`）
2. 对每条 commit message，与 TAPD 需求标题中的**核心业务词**进行匹配
3. 标记匹配结果：

| 结果 | 处理 |
|------|------|
| 全部匹配 | 通过，继续 Step 7 |
| 存在不匹配的 commit（如其他需求混入） | 使用 AskQuestion 向用户展示疑似不属于本需求的 commit 列表，要求确认：<br>- 用户确认「属于本需求」→ 保留<br>- 用户确认「不属于」→ 从 `FEATURE_COMMIT_LIST` 中移除，重新计算变更文件和 `CORE_SYMBOLS`，然后**重新执行 Step 5c/5d 和 Step 6** |

### 检查项 3：变更文件与 commit 一致性

确认最终用于报告的变更文件列表**全部来源于 `FEATURE_COMMIT_LIST` 中的 commit**，而非分支全量 diff：

```bash
# 过滤后 commit 范围的文件列表
FILTERED_FILES=$(git diff --name-only ${OLDEST_FEATURE_COMMIT}^..${NEWEST_FEATURE_COMMIT})

# 如果分析过程中使用了全量 diff 的文件列表，必须在此步骤替换为 FILTERED_FILES
```

若发现报告中引用了 `FILTERED_FILES` 以外的文件（即其他需求引入的变更），必须剔除后再进入 Step 7。

### 自检通过后输出

```
✓ 收窄自检通过：
  - commit 过滤已执行，共 {N} 个需求相关提交
  - 全部提交已确认归属本次需求
  - 变更文件列表与过滤后 commit 一致
继续执行 Step 7...
```

---

## Step 7: 填充模版

> **⚠️ 强制约束：本步骤生成的报告必须严格遵循 `<skill-root>/template.md` 的结构和格式。**
> - **章节顺序**：必须与 `template.md` 完全一致，禁止增删、合并或调换章节
> - **标题层级**：必须与 `template.md` 的 `##` / `###` / `####` 层级一一对应
> - **表格列名**：每张表格的列名必须与 `template.md` 中的定义完全一致，禁止自行增删或重命名列
> - **表格行数**：`template.md` 中预定义的行（如配置变更的 MySQL/Redis/Kafka 等）必须全部保留，无改动的行填"无"
> - **留空章节**：`template.md` 中标注"人工填写"的章节（如"技术方案"）必须保持留空，禁止自动填充
> - **禁止自由发挥**：禁止在模版结构之外添加额外章节、注释、说明段落或总结性文字

**操作步骤**：先读取 `<skill-root>/template.md` 获取完整模版结构，然后按以下规则将分析结果填充到对应章节。

### 一、需求内容

```markdown
## 需求内容

TAPD链接：{tapd_link}
需求标题：{title}
分支信息：
变更分支: {branch}
基准分支: {base_branch}

### 提交记录

{仅列出 5b-git 步骤 2 过滤后的 FEATURE_COMMIT_LIST，而非分支全量 commit。
 若过滤确认分支上所有 commit 均属于本次需求，可使用 git log ${BASE_BRANCH}..HEAD --oneline --no-merges。}
```

### 二、技术方案

**保持模版原样，留空白给人工填写。不做任何自动填充。**

```markdown
## 二、技术方案

### 技术方案

本次需求技术方案摘要：_（人工填写）_
关键设计点：_（人工填写）_
依赖与风险：_（人工填写）_
```

### 三、变更内容与影响范围

#### 1. 配置变更

根据 Step 6 识别的 MySQL/Redis/Kafka/外部服务/配置项/并发控制改动，填充配置变更表：

```markdown
| 依赖类型 | 具体内容 | 影响说明 | 风险点 |
|----------|---------|---------|-------|
| MySQL | {识别结果或"无新增或修改数据库表结构"} | {影响说明} | {风险等级} |
| Redis | {识别结果或"无直接Redis缓存改动"} | {影响说明} | {风险等级} |
| Kafka | {识别结果或"无新增Topic或消费组"} | {影响说明} | {风险等级} |
| 外部服务 | {识别结果或"无Feign/Dubbo接口变更"} | {影响说明} | {风险等级} |
| 配置项 | {识别结果} | {影响说明} | {风险等级} |
| 并发控制 | {识别结果或"无新增分布式锁或限流"} | {影响说明} | {风险等级} |
```

无改动的行**保留**，内容填写"无"并标注"低"风险。

#### 2. 变更方法

从 Step 5 的变更方法列表填充。

#### 3. 变更入口

变更入口**仅列举入口级别**（接口/定时任务/中间件），不要列举中间方法。

- **3.1 变更入口-直接影响**：变更方法本身就是入口，或变更方法没有更上层调用者
- **3.2 变更入口-间接影响**：变更方法通过中间层被某个入口间接调用，列出该入口及其向下到变更方法的调用链路

#### 4. 变更业务范围

- **4.1 变更业务范围-直接影响**：直接受影响的业务域和入口
- **4.2 变更业务范围-间接影响**：间接受影响的业务域和入口

#### 5. 前端页面入口

结合变更入口、接口路径和需求描述，填充前端页面入口表：

- **页面**：受影响的前端页面或路由，如项目详情页、团队管理页、生成任务页
- **功能点**：用户在该页面触发的业务功能
- **操作路径**：从页面进入并操作到该功能的步骤
- **调用接口**：该功能最终调用的后端 API / RPC / callback 接口
- **说明**：补充影响范围、直接/间接关系或无法确认原因；无前端入口时保留表格并填「-」

### 四、上线顺序及观察指标

保持模版骨架结构，表格中的具体内容留空（由人工在上线时填写）：

- 4.1 上线及回滚方案 → 保留表格结构，内容留空
- 4.2 上线后观察 → 保留监控表格结构，观测结果列留空

---

## Step 7b: 模版结构校验（上传前必须通过）

> 本步骤是**强制关卡**，在 Step 7 填充完成后、Step 8 上传飞书之前执行。校验不通过则**禁止**上传。

### 校验方法

读取 `<skill-root>/template.md`，逐项比对 Step 7 生成的报告 Markdown，按以下清单检查：

### 检查项 1：章节完整性

确认报告包含 `template.md` 中的**所有章节标题**（按出现顺序）：

| 序号 | 必须存在的章节标题 |
|------|-------------------|
| 1 | `## 需求内容` |
| 2 | `## 二、技术方案` |
| 3 | `## 三、变更内容与影响范围` |
| 4 | `### 1. 配置变更` |
| 5 | `### 2. 变更方法` |
| 6 | `### 3. 变更入口` |
| 7 | `#### 3.1 变更入口-直接影响` |
| 8 | `#### 3.2 变更入口-间接影响` |
| 9 | `### 4. 变更业务范围` |
| 10 | `#### 4.1 变更业务范围-直接影响` |
| 11 | `#### 4.2 变更业务范围-间接影响` |
| 12 | `### 5. 前端页面入口` |
| 13 | `## 四、上线顺序及观察指标` |
| 14 | `### 4.1 上线及回滚方案` |
| 15 | `### 4.2 上线后观察` |

- 缺少任何章节 → **阻塞**，补全后重新校验
- 出现 `template.md` 中不存在的额外章节 → **阻塞**，删除后重新校验

### 检查项 2：表格列名一致性

对比报告中每张表格的列名与 `template.md` 中对应表格的列名：

| 章节 | template.md 中的列名 |
|------|---------------------|
| 配置变更 | 依赖类型 \| 具体内容 \| 影响说明 \| 风险点 |
| 变更方法 | 模块 \| 方法数 \| 变更类型 \| 说明 |
| 变更入口-直接影响 | 类型 \| 名称 \| 方法签名 \| 变更类型 |
| 变更入口-间接影响 | 类型 \| 名称 \| 说明 |
| 变更业务范围-直接影响 | 业务域 \| 入口/方法 \| 说明 |
| 变更业务范围-间接影响 | 业务域 \| 入口/方法 \| 说明 |
| 前端页面入口 | 页面 \| 功能点 \| 操作路径 \| 调用接口 \| 说明 |
| 大盘监控 | 监控维度 \| 核心指标 \| 监控链接 \| 观测时长 |
| 观测指标 | 平台 \| 监控维度 \| 核心指标说明 \| Check项 \| 监控链接 \| 观测时长 \| 预期结果 \| 观测结果 |

- 列名不匹配（增删/重命名） → **阻塞**，按 `template.md` 修正后重新校验

### 检查项 3：留空章节未被自动填充

确认以下章节**仅保留标题和模版骨架**，未被自动填充具体内容：

| 章节 | 要求 |
|------|------|
| 二、技术方案 | 仅保留"_（人工填写）_"占位文本 |
| 4.1 上线及回滚方案 | 保留表格骨架，内容留空 |
| 4.2 上线后观察 | 保留表格骨架，观测结果列留空 |

- 发现自动填充了应留空的章节 → **阻塞**，清除填充内容后重新校验

### 校验通过后输出

```
✓ 模版结构校验通过：
  - 全部 {N} 个章节完整且顺序正确
  - 全部表格列名与 template.md 一致
  - 留空章节未被自动填充
继续执行 Step 8 输出飞书文档 Markdown...
```

---

## Step 8: 输出飞书文档 Markdown

将 Step 7 生成的报告以**飞书文档兼容的 Markdown 格式**直接输出给用户。

### 8a. 保存报告文件

将完整报告 Markdown 写入本地文件：

```bash
REPORT_FILE="<skill-root>/output/${TITLE}-准入准出报告.md"
mkdir -p "<skill-root>/output"
```

将 Step 7 生成的完整 Markdown 内容写入 `${REPORT_FILE}`。

### 8b. 输出给用户

向用户展示：

1. 报告文件路径
2. 完整的 Markdown 内容（可直接复制粘贴到飞书文档）

```
✓ 准入准出报告已生成：
  文件路径：${REPORT_FILE}

报告内容如下（可直接粘贴到飞书文档）：

---
{完整报告 Markdown 内容}
---
```

### 8c.（可选）上传飞书

如果用户配置了 `upload_to_feishu=true` 且 `lark-feishu` skill 可用，可以自动上传：

> `<lark-feishu-root>` 指 `lark-feishu` skill 的安装目录。

```bash
export FEISHU_APP_ID=cli_a826a4642939d013
export FEISHU_APP_SECRET='jZmklxffRqKpcia2xJLMfIEVZokKYavJ'

python3 "<lark-feishu-root>/scripts/feishu_doc_api.py" create_sibling_doc "<参照文档_wiki_token>" "${TITLE}-准入准出报告" --file "${REPORT_FILE}"
```

上传成功 → 向用户展示飞书文档链接。上传失败 → 不阻塞，报告已在本地生成。

---

## Step 9:（可选）上报结果

仅当 Step 8c 上传飞书成功后，才将报告信息上报到准入准出服务。如果未上传飞书，跳过本步骤。

### 9a. 构建请求参数

| 参数 | 来源 |
|------|------|
| `repo_name` | Step 2 解析的仓库名称 |
| `branch_name` | Step 2 获取的当前分支 |
| `email` | Step 0g 获取的用户邮箱（`USER_EMAIL`） |
| `feishu_url` | Step 8d 创建文档后返回的飞书文档链接 |

### 9b. 发送上报请求

```bash
curl --location '${API_BASE_URL}/api/external/record-and-notify' \
  --header 'Content-Type: application/json' \
  --data-raw '{
    "repo_name": "${REPO}",
    "branch_name": "${BRANCH}",
    "email": "${USER_EMAIL}",
    "feishu_url": "${FEISHU_DOC_URL}"
  }'
```

### 9c. 结果处理

- **成功**（HTTP 2xx） → 记录完成，向用户展示最终结果：飞书文档链接 + 上报成功
- **失败** → 记录警告但不阻塞，向用户展示飞书文档链接 + 上报失败提示（报告已上传，仅通知未触发）
- **`upload_to_feishu=false`** → 跳过本步骤（无飞书链接可上报）

---

## MCP 工具速查

| MCP Server | 工具名 | 用途 |
|-----------|--------|------|
| `user-gitnexus` | `list_repos` | 列出已索引仓库 |
| `user-gitnexus` | `detect_changes` | 检测变更并映射到符号和执行流 |
| `user-gitnexus` | `impact` | 分析单个符号的影响范围（按 depth 分组） |
| `user-gitnexus` | `context` | 获取符号 360° 视图（调用者、被调用者、所属流程） |
| `user-gitnexus` | `query` | 搜索代码知识图谱的执行流 |
| `user-tapd` | `get_api_story_getTapdStory` | 根据链接或 ID 查询 TAPD 需求详情 |

## lark-feishu skill 命令速查

飞书上传通过 `lark-feishu` skill 的本地 Python 脚本完成（非 MCP），以下为 Step 8 涉及的核心命令：

| 命令 | 用途 |
|------|------|
| `feishu_doc_api.py read_wiki "<url>"` | 读取 wiki 文档内容和结构 |
| `feishu_doc_api.py create_sibling_doc "<ref>" "标题" --stdin` | 在参照文档同级创建新 wiki 文档并写入内容 |
| `feishu_doc_api.py update "<docId>" --stdin` | 覆盖写入文档内容 |
| `feishu_doc_api.py update "<docId>" --file "<path>"` | 从文件写入文档内容 |
| `feishu_api.py login` | OAuth 登录（确保文档 owner 正确） |

## GitNexus CLI

```bash
npx gitnexus status                                        # 检查索引状态
NODE_OPTIONS='--stack-size=65536' npx gitnexus analyze     # 增量索引
NODE_OPTIONS='--stack-size=65536' npx gitnexus analyze --force  # 强制全量重建
npx gitnexus list                                          # 列出所有已索引仓库
```

> **栈溢出防护**：`gitnexus analyze` 在大型 Java 仓库上会进行深度递归的 AST 解析和调用链追踪，默认 Node.js 栈空间可能不足。所有 `analyze` 命令**必须**附加 `NODE_OPTIONS='--stack-size=65536'`。`status`、`list`、`mcp` 等非分析命令无需此参数。

## 边界情况

| 场景 | 处理方式 |
|------|---------|
| 非 Git 仓库 | 报错终止，提示用户在 Git 仓库中运行 |
| 无 remote URL | 报错终止，提示配置 `git remote` |
| Node.js / npx 缺失 | Step 0a 自动安装（Homebrew → nvm → 系统包管理器），全部失败则提示用户手动安装 Node.js v22 |
| 无 TAPD 链接 | Step 4 中要求用户手动提供 |
| 多个 TAPD 链接 | Step 4 中展示列表让用户选择 |
| 有未提交变更 | Step 4 中警告用户，建议先提交代码 |
| 测试/集成分支含多需求 commit | 5b-git 步骤 2 强制按需求关键词过滤 commit；过滤后为空则要求用户手动确认；过滤后等于全量则向用户确认后继续。**禁止**跳过过滤直接用全量 diff |
| GitNexus 索引缺失 | 在目标仓库根目录 `${PROJECT_ROOT}` 执行 `NODE_OPTIONS='--stack-size=65536' npx gitnexus analyze` 建立索引，确认后再分析；**禁止**未建索引即降级 |
| GitNexus 索引不完整（新增符号 not found） | 先拉取代码（`git fetch` + `checkout` + `pull`），再执行 `NODE_OPTIONS='--stack-size=65536' npx gitnexus analyze` 增量索引，完成后再验证 |
| GitNexus 索引失败 | 标记 `GITNEXUS_AVAILABLE=false`，降级到 Step 5e Cursor 本地分析 |
| `npx gitnexus analyze` 栈溢出 | 确认已附加 `NODE_OPTIONS='--stack-size=65536'`；若仍溢出则尝试 `--stack-size=131072`；确认 Node.js 版本为 v22（`node --version`）且 gitnexus 版本为 1.6.5（`npx gitnexus --version`），版本不匹配时按 Step 0a/0b 重新安装 |
| 飞书上传失败 | 不阻塞，报告已在本地生成为 Markdown 文件 |
| 飞书凭证未配置 | Step 0e 自动使用内置默认凭证；如需自定义可在 `config.json` 中覆盖 `feishu_app_id` / `feishu_app_secret` |
| lark-feishu skill 未安装 | Step 0d 自动安装；若自动安装失败，提示用户手动安装或跳过（报告仅本地生成） |
| 上报接口失败 | 记录警告但不阻塞，飞书文档已上传成功，仅通知未触发 |
| 用户邮箱未配置 | Step 0g 从 `git config user.email` 获取；获取不到则询问用户 |
| 飞书目标目录下无子文档 | 提示用户提供一个参照文档 URL，或手动在目标目录下先创建一个空文档 |

## 输出约束

> **核心原则：`template.md` 是报告的唯一结构标准，任何偏离都视为错误。**

1. 报告正文**不得**出现工具名（GitNexus）、模式编号、降级过程等内部信息
2. **（强制）** 所有章节标题、层级结构、表格列名**必须**与 `template.md` 完全一致——不得增删章节、不得调换顺序、不得重命名列
3. **（强制）** 生成报告前**必须**先读取 `template.md`，以其结构为骨架填充内容；禁止凭记忆或推理自行构建报告结构
4. **（强制）** 输出报告前**必须**通过 Step 7b 模版结构校验，校验不通过则禁止输出
5. 无改动的配置类型行保留，内容填"无"，风险填"低"
6. 「二、技术方案」**必须**留空给人工填写
7. 「四、上线顺序及观察指标」保持骨架，具体内容留空
8. 翻译和实验相关表格始终保留标题和表头，无改动则填「-」
9. **（强制）** 禁止在模版结构之外添加额外章节、注释段落、总结性文字或"补充说明"

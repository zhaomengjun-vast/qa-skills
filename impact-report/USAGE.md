# 影响范围评估报告 Skill 使用说明

## 一、这个 Skill 是做什么的

`impact-report` 是一个自动生成「影响范围评估报告」的 Claude Code / Cursor Skill。给定一个需求 PRD 和对应的代码仓库，它会：

1. 读取 PRD，提取需求内容（背景、目标、功能点、涉及工程）；
2. 通过 GitNexus 对代码变更做影响面分析（变更入口、调用链、直接/间接影响）；
3. 按规则识别各类改动（数据库、缓存、消息队列、配置、接口、定时任务等）；
4. 映射需要回归的任务与页面触发路径（区分算法类 / 非算法类）；
5. 按固定模版填充报告，并上传到飞书 wiki。

## 二、前置环境

Skill 的 Step 0 会自动检测并尽量自动安装，首次运行按引导完成即可：

| 依赖 | 说明 | 缺失时 |
|------|------|--------|
| Git | 代码仓库环境 | 报错终止 |
| Node.js v22 | GitNexus 依赖，锁定 v22 | 自动装（nvm/brew/包管理器） |
| GitNexus CLI v1.6.5 | 代码影响面分析核心工具 | 自动 `npm i -g gitnexus@1.6.5` |
| 飞书 CLI（lark-cli） | 读取 PRD、上传报告 | `npx @larksuite/cli@latest install` |
| 飞书 CLI 用户授权 | **必需前置**，读 PRD 和上传都要 | 引导 `lark-cli auth login`（浏览器授权） |

> 飞书授权是硬性前置：很多 PRD 文档必须用个人授权（user_access_token）才能读取，未授权会阻塞流程。首次使用请先完成 `lark-cli auth login`。

## 三、安装 Skill 到本地

Skill 仓库：`https://github.com/zhaomengjun-vast/qa-skills`

### 方式一：克隆整个仓库

```bash
git clone git@github.com:zhaomengjun-vast/qa-skills.git
```

`impact-report/` 目录即为本 Skill。

### 方式二：放到 Skill 目录

将 `impact-report/` 目录放到你的工具 Skill 目录下：

- Claude Code：`~/.claude/skills/impact-report/`
- Cursor：`~/.cursor/skills/impact-report/`

```bash
# 示例：克隆后拷贝到 Claude Code 的 skills 目录
git clone git@github.com:zhaomengjun-vast/qa-skills.git
cp -r qa-skills/impact-report ~/.claude/skills/impact-report
```

安装后重启或刷新 AI 工具的 UI，使其识别新 Skill。

### 目录结构

```
impact-report/
├── SKILL.md                 # Skill 主流程（Step 0~9）
├── template.md              # 报告模版（结构标准，勿随意改结构）
├── change-analysis-rules.md # 各类改动识别规则
├── regression-mapping.md    # 回归任务与触发路径映射规则
├── config.json              # 运行配置（飞书 wiki 地址等）
├── config.example.json      # 配置示例
├── scripts/impact_api.py      # 上报接口客户端
└── output/                  # 生成的报告
```

## 四、配置

`config.json` 关键项：

```json
{
  "api_base_url": "https://test-indo-zrzc.fintopia.tech",
  "default_upload_to_feishu": true,
  "default_send_notify": true,
  "feishu_wiki_url": "https://a9ihi0un9c.feishu.cn/wiki/xxxxxxxx"
}
```

- `feishu_wiki_url`：报告上传的目标飞书 wiki 节点（报告会作为其子/同级文档创建）。改成你团队的目标 wiki 即可。
- 飞书访问凭证由 `lark-cli` 的用户授权管理，**无需**在 config 里配置 app_id / app_secret。

## 五、使用方法

在 Claude Code / Cursor 中，用自然语言触发 Skill（触发词：**影响范围评估 / impact / 变更分析报告**），并提供三项必需输入：

1. **产品文档 PRD**（飞书 docx / wiki 链接）
2. **本次需求改动的代码地址（本地）**——本地仓库根目录路径
3. **分支**——本次需求所在分支

> 三项缺一不可，缺失会阻塞等待补齐。

### 提示词模版

```
用 impact-report 生成影响范围评估报告。
PRD：<飞书 PRD 链接>
代码仓库：<本地仓库路径>，分支：<分支名>
严格按照 skill 步骤执行，不要遗漏步骤。
```

### 多工程示例（前端 + 后端）

```
用 impact-report 生成影响范围评估报告。
PRD：https://xxx.feishu.cn/docx/xxxxxxxx
前端代码仓库：/Users/you/IdeaProjects/tripo-app-flutter，分支：main
后端代码仓库：/Users/you/IdeaProjects/app-server，分支：master
严格按照 skill 步骤执行，不要遗漏步骤。
```

Skill 会在 Step 4b 识别多工程，对每个工程分别做 GitNexus 分析后合并结果。

## 六、执行流程（Step 0~9）

| 步骤 | 做什么 |
|------|--------|
| Step 0 | 环境检查与自动安装（Node/GitNexus/飞书 CLI/授权/config） |
| Step 1 | 读取配置 |
| Step 2 | 收集三项输入（PRD+代码地址+分支），读取并提取 PRD 内容 |
| Step 4 | 用户确认参数（仓库、分支、上传选项等） |
| Step 4b | 多工程识别与确认 |
| Step 5 | 变更分析：GitNexus 索引（先查后建，已建增量/未建全量）→ Git 收窄 → 影响分析 → 多工程合并 |
| Step 6 | 规则识别与分类（DB/缓存/MQ/配置/接口/定时任务） |
| Step 6b | 收窄自检（commit 归属 + 文件范围验证） |
| Step 6c | 回归任务与触发路径映射（算法类 / 非算法类） |
| Step 7 | 按 template.md 填充报告（H1 = 需求名 + 影响范围评估） |
| Step 7b | 模版结构校验（章节、列名、留空章节，不通过禁止上传） |
| Step 8 | 保存本地 Markdown + 上传飞书 wiki |
| Step 9 | （可选）上报结果到影响范围评估服务 |

## 七、输出

- **本地文件**：`impact-report/output/{需求名}-影响范围评估报告.md`
- **飞书文档**：上传到 `feishu_wiki_url` 指定节点，返回文档链接

报告结构（严格对齐 template.md）：

1. 需求内容（含提交记录）
2. 技术方案（人工填写，自动留空）
3. 变更内容与影响范围
   - 配置变更 / 变更方法 / 变更入口（直接·间接）/ 变更业务范围（直接·间接）/ 前端页面入口
   - 需要回归的任务以及触发路径（**6.1 算法类** / **6.2 非算法类**）
4. 上线顺序及观察指标（骨架留空，上线时人工填）

## 八、常见问题

| 现象 | 原因 / 处理 |
|------|------------|
| 读取 PRD 返回 `forBidden` | 飞书未授权或授权过期 → 执行 `lark-cli auth login` 重新授权 |
| GitNexus 全量重建很慢 | 已索引仓库只做增量；仅首次或索引损坏才需 `analyze --force` |
| Node 版本不对 | 必须 v22；用 `nvm use 22` 切换 |
| 分支不存在 | 会在 Step 4 提示，按实际存在的分支确认 |
| Step 9 上报 403 | git 邮箱未授权 → 用已授权邮箱（`git config user.email`）后重跑上报；不影响报告已生成与上传 |
| 报告只在本地、没上传飞书 | 检查 `default_upload_to_feishu` 与飞书授权状态 |

## 九、注意事项

- 报告结构以 `template.md` 为唯一标准，Step 7b 会强制校验，不通过禁止上传。
- 「技术方案」「上线顺序及观察指标」为人工填写区，生成时自动留空。
- 算法类回归（6.1）仅适用于含 3D 模型生成任务的工程；纯用户体系 / 后端 / 配置类需求该表填「不涉及」。

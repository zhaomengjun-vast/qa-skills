# 回归任务与触发路径映射规则

> 本文件供 SKILL.md 的「Step 6c: 回归任务与触发路径映射」读取，用于把代码变更影响面落到**可执行的回归用例**与**真实页面触发路径**，最终填充 `template.md` 的「三-6. 需要回归的任务以及触发路径」。
>
> 核心原则：
> - 优先用**真实页面触发**；只有页面无法构造时才落到接口 / 脚本触发，并在「页面操作步骤」中注明。
> - 每条回归项必须同时写清「为什么要回归」和「怎么触发」，方便测试同学直接执行。
> - 保留代码事实（route、package、endpoint、TaskType、workflow、worker task、关键参数），再补一段白话说明对应的用户动作。
> - 不要只列文件名，每个结论都要落到入口、调用链、任务名或页面触发动作。

---

## 1. 映射算法任务和前端路径

从「变更入口 / 调用链」出发，按下面这条主链路逐段查证，把后端提交映射到算法 workflow / worker task：

```text
页面组件
-> 前端 service/*.ts endpoint
-> 后端 handler/routes
-> 后端 logic/operation 方法
-> 后端 Submit*Task（训练/任务客户端）
-> model.TaskType / request.task_type
-> 算法 main.py /add_* endpoint
-> 算法 task_util.py send_task_to_Celery()
-> workflows.yml 中的 workflow
-> workers/tasks/<task>.py execute_task()
```

### workflow 名推导

算法侧 workflow 名由 `send_task_to_Celery(data, function_name)` 推导：

- `data["model"]` 是版本号（如 `v3.1-20260211`、`v3.0-20250812`、`Nexus-v1.0-20260214`）。
- `function_name` 中间段转为 workflow，例如 `add_image2model_task` → `image2model`。
- 若 `<version>:<workflow>` 不存在，会 fallback 到 `default`。

### worker 子任务影响判定

| 改动位置 | 回归判定 |
|---|---|
| `workers/tasks/<name>.py` | 回归所有在 `workflows.yml` 引用 `<name>` 的 workflow；覆盖其上游输入和下游消费 |
| `utils/task_conditions.py` | 回归使用该 `condition_*` 的 workflow 分支；至少覆盖 True / False 两侧 |
| `utils/task_util.py` | 回归 workflow 构建、queue、估时、priority；选 2-3 条代表性完整任务 |
| `tripo_workflows/workflows.yml` | 回归被改 workflow 的完整 DAG、条件跳过、并行 GROUP、最终 gather |
| `workers/worker_utils/*` | 回归所有调用该 util 的 worker task；关注 S3/Redis/Kafka/文件锁/上传回调 |
| `workers/worker_config.py` | 回归任务名、队列名、worker 启动和下游 task_info 读取 |
| 后端 `training_server/client.go` | 回归对应 `Submit*Task` 的后端 API 和算法任务入参 |
| 前端 `service/*.ts` | 回归页面触发、请求体、错误 / 轮询 / 状态展示 |

---

## 2. 前端公共包与官网回归映射

私有包 monorepo（`@xxx/*` 公共包）做影响分析时：先按 `packages/*/package.json` 的真实 `exports` 定位，再看 `src/**/index.ts` 和消费方；README / llmdoc 与代码冲突时**以代码为准**，包版本也以 `package.json` 为准，不要照抄陈旧文档版本。

### 公共包入口与回归路径（示例口径）

| 包 | 实际入口 / exports | 重点消费 / 回归路径 |
|---|---|---|
| `utils` | `.` / `./date` / `./resource` | 被 auth/design/engine 内部依赖；外部消费上传、下载、日期初始化、文件后缀、登录跳转。改 `resource` 重点看上传分片 `partUpload` |
| `auth` | `.`（core）/ `./ui` / `./vite` | `TripoAuth`、`fetchSessionToken`、登录页 / 弹窗、Vite exclude/include；改 `./vite` 要回归登录 UI 是否被 UnoCSS 扫到 |
| `design` | `.` / `./config` / `./nuxt` / `./preset` / `./style.css` | 消费方页面组件渲染、主题 token、UnoCSS preset、Nuxt 集成、全局样式（注意 `!important` 覆盖） |
| `engine` | `.`（core/ecs/pipeline/...）/ `./vue` | 3D 预览 / 3D tools 的 `Canvas/createEngine/useEngine`、scene/camera/control、ECS system、资源释放、移动端性能 |
| `fingerprint` | `.` | 设备 ID 稳定性、隐私 / 遥测关闭、SSR / 浏览器边界、被 trace 依赖 |
| `trace` | `.` | 广告归因、UTM、去重、remote config、transport、首访 / 重复访问上报；确认真实消费方是否仍直接 import |
| `doc` | VitePress 私有包（不发布） | 文档站、demo、API 生成；改 public API 时检查 doc src 与 `gen-api-docs` 是否同步 |

### 跨包级联拓扑（按真实 runtime dependency 判断）

| 改动来源 | 内部级联 | 外部回归 |
|---|---|---|
| `utils` | auth、design、engine | 上传 / 下载 / 后缀 / 登录跳转 / engine event bus |
| `fingerprint` | trace | 设备 ID、dedupe hash、浏览器 source 稳定性 |
| `auth` | doc + 外部消费方 | 登录弹窗 / 页面、OIDC、token/session、Vite plugin |
| `design` | doc + 外部消费方 | Nuxt module、UnoCSS preset/config、dialog/toast、通用组件 |
| `engine` | doc + 外部消费方 | 3D workspace、3D tools、WebGL/context/dispose |
| `trace` | doc + 外部真实消费方 | remote config、UTM、第三方埋点是否仍由业务层直接使用 |

发布 / 版本类改动（`.changeset/**`、`packages/*/package.json`）：回归包版本、内部依赖级联、`exports`/`types`、build/prepack、私有 registry 发布路径。

### 官网（Nuxt 项目）按真实路由和服务端入口拆

| 页面 / 模块 | 代码入口（口径） | 影响面与回归触发 |
|---|---|---|
| 首页 / 营销页 | `pages/index.vue`、营销组件、首页内容 JSON | 首屏、响应式、CTA、埋点上报、内容多语言。触发：打开 `/` 与 `/{locale}` → 点主 CTA |
| 功能页（catch-all slug） | `pages/features/[...slug].vue`、对应 server api、CMS adapter | CMS feature-pages、多段 slug、404、preview cookie、SEO、JSON-LD。触发：单段 / 多段 slug、切 locale、CMS preview |
| Use Cases / Hub-Spoke / GEO | `pages/use-cases/[...slug].vue`、相关 server api/utils | hub/spoke 路由、GEO landing、内部链接、canonical、sitemap。触发：hub 页、spoke 详情、导航接口 |
| Blog / Research | `pages/blog/**`、`pages/research/**`、对应 server api、MDX 组件、content | 文章 / MDX 渲染、目录、tag/category、redirect、局部样式、公式 / 代码块。触发：文章详情、分类列表、旧 URL 301 |
| 3D 工具页（viewer/convert） | `pages/3d-tools/**`、对应组件、worker/WASM | `pair` 参数解析、无效值 301、dialog 打开、移动端浮动按钮、SEO。触发：通用页、单格式页、上传合法 / 超大 / 不支持文件 |
| 统一登录 | `pages/login/**`、login 相关 composable、auth 插件、routeRules/devProxy | `/login` 与 `/{locale}/login`、iframe 模式、postMessage、OIDC popup/redirect、CSP frame-ancestors、auth-proxy。触发：全页登录、iframe、移动端 OIDC、非法 redirect |
| SEO / sitemap / preview / revalidate | `use-seo`、`server/routes/{sitemap,robots,llms}`、`server/api/{preview,revalidate}` | meta 默认值、OpenGraph/Twitter、JSON-LD、sitemap 分片、CMS Live Preview、CDN 刷新、IndexNow。触发：页面 head、sitemap/robots/llms URL、CMS webhook、preview cookie |
| i18n / locale redirect | `i18n/locales`、locale redirect middleware、router options | 前缀策略、多 locale、loginOnly locale、语言切换、滚动缓存。触发：默认 / 非默认语言、loginOnly 路径、切换后滚动 / SEO |

---

## 3. 常用回归任务与页面触发

下表把常见算法任务映射到「真实页面触发 → endpoint → 后端提交 → 算法 task_type/workflow → 关键参数」。生成报告时按本次变更命中的行裁剪，并补足页面操作步骤。

| 回归对象 | 前端页面触发 | Endpoint | 后端提交 | 算法 task_type / workflow | 关键参数 |
|---|---|---|---|---|---|
| 文生模型 | Workspace → Generate → Text to Model → Generate | `/v2/studio/operation/text_to_model` 或 `/image-prompt-model` | `SubmitTextToModelTask` | `text_to_model` / `text2model` | `model_version`, `prompt`, `texture`, `pbr`, `geometry_quality`, `generate_parts`, `quad` |
| 图生模型 | Workspace → Generate → Image to Model → 上传单图 → Generate | `/v2/studio/operation/image_to_model` | `SubmitImageToModelTask` | `image_to_model` / `image2model` | `image`, `enable_image_autofix`, `texture`, `pbr`, `texture_quality`, `generate_parts` |
| 多视图建模 | Workspace → Generate → Multi View → 上传≥2 张图 → Generate | `/v2/studio/operation/multiview_to_model` | `SubmitMultiviewToModelTask` | `multiview_to_model` / `mv2model` | `image[]`, `texture`, `pbr`, `geometry_quality`, `generate_parts` |
| 批量图生模型 | Workspace → Generate → Batch Images → 上传多图 → Generate | `/v2/studio/operation/batch_image_to_model` | 多次 / 批量 `SubmitImageToModelTask` | `image_to_model` / `image2model` | `image[]`, `texture_quality`, batch 数量 |
| 贴图生成 | Workspace → Texture → 文本 / 图片 / 多视图贴图 → Generate Texture | `/v2/studio/operation/texture_model` | `SubmitTextureTask` | `texture_model` / texture workflow | `prompt_text`, `image`, `images`, `part_names`, `texture_quality`, `texture_alignment` |
| PBR 生成 | Workspace → Texture PBR → Generate | `/v2/studio/operation/pbr_generate` | `SubmitPbrTask` | `texture_model` / `pbr` | `project_id`, `model_version` |
| 贴图超分 | Workspace → Texture Upscale → 选质量 → Generate | `/v2/studio/operation/texture_upscaler` | `SubmitTextureUpscalerTask` | `texture_model` / texture upscaler | `texture_quality` |
| 自动绑定 | Workspace → Rigging → Auto Rig | `/v2/studio/operation/pre_rig_check` then `/rigging_model` | `SubmitAnimatePreRigCheckTask`, `SubmitAnimateRigTask` | `animate_prerigcheck`, `animate_rig` | `rig_type`, `model_version` |
| 动作迁移 | Workspace → Rigging → Retarget → 选动作 → Apply | `/v2/studio/operation/retarget_model` | `SubmitAnimateRetargetTask` | `animate_retarget` | `animations`, `rig_type` |
| 分 part | Workspace → Segmentation → 选粒度 → Segment | `/v2/studio/operation/ai_segmentation` | `SubmitMeshSegmentationTask` | `mesh_segmentation` / `mesh2part`, `image2segmentation` | `segmentation_granularity` |
| 分 part 保存 | Workspace → Segmentation → 编辑后保存 | `/v2/studio/operation/modification` | `SubmitMeshModificationTask` | `mesh_modification` | `modification_type=apply_indices` |
| 补洞 / 补全 | Workspace → Fill Parts → 选 part → Complete/Fill | `/v2/studio/operation/ai_completion` 或 `/mesh_fill` | `SubmitMeshCompletionTask`, `SubmitMeshFillTask` | `mesh_completion`, `mesh_fill` | `part_names` |
| 重拓扑 / 减面 | Workspace → Retopology/Remesh → Submit | `/v2/studio/operation/remesh` | `SubmitHighpolyToLowpolyTask` 或 `SubmitConvertTask` | `highpoly_to_lowpoly`, `convert_model` | `face_limit`, `quad`, `smart_poly` |
| 生图 | Workspace → Generate Image → 输入 prompt → Generate | `/v2/studio/image/gen_image_v2` | image logic → `SubmitTextToImageTask` | `text_to_image` | `model_version`, `prompt`, `amount`, `resolution`, `scale`, `template_id` |
| 生多视图图 | Workspace → Generate Image → 单图卡片 → Generate Multiview | `/v2/studio/image/gen_multiview` | image logic / consumer | `image2multiview` | `image`, `if_upload` |

### 条件分支覆盖

分析 `workflows.yml` 时，把回归拆成「主链路 + 条件开关」：

| 条件 / 参数 | 触发方式 |
|---|---|
| `condition_texture` | Generate 页开启 Texture；Texture 页直接生成贴图 |
| `condition_pbr` | 开启 Texture 后再开启 PBR |
| `condition_highres` | `texture_quality` 选 detailed/extreme 等高清路径 |
| `condition_geometry_detailed` | Generate 页选 `v3.1` 且 Geometry Quality = Detailed |
| `condition_poly` | Generate 页选 quad / smart poly / low poly 配置 |
| `condition_mesh2part` / `condition_mesh2part_v2` | 开启 Generate Parts 或进入 Segmentation 页 |
| `condition_image_autofix` | 图生模型开启 image autofix，使用需修复 / 去背景的输入 |
| `condition_autosize` | 使用 autosize 输入，让 workflow 包含 `image_caption` autosize |
| `condition_render_image_*` | 完整生成并检查最终预览图 / 渲染输出 |
| `condition_postprocess` | 选 stylize / postprocess 路径或确认 workflow 包含该条件 |

如果某个条件函数本身被修改，必须给出至少一个 True 用例和一个 False 用例。无法从页面稳定触发 False 分支时，注明需接口级构造请求。

---

## 4. 回归优先级与裁剪

| 优先级 | 范围 |
|---|---|
| P0 | 变更直接命中的 workflow/task/核心 route/package，以及用户主路径可触发的失败风险 |
| P1 | 同一 worker util、同一 condition、同一 TaskType 家族、同一公共包消费方的相邻路径 |
| P2 | 展示、轮询、历史记录、导出 / 下载、SEO 非关键字段、非核心状态刷新 |

生成「三-6. 需要回归的任务以及触发路径」时：

- **先把回归对象分两类**填到对应子表：
  - **6.1 算法类任务**：命中算法 workflow / worker task 的对象，范围固定为 §3 表中的文生模型、图生模型、多视图建模、批量图生模型、贴图生成、PBR 生成、贴图超分、自动绑定、动作迁移、分 part、分 part 保存、补洞/补全、重拓扑/减面、生图、生多视图。
  - **6.2 非算法类任务**：前端页面 / 公共包（§2）/ 官网回归、登录、埋点、SEO、发布，以及不经算法 workflow 的后端接口 / 配置 / 数据类回归。
- 仅保留本次变更**实际命中**的回归对象，不要把上表整张抄进报告；对应子表无命中时整行填「不涉及」。
- 每行的「页面操作步骤」要具体到可执行的点击 / 输入序列；纯前端改动则落到 route、组件、包、登录 / 埋点 / SEO / 发布路径。
- 「算法任务/前端结果」列：6.1 写 task_type / workflow / worker task；6.2 纯前端改动写预期前端结果（如登录跳转、SEO metadata、trace event、页面渲染）。
- 无法从页面触发时，在「页面操作步骤」注明「需接口 / 脚本触发」并给出 endpoint 与最小请求要点。

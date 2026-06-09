# 影响面评估模版

## 需求内容

TAPD链接：https://a9ihi0un9c.feishu.cn/wiki/HYfwwUCuiis4sKkgRVZcyxQInnd
需求标题：Segmentation v2 1.0版本
分支信息：
变更分支: master/main（已上线）
基准分支: master

### 提交记录

**后端 tripo-studio：**
- 4c0e7fae feat: introduce segmentation granularity parameter for model tasks
- aafe688c Feat: add mesh fill operation and AI segmentation free trial
- 648feaeb feat(ai): add segmentation handler callback
- 8d53b3b0 feat(TrainingServer) 移除MeshSegmentationTask中不必要的默认参数
- 0a02cd57 feat: 更新计费逻辑以跳过 team 用户的 AI Segmentation 和 Ultra Texture 免费试用
- 702dd786 feat(Billing) 添加 ai-segmentation 试用配额旁路逻辑，优化免费用户生成入口体验
- 9205c42c feat(Billing) 添加生成入口复用 ai-segmentation 试用配额功能，优化计费逻辑
- ab03d30e feat(FreeTrial) 精简试用配置，仅保留 AiSegmentation 和 UltraTexture
- 1ef8195e feat(Billing) 全员开放 AI Segmentation 和 Ultra Texture 免费试用
- fc52b482 feat(Billing) 添加 ShouldBypassForGeneratePartsTrial 方法
- 12b8be9d feat(Billing) 添加 ai-segmentation 试用额度预分配逻辑

**前端 fe-tripo-studio：**
- d5a3b7ed feat(segmentation): 新增AI智能分割与快速补面全流程功能
- cf3462c2 feat(segmentation): 添加补全模式选择功能并优化面板
- 5df105d8 feat(segmentation): 新增模型生成部件拆分功能并优化界面
- 06537568 feat(workspace-segmentation): 为分割部件添加多色显示与交互管理
- 6e8e320c feat(segmentation): update segmentation workflow
- 4cffc7a6 feat(step-guide, segmentation, generate): 优化分割工作区分步引导与生成分块试用逻辑
- 3aefcee4 feat(credits/trial): 新增折扣展示组件并提取通用试用逻辑

**算法 algo-server：**
- 4a8dfee feat(segmentation): add image segmentation v2 pipeline
- 8cb1cc8 add version for segmentation

## 二、技术方案

### 技术方案

本次需求技术方案摘要：_（人工填写）_
关键设计点：_（人工填写）_
依赖与风险：_（人工填写）_

## 三、变更内容与影响范围

### 1. 配置变更

| 依赖类型 | 具体内容 | 影响说明 | 风险点 |
|----------|---------|---------|-------|
| MySQL | 无新增或修改数据库表结构 | 代码中涉及数据库查询和更新，但无表结构变更 | 低 |
| Redis | 无直接Redis缓存改动 | 无新增缓存key或缓存策略调整 | 低 |
| Kafka | 新增 Kafka 消费者回调处理：AiSegmentationConsumerHandler 注册于 consumer.go，处理 ai_segmentation 任务回调 | 算法侧完成分割后通过 Kafka 回调通知后端，更新操作状态 | 中，需确认消费组和回调幂等性 |
| 外部服务 | 新增 training_server 调用：SubmitMeshFillTask（mesh_fill_endpoint）；算法侧新增 nano banana 2 API 调用生成分割图 | 后端通过 training_server 提交 mesh_fill 任务到算法；算法调用外部 AI API 生成 2D 分割色块图 | 中，mesh_fill_endpoint 当前为空（暂回落 mesh_completion），需关注算法侧 nano banana 2 可用性 |
| 配置项 | 新增业务配置项：FreeTrialConfig.AiSegmentation（Enabled/MaxCount/PriceId）；billing key: ai_segmentation.basic、mesh_fill.perpart | 控制 AI Segmentation 免费试用次数（全员 3 次）和计费单价 | 中，配置开关影响计费流程，需确认各环境配置一致 |
| 并发控制 | 新增 batch 入口试用额度预分配逻辑（AcquireAiSegmentationTrialBudget），避免并发场景过度消费配额 | batch 生成场景下多任务并发消费同一份试用额度 | 中，需确认预分配与实际扣减的一致性 |

### 2. 变更方法（表格）
| 模块 | 方法数 | 变更类型 | 说明 |
|----------|---------|---------|-------|
| operation/segmentation_granularity.go | 2 | 新增 | normalizeSegmentationGranularity、resolveGenerateGranularity |
| operation/create_ai_segmentation_logic.go | 2 | 新增 | NewCreateAiSegmentationLogic、CreateAiSegmentation |
| operation/create_mesh_fill_logic.go | 2 | 新增 | NewCreateMeshFillLogic、CreateMeshFill |
| operation/create_image_to_model_logic.go | 1 | 修改 | CreateImageToModel 增加 granularity 参数处理 |
| operation/create_text_to_model_logic.go | 1 | 修改 | CreateTextToModel 增加 granularity 参数处理 |
| operation/create_multiview_to_model_logic.go | 1 | 修改 | CreateMultiviewToModel 增加 granularity 参数处理 |
| operation/create_image_prompt_model_logic.go | 1 | 修改 | CreateImagePromptModel 增加 granularity 参数处理 |
| services/billing.go | 5 | 新增/修改 | ShouldBypassForGeneratePartsTrial、resolveAiSegmentationTrial、CanConsumeAiSegmentationTrial、AcquireAiSegmentationTrialBudget、PrechargeForMeshFill |
| consumer/handler/ai_segmentation.go | 2 | 新增 | OnSuccess、OnFail（AiSegmentationConsumerHandler） |
| training_server/client.go | 1 | 新增 | SubmitMeshFillTask |
| algo: workers/tasks/image2segmentation.py | 1 | 新增 | execute_task（v2 pipeline：render_normal → upload S3 → segmentation API） |
| algo: workers/tasks/mesh2part.py | 1 | 修改 | 新增 segmentation_granularity 参数支持 |


### 3. 变更入口

#### 3.1 变更入口-直接影响
| 类型 | 名称 | 方法签名 | 变更类型 |
|----------|---------|---------|-------|
| 接口（API） | POST /operation/ai_segmentation | CreateAiSegmentationHandler → CreateAiSegmentation | 新增 |
| 接口（API） | POST /operation/mesh_fill | CreateMeshFillHandler → CreateMeshFill | 新增 |
| 接口（API） | POST /operation/image_to_model | CreateImageToModelHandler → CreateImageToModel | 修改（增加 segmentation_granularity 参数） |
| 接口（API） | POST /operation/text_to_model | CreateTextToModelHandler → CreateTextToModel | 修改（增加 segmentation_granularity 参数） |
| 接口（API） | POST /operation/multiview_to_model | CreateMultiviewToModelHandler → CreateMultiviewToModel | 修改（增加 segmentation_granularity 参数） |
| 接口（API） | POST /operation/image_prompt_model | CreateImagePromptModelHandler → CreateImagePromptModel | 修改（增加 segmentation_granularity 参数） |
| 中间件（MQ Consumer） | Kafka: AiSegmentationConsumerHandler | OnSuccess / OnFail | 新增 |

#### 3.2 变更入口-间接影响
| 类型 | 名称 | 说明 |
|----------|---------|---------|
| 接口（API） | POST /operation/batch（batch 生成入口） | 通过 AcquireAiSegmentationTrialBudget 预分配试用配额，间接受计费逻辑变更影响 |
| 接口（API） | GET /marketing/detail | 通过 BillingService 间接受 FreeTrial 配置变更影响（展示试用次数） |

### 4. 变更业务范围

#### 4.1 变更业务范围-直接影响
| 业务域 | 入口/方法 | 说明 |
|----------|---------|---------|
| 3D模型拆分（Segmentation） | POST /operation/ai_segmentation | 新增 AI 智能拆分入口，支持低/中/高粒度控制 |
| 模型补全（Fill/Completion） | POST /operation/mesh_fill | 新增快速封口（Quick Cap）模式，独立计费 |
| 3D模型生成 | POST /operation/image_to_model、text_to_model、multiview_to_model、image_prompt_model | 生成入口增加 generate_parts + segmentation_granularity 参数联动 |
| 计费/试用 | BillingService | AI Segmentation 全员免费试用 3 次，生成入口复用试用配额 |

#### 4.2 变更业务范围-间接影响
| 业务域 | 入口/方法 | 说明 |
|----------|---------|---------|
| Batch 生成 | POST /operation/batch | 并发场景试用额度预分配逻辑变更 |
| 营销/会员 | GET /marketing/detail | 试用次数展示受 FreeTrialConfig 影响 |
| 算法服务 | image2segmentation worker | 新增 v2 pipeline（normal map → nano banana 2 → 分割图），增加 segmentation_granularity 参数传递 |

### 5. 前端页面入口

| 页面 | 功能点 | 操作路径 | 调用接口 | 说明 |
|------|--------|----------|----------|------|
| 生成设置页（Generate Panel） | Generate in parts 粒度选择 | 打开 Generate in parts 开关 → 选择 Low/Medium/High → 点击 Generate | POST /operation/image_to_model（segmentation_granularity） | 新增三档粒度控制，仅 HD Model 下可用 |
| 拆分工作台（Segmentation Workspace） | Detail Level 选择与拆分 | 进入 Segment 模块 → 选择 Low/Medium/High → 点击 Start Segmenting | POST /operation/ai_segmentation | 未拆分模型展示三档选择面板 |
| 拆分工作台（Segmentation Workspace） | Part List 管理 | 拆分完成后 → 左侧展示 Mesh List → 双击重命名/删除/可见性控制 | - | 拆分后展示分割预览图和 Part 列表 |
| 补全工作台（Fill Parts Workspace） | Complete Mode 选择 | 进入补全模块 → 选择 Quick Cap 或 AI Completion → 执行 | POST /operation/mesh_fill | 新增 Quick Cap 模式，免费；AI Completion 不再消耗积分 |
| 生成设置页（Generate Panel） | 免费试用标注 | Generate in parts 开关旁展示 Trial 0/3 角标 | GET /marketing/detail | 免费用户 3 次试用 |

## 四、上线顺序及观察指标

### 4.1 上线及回滚方案

#### 4.1.1 上线方案

**后端服务上线顺序**

| 顺序 | 系统/模块/配置 | 依赖服务/配置 |
|------|--------------|-------------|
| 1 | | |
| 2 | | |
| 3 | | |

**前端服务上线顺序**

| 顺序 | 系统/模块/配置 | 依赖服务/配置 |
|------|--------------|-------------|
| 1 | | |
| 2 | | |
| 3 | | |

#### 4.1.2 方案评估确认（可选简述）

依赖服务：依赖其他服务（如前端依赖对应后端、ec-api 依赖其他后端等）的，写明依赖服务并确认已上线完成。
依赖配置：依赖的配置变更（MySQL、Kafka、代码开关、实验等）；Flyway 需在测试环境验证后再上线。
发布类型：灰度/蓝绿/全量发布，或实验开量；蓝绿可注明分批比例与观测时长（如 10%→50%→100%，每档观测≥5 分钟）。

#### 4.1.3 回滚方案

降级开关：本次功能是否有降级开关及操作方式。
依赖项回滚：是否需依赖服务/配置先回滚，写明依赖的服务或配置。
回滚方式：灰度机器回滚 / 蓝绿回滚 / 全量回滚。

### 4.2 上线后观察

#### 4.2.1 大盘监控

重点关注本次需求涉及的业务及服务核心指标（可按需引用现有 Grafana/APM 等大盘）。

| 监控维度 | 核心指标 | 监控链接 | 观测时长 |
|---------|---------|---------|---------|
| 后端核心监控 | 业务：激活、鉴权、订单；技术：接口 | 如 Grafana/APM 链接 | 10分钟 |
| 后端系统监控 | QPS、CPU、内存、耗时 | 如 Rhino APM 链接 | 10分钟 |
| 前端核心监控(APP/Web) | 业务与可用性 | 如 Grafana 链接 | 1小时 |

无相关监控可填「不涉及」；观测时长按实际约定填写（如 10 分钟、1 小时）。

#### 4.2.2 本次需求上线/实验开量后监控和观测指标

| 平台 | 监控维度 | 核心指标说明 | Check项 | 监控链接 | 观测时长 | 预期结果 | 观测结果 |
|------|---------|------------|---------|---------|---------|---------|---------|
| 后端 | 后端业务监控 | ai_segmentation/mesh_fill 接口调用量、成功率 | | | 10分钟 | | |
| 后端 | 金额核对 | 试用扣款为 0、正常扣款与 billing key 匹配 | | | 10分钟 | | |
| 后端 | 技术监控 | /operation/ai_segmentation、/operation/mesh_fill 接口 QPS、P95、错误率 | | | 10分钟 | | |
| 后端 | 日志 | ai_segmentation 回调成功/失败日志、试用配额消耗日志 | | | 10分钟 | | |
| 后端 | 实验 | - | | | 1小时 | | |
| 前端 | 前端技术监控 | Sentry/Grafana：segmentation 模块报错、量级、性能耗时 | | | 1小时 | | |
| 前端 | 前端业务过程监控 | 拆分流程完成率、Quick Cap 使用率 | | | 1小时 | | |
| 前端 | 神策埋点观察 | detail_level 选择分布、segmentation 功能渗透率 | | | 1小时 | | |

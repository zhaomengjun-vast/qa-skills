# App端 用户体系迁移（Web→App打通） 影响面评估

## 需求内容

TAPD链接：未提供
需求标题：App端 用户体系迁移（Web→App打通）
分支信息：
变更分支: 前端 tripo-app-flutter=main / 后端 tripo-app-service(app-server)=master
基准分支: 无独立基准分支（两仓库均为本次需求新建，全量历史即本次需求范围）

PRD链接：https://a9ihi0un9c.feishu.cn/docx/QUDadRObyo1w5Ix82UucnvnQn2u

### 提交记录

本次需求涉及两个工程，均为需求新建仓库，全部提交属于本次需求：

**前端 tripo-app-flutter（main，32 个提交，节选核心）**

- 8efcf64 Initial Flutter Godot shell integration
- 9aa95a4 feat: 新增 Dio 网络层和 Godot 网络桥（API/CDN/Auth endpoint、JWT 注入、Ory 错误解析、Godot network.* 分发）
- c36cc0a feat: CDN/资源下载接入 Dio 流式下载并打通进度回传
- 6040f2b feat: 设置页接入登录入口（Sign in now + Android HostBridge + host.showLogin）
- a90d3ea feat: 打通设置页邮箱验证码登录全链路
- b685425 feat: 接入 Google 第三方登录（Android Credential Manager → Kratos OIDC）
- 4343647 feat: 重构登录落地页对齐设计稿
- 3f14883 feat: 重构登录流程 UI（落地页/OTP/成功横幅）并打通登录态同步至网络层
- 4ae3812 feat: Google / Apple 登录迁移到 Flutter 插件 && iOS Flutter ↔ Godot 桥接
- 87bfdae refactor: Godot 登录态切换为 Flutter Kratos JWT
- 39eeeb7 迁移对象存储上传，默认走AWS
- 2b8cb96 feat: 接入 App Service profile + JWT 401 自动刷新
- 89c9264 合并 godot&flutter 层的 token 管理逻辑
- 1960abd feat: 绑定页接入 /account/merge，凭证采集走统一桥
- 1a24d66 支持压缩 glb 解析

**后端 app-server / tripo-app-service（master，61 个提交，节选核心）**

- 0eb3d72 first commit / 81004ed feat(init): initial commit
- 1727482 refactor(merge): kratos_uid 全栈重命名为 sub_id
- 3afb824 feat(merge): 引入 merge_status 任务队列 + 后台 worker
- 3ff096e feat(merge): worker 生产级硬化
- fde3d61 feat(merge): /account/merge 支持 dry_run 探测老账号
- 62a7f14 feat(merge): 新增订阅迁移逻辑 mergeSubscription
- 3649b61 feat(merge): case 1.2 支持取消 web 订阅并保留权益
- fbc2d24 feat(merge): 老服务钱包余额按永久/订阅拆分迁移
- 76dce8e feat(merge): 迁移补 op_tags + AccountMerge 加 old_uid/source 双闸门
- 674d955 fix(merge): Google Play 订阅迁移 source_id 对齐 RC base order_id
- ab2d3b9 feat(profile): /user/profile 新增 entitlement 字段
- c30b026 feat(checkin): 实现每日签到完整链路
- cbdaf2c feat(exchange): 实现兑换码核心兑换链路
- d5df3a3 feat(reward): 实现 AppLovin S2S 多环境回调分流网关
- 9aeb6da feat(metrics): 接入 Prometheus 指标 + Grafana dashboard

## 二、技术方案

### 技术方案

本次需求技术方案摘要：_（人工填写）_
关键设计点：_（人工填写）_
依赖与风险：_（人工填写）_

## 三、变更内容与影响范围

### 1. 配置变更

| 依赖类型 | 具体内容 | 影响说明 | 风险点 |
|----------|---------|---------|-------|
| MySQL | PostgreSQL 新建 9 张表：identity_mapping、merge_status、checkin_record、exchange、config、events、submissions、ad_reward、webhook_event_log；含 4 个 ENUM 类型（exchange_status/category、events_status、submissions_status、ad_reward_status）。存储于 appdb；另只读访问 tripodb（Studio 库）用于绑定校验与资产迁移 | 全新用户体系相关表，覆盖账号映射、迁移任务队列、签到、兑换、活动、广告奖励、webhook 幂等日志 | 中，新库新表且承载账号绑定/迁移核心数据，需保证 schema.sql 与 sqlc 生成物一致、索引与幂等约束（UNIQUE old_uid、UNIQUE code、UNIQUE(sub_id,task_id)）正确 |
| Redis | 无直接 Redis 缓存改动 | 服务自身无 Redis 依赖；幂等与缓存下沉到 Tally 计费服务 | 低，无缓存相关改动 |
| Kafka | 无新增 Topic 或消费组 | 未使用 Kafka/MQ；迁移任务采用 merge_status 表作为数据库队列 | 低，无消息队列相关改动 |
| 外部服务 | 新增依赖：Ory Kratos（身份认证/JWT）、Tally（积分/订阅/权益计费）、Studio（项目/支付档案）、HollyMollyApp 老移动服务（账号/任务解析）、AWS S3（资产存储）、AppLovin（S2S 广告回调）、RevenueCat（订阅 webhook，当前 stub） | 登录、积分、会员、订阅、绑定迁移全部依赖上述外部服务；跨服务契约变更会直接影响主链路 | 高，强依赖多个外部服务，Kratos/Tally 契约或可用性异常将阻断登录与付费主链路 |
| 配置项 | config.go 新增大量配置：DBDSN/TripoDBDSN、KratosJWKURL、TallyBaseURL、StudioBaseURL/InternalBaseURL/InternalKey/Origin、OldMobileServiceURL/InternalSK、AdminKey、S3（Endpoint/Region/Bucket/AK/SK）、Ad（EventKey/TxIDPrefix/Ios/Android/RewardCredits/MaxAmountPerEvent/DailyLimit）、S2SGateway（Routes/DefaultUpstream）、Prices、Subscriptions、Entitlement（DownloadPrice/ConvertPrice）、Checkin（Daily/WeeklyPriceID）、MetricsPort；前端 app_env.dart 新增 api/auth/cdn/studio 四类 endpoint 及 staging/production 区分、Google Web/iOS Client ID | 属配置类双重影响：定义于 config.go/YAML/app_env.dart，运行时在中间件、各 logic、S2S 网关、签到/兑换发积分中决定业务行为；密钥、回调路由、价格映射均为高风险配置 | 高，含鉴权密钥、S2S 分流路由、价格/积分映射等高风险项，配置错误会导致鉴权失败、积分错发或回调串环境 |
| 并发控制 | 无分布式锁；迁移 worker 用 PostgreSQL `FOR UPDATE SKIP LOCKED` + visibility_timeout(10min) 实现多副本错峰抢占，签到用 UPSERT 原子校验，兑换用 `SELECT ... FOR UPDATE` 行锁 | 以数据库行级锁/原子 SQL 保证并发安全，非 Redis 分布式锁 | 中，迁移任务重试（最多 5 次、指数 backoff）与幂等依赖 DB 约束，需验证多副本下不重复迁移 |

### 2. 变更方法（表格）
| 模块 | 方法数 | 变更类型 | 说明 |
|----------|---------|---------|-------|
| 后端-账号绑定/迁移 merge | 6+ | 新增 | AccountMerge（双闸门+DryRun）、mergeSubscription（订阅升降级/账单保留 Case1.1/1.2）、StartMigrationWorker/drainOnce/processOne（DB 队列后台 worker）、transferOneTask（老服务资产迁移到 Studio）、ResetMergeBySubID（测试重置） |
| 后端-用户信息 profile | 2 | 新增 | GetProfile（组合 Studio 支付档案 + 绑定状态）、getBindingInfo（查 identity_mapping） |
| 后端-广告奖励 reward | 4+ | 新增 | HandleApplovinS2S（签名校验+积分发放状态机）、RouteS2S/proxyS2S（多环境前缀分流网关）、GetQuota、CreateTransaction/CancelRewardTx |
| 后端-签到 checkin | 2 | 新增 | Checkin（UPSERT 原子签到，day1-6/day7 分档发积分）、GetCheckin（当月累计查询） |
| 后端-兑换 exchange | 1 | 新增 | Exchange（credit/subscription 两类兑换码，行锁+互斥订阅校验） |
| 后端-活动 event | 5 | 新增 | ListEvents/GetEvent/ListSubmissions/MySubmission/CreateSubmission/UpdateSubmission |
| 后端-配置/健康/webhook | 3 | 新增 | GetPublicConfig、Health、RevenueCatWebhook（stub） |
| 后端-中间件 | 2 | 新增 | AuthMiddleware（JWT 解析取 sub、User-Agent 平台识别）、AdminAuthMiddleware（X-Admin-Key 恒定时间比较） |
| 前端-登录鉴权 auth | 8+ | 新增 | AuthController（signInWithGoogle/signInWithApple/submitEmail/submitCode/resendCode/exchangeSession/refreshJwt/restore/logout/mergeAccount）、AuthApi（Kratos flow 封装）、SessionStore（secure storage）、google/apple_auth_bridge |
| 前端-网络层 core/network | 5+ | 新增 | DioClient、ApiClient、AuthInterceptor（JWT 注入+401 自动刷新去重）、UserAgentInterceptor、DownloadService（流式下载+进度）、ImageUploadService（AWS SigV4 直传 S3） |
| 前端-桥接 bridge | 3+ | 新增 | FlutterBridge（native↔Dart 分发）、GodotNetworkBridge（network.* 请求/下载/上传，JWT 注入）、PlatformServicesBridge（凭证采集） |

### 3. 变更入口

#### 3.1 变更入口-直接影响
| 类型 | 名称 | 方法签名 | 变更类型 |
|----------|---------|---------|-------|
| 接口 | POST /account/merge | merge.AccountMergeHandler → AccountMergeLogic.AccountMerge | 新增 |
| 接口 | GET /account/merge/progress | merge.MergeProgressHandler → MergeProgressLogic.MergeProgress | 新增 |
| 接口 | POST /internal/merge/reset (Admin) | merge.ResetMergeHandler → ResetMergeLogic.ResetMerge | 新增 |
| 接口 | GET /user/profile | profile.GetProfileHandler → GetProfileLogic.GetProfile | 新增 |
| 接口 | POST /user/checkin | checkin.CheckinHandler → CheckinLogic.Checkin | 新增 |
| 接口 | GET /user/checkin | checkin.GetCheckinHandler → GetCheckinLogic.GetCheckin | 新增 |
| 接口 | POST /user/exchange/:code | exchange.ExchangeHandler → ExchangeLogic.Exchange | 新增 |
| 接口 | GET /reward/quota | reward.GetRewardQuotaHandler → GetRewardQuotaLogic.GetRewardQuota | 新增 |
| 接口 | POST /reward/transaction | reward.CreateRewardTxHandler → CreateRewardTxLogic.CreateRewardTx | 新增 |
| 接口 | GET /reward/transaction/:tx_id | reward.GetRewardTxHandler → GetRewardTxLogic.GetRewardTx | 新增 |
| 接口 | DELETE /reward/transaction/:tx_id | reward.CancelRewardTxHandler → CancelRewardTxLogic.CancelRewardTx | 新增 |
| 接口 | GET /event/ , /event/:id , /event/:id/submission | event.ListEvents/GetEvent/ListSubmissions Handler | 新增 |
| 接口 | GET /event/:id/my-submission , POST /event/:id/submission , PUT /event/submission/:id | event.MySubmission/CreateSubmission/UpdateSubmission Handler | 新增 |
| 接口 | GET /config/:key | config.GetPublicConfigHandler → GetPublicConfigLogic.GetPublicConfig | 新增 |
| 接口 | GET /health | system.HealthHandler | 新增 |
| 中间件 | GET /reward/s2s/applovin（AppLovin S2S 回调） | reward.ApplovinS2SHandler → HandleApplovinS2S + RouteS2S 分流网关 | 新增 |
| 中间件 | POST /webhook/revenuecat（RevenueCat 订阅 webhook） | webhook.RevenueCatWebhookHandler（当前 stub） | 新增 |
| 定时任务 | 账号迁移后台 Worker | merge.StartMigrationWorker → drainOnce（每 10s±3s 扫 merge_status(pending)，ClaimPendingMergeTasks → transferOneTask） | 新增 |

#### 3.2 变更入口-间接影响
| 类型 | 名称 | 说明 |
|----------|---------|---------|
| 中间件 | AuthMiddleware | 所有 /user/*、/account/*、/reward/transaction*、鉴权 event 接口经其解析 JWT 取 sub_id；变更影响全部鉴权入口 |
| 中间件 | AdminAuthMiddleware | /internal/merge/reset 经其 X-Admin-Key 校验；AdminKey 为空时返回 404 |
| 外部服务 | Tally 计费 | 被 merge/checkin/exchange/reward 间接调用（MergeCreditsAndSub、GrantCheckinCredits、GrantExchangeCredits/Subscription、GrantAdRewardCredits、CreateSubscriptionFromPlan、CancelPspSubscription 等），Tally 契约变更间接影响全部积分/订阅入口 |
| 外部服务 | Ory Kratos | 前端登录/注册/OIDC/whoami 全链路依赖，JWT 由其签发；影响所有需登录的入口 |
| 外部服务 | HollyMollyApp 老服务 | AccountMerge/transferOneTask 经其 ResolveUser/GetTaskDetail 拉取老账号快照与任务详情 |
| 外部服务 | Studio | GetProfile 与资产迁移经 GetPaymentProfile/CreateProject 间接依赖 |

### 4. 变更业务范围

#### 4.1 变更业务范围-直接影响
| 业务域 | 入口/方法 | 说明 |
|----------|---------|---------|
| 登录注册 | 前端 AuthController + Kratos flow / 后端 AuthMiddleware | 邮箱验证码、Google/Apple/Meta OIDC 登录注册，统一入口页判定 login/registration |
| 账号绑定与迁移 | POST /account/merge、迁移 Worker | 存量 App 设备账号绑定 Web 邮箱账号，触发积分/订阅/资产迁移 |
| 积分体系 | POST/GET /user/checkin、POST /user/exchange/:code、/reward/* | 签到发积分、兑换码、广告奖励积分，统一走 Tally Credit Wallet |
| 会员权益/订阅 | mergeSubscription、/user/profile、RevenueCat webhook | 会员方案对齐、订阅升降级与账单保留策略、权益查询 |
| 会话管理 | 前端 SessionStore/AuthInterceptor、whoami | session_token（1 月）换取 JWT（15 分钟）、401 自动刷新、登出 |

#### 4.2 变更业务范围-间接影响
| 业务域 | 入口/方法 | 说明 |
|----------|---------|---------|
| 资产库 | transferOneTask → Studio CreateProject / OSS 迁移 | 绑定后老服务已生成 3D 资产迁移到统一资产库（存储层统一，展示层后续迭代） |
| 广告变现 | RouteS2S 多环境分流网关 | S2S 回调按前缀在多环境/老服务间分流代理，影响广告积分归属与老服务兜底 |
| 运营活动 | /event/*、/config/:key | 投稿活动与公开配置下发，随用户体系接入 |
| 计费一致性 | Tally 订阅/权益/ledger | 迁移与兑换写入的订阅、权益、积分需与 Tally 侧状态保持一致 |

### 5. 前端页面入口

| 页面 | 功能点 | 操作路径 | 调用接口 | 说明 |
|------|--------|----------|----------|------|
| 登录落地页 AuthLandingPage | 品牌主视觉 + Google/Apple/Email 三方登录入口 | Godot 触发 host.ensureLogin → main.dart 打开 AuthLandingPage | GET /self-service/login/api（OIDC flow 创建） | Google 全平台、Apple 仅 iOS；点击进入对应流程 |
| 邮箱验证码页 LoginPage | 邮箱输入 → 验证码输入 → 重发 | 落地页点「Sign in with Email」→ 输入邮箱 → 输入 6 位验证码 | POST /idp-ext/auth/check-identifier；GET/POST /self-service/login\|registration/api | 两步流程，check-identifier 自动路由登录/注册 |
| 账号绑定页 BindingPage | 存量用户绑定 Web 邮箱，采集设备凭证并提交合并 | profile 返回 is_bound=false 自动弹起 → 点「Bind Now」 | POST /account/merge（Header: Bearer JWT, X-Client-Source: mobile_app；Body: device_id / app_transaction_id / purchase_token） | 一次性绑定，成功后刷新 profile |
| 设置页登录入口（Godot 侧） | 头像圆环 + Sign in now 按钮 | Godot 设置页 → host.ensureLogin | 同落地页 | Godot 事件经 HostBridge 转发到 Flutter |
| 主界面登录态（Godot 侧） | 冷启动恢复会话、显示登录态、登出 | App 启动 → auth.restore() → host.authStateUpdated | GET /sessions/whoami?tokenize_as=default_jwt | Godot 监听登录态变化更新 UI |

### 6. 需要回归的任务以及触发路径

#### 6.1 算法类任务

> 算法类任务范围：文生模型、图生模型、多视图建模、批量图生模型、贴图生成、PBR 生成、贴图超分、自动绑定、动作迁移、分 part、分 part 保存、补洞/补全、重拓扑/减面、生图、生多视图。

| 场景用例 | 页面操作步骤 | 前端 endpoint/package | 后端提交 | 算法任务/前端结果 |
|---------|------------|----------------------|---------|------------------|
| 不涉及 | 本需求为 App 用户体系迁移，不含 3D 模型算法生成任务；仅在账号绑定时迁移老服务已生成的资产，不触发任何算法 workflow | - | - | 不涉及 |

#### 6.2 非算法类任务

> 非算法类任务：前端页面 / 公共包 / 官网回归、登录、埋点、SEO、发布，以及不经算法 workflow 的后端接口 / 配置 / 数据类回归。

| 场景用例 | 页面操作步骤 | 前端 endpoint/package | 后端提交 | 算法任务/前端结果 |
|---------|------------|----------------------|---------|------------------|
| 邮箱验证码注册（新用户） | 落地页 → Sign in with Email → 输入未注册邮箱 → 收验证码 → 输入 6 位码 → 进入主页 | check-identifier → GET/POST /self-service/registration/api | 无（经 Kratos） | 注册成功获取 session_token，换取 JWT |
| 邮箱验证码登录（老用户） | 落地页 → Sign in with Email → 输入已注册邮箱 → 输入验证码 → 登录 | check-identifier → GET/POST /self-service/login/api | 无（经 Kratos） | 登录成功获取 session_token |
| Google 登录 | 落地页 → Continue with Google → Google 授权 → 登录 | google_sign_in 取 id_token → POST /self-service/login/api {method:oidc,provider:google} | 无 | 登录/自动注册成功，前端登录态同步 Godot |
| Apple 登录（iOS） | 落地页 → Sign in with Apple → Face ID/Touch ID → 登录 | sign_in_with_apple 取 id_token+nonce → POST /self-service/login/api {method:oidc,provider:apple} | 无 | 登录成功；无邮箱时跳绑定邮箱页 |
| Meta/Facebook 登录 | 落地页 → Meta 登录按钮 → 授权 | id_token → POST /self-service/login/api {method:oidc,provider:facebook} | 无 | 登录成功；无邮箱时跳绑定邮箱页 |
| 三方登录邮箱绑定 | Social Login 无邮箱 → 绑定邮箱页 → 输入邮箱+验证码 | /self-service/*/api（补邮箱） | 无 | 邮箱绑定成功进入主页 |
| Token 换取与 401 自动刷新 | 已登录状态发起任意鉴权请求，JWT 过期时自动刷新 | AuthInterceptor + GET /sessions/whoami?tokenize_as=default_jwt | 无 | 401 触发用 session_token 换新 JWT 并重发原请求；session_token 失效则跳登录 |
| 会话状态检查/登出 | 冷启动恢复；设置页点退出登录 | GET /sessions/whoami；DELETE /self-service/logout/api | 无 | 恢复登录态或清本地 token 跳登录页 |
| 存量账号绑定+迁移 | 存量用户触发登录墙 → 绑定页 Bind Now → 采集 device_id/app_transaction_id/purchase_token → 提交 | POST /account/merge | AccountMerge（双闸门+DryRun）→ merge_status 入队 → 后台 Worker transferOneTask | 绑定成功；积分/订阅合并、资产迁移到 Studio；GET /account/merge/progress 轮询进度 |
| 订阅迁移升降级/账单保留 | 存量用户双端均有订阅时绑定 | POST /account/merge | mergeSubscription（Case1.1 新建 / Case1.2 保护权益+周期末取消 web 订阅） | 保留高价值账单，取消另一端下期账单，权益不中断 |
| 每日签到发积分 | 进入签到页 → 点签到 | POST /user/checkin | CheckinLogic.Checkin（UPSERT 原子，day1-6/day7 分档）→ Tally.GrantCheckinCredits | 签到成功发对应积分；GET /user/checkin 查当月累计 |
| 兑换码（积分/订阅） | 输入兑换码提交 | POST /user/exchange/:code | ExchangeLogic.Exchange（行锁+订阅互斥校验）→ Tally.GrantExchangeCredits/Subscription | 兑换成功发积分或订阅权益 |
| 广告奖励 S2S 回调 | 观看激励广告 → AppLovin 回调 | GET /reward/s2s/applovin | HandleApplovinS2S（签名校验+状态机+日限额）+ RouteS2S 多环境分流 → Tally.GrantAdRewardCredits | 积分发放；非本环境前缀代理到对应环境/老服务兜底 |
| 广告奖励额度/交易 | 进入广告积分页查额度、创建/取消交易 | GET /reward/quota、POST/GET/DELETE /reward/transaction/:tx_id | GetRewardQuota/CreateRewardTx/CancelRewardTx | 显示剩余额度、创建 pending 记录（24h 过期） |
| 用户信息（积分/权益/绑定态） | 进入个人中心 | GET /user/profile | GetProfile（Studio 支付档案 + identity_mapping 绑定态） | 展示会员/权益/绑定状态 |
| RevenueCat 订阅 webhook | Apple/Google 订阅事件回调 | POST /webhook/revenuecat | RevenueCatWebhookLogic（当前 stub，需回归实现后行为） | 订阅状态同步 Tally（待实现） |
| 投稿活动 | 进入活动页浏览/我的投稿/提交/更新 | GET /event/*、POST/PUT /event/*/submission | ListEvents/GetEvent/ListSubmissions/MySubmission/CreateSubmission/UpdateSubmission | 活动列表与投稿 CRUD |
| 公开配置下发 | App 拉取公开配置 | GET /config/:key | GetPublicConfig | 返回 jsonb 配置值 |
| 资源流式下载 | 加载大模型/资源文件 | GodotNetworkBridge network.download（Dio 流式+进度回传） | 无 | 大文件分块下载、进度回传、直写磁盘 |
| 对象存储上传（AWS） | 上传图片/资源 | ImageUploadService → POST /v2/studio/storage/temporary_token → AWS SigV4 PUT S3 | 无（直传 S3） | STS 临时凭证直传 AWS S3 |
| glb 压缩解析 | 加载压缩 glb 模型 | Godot 侧解析（前端结果） | 无 | 压缩 glb 正常解析渲染 |

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
| 后端 | 后端业务监控 | 本次需求涉及的业务场景指标（日志统计、监控图、SQL 等） | | | 10分钟 | | |
| 后端 | 金额核对 | 涉及资金的需求：用户金额与实际到账等 | | | 10分钟 | | |
| 后端 | 技术监控 | 本次新增或影响的接口：QPS、P95、错误率等 | | | 10分钟 | | |
| 后端 | 日志 | 重要正常/异常日志、warning/error | | | 10分钟 | | |
| 后端 | 实验 | 实验入组人数、分流比例、实验组与对照组业务表现 | | | 1小时 | | |
| 前端 | 前端技术监控 | Sentry/Grafana：报错、量级、性能耗时 | | | 1小时 | | |
| 前端 | 前端业务过程监控 | 核心页面流程监控 | | | 1小时 | | |
| 前端 | 神策埋点观察 | 曝光、点击上报及转化率看板与实验数据比对 | | | 1小时 | | |

不涉及的平台/维度可整行填「不涉及」或保留表头、内容填「-」。
观测结果列为上线后人工填写，生成时留空即可。

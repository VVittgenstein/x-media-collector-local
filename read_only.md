## file: {{DR_MD_FILENAME}}  
project: "{{PROJECT_TEXT}}"  
version: 0.1  
date: {{今天的日期，ISO8601}}  
derived_from: "Deep Research (raw notes in context)"

# {{PROJECT_TEXT}} · DR 结论（只读）

> 本文是从上游调研原文蒸馏的**结论性文档**，用于人审阅与 6b 机读抽取。  
> 约定：文中方括号标注 [EVID-###] 以指向“参考文献”。

## 1. 背景&目标

- 目标（What/Why）：构建一个**本地部署的 WebUI 小工具**，用户输入一个或多个 `https://x.com/<handle>` 账号主页 URL，并对每个账号配置筛选条件，启动任务后将符合条件的**图片/视频**下载到本地目录结构中。[EVID-001]
    
- 使用动机：用于 AI 模型训练数据收集；核心产物是一批可追溯来源的媒体文件，且**每个文件名必须包含 tweetId**，能追溯“至少来自哪个推文”。[EVID-001]
    
- 成功判据（对 MVP 的可验证结果）：
    
    - 对给定账号与筛选条件，下载结果的目录结构、命名、去重与统计口径符合约定；并发/队列/取消/续跑行为可按验收用例复现。[EVID-001]
        
    - 研究报告提出的评测口径包含：在限定日期范围内对测试账号集实现媒体抓取“准确率 100%”的人工核对；并在长时间任务中保持队列管理正确与无崩溃等稳健性表现（作为验证建议/基线）。[EVID-002]
        
- 非目标 / 暂不覆盖：
    
    - 不做“建库型产品”：不追求复杂数据库/媒体库/资产管理系统。[EVID-001]
        
    - UI 不做图片预览墙，仅展示统计与打开文件夹入口。[EVID-001]
        
    - 不使用官方开发者 API（Twitter/X Developer API），走浏览器会话模拟与 X 网页内部接口路径。[EVID-001]
        
    - 工具不负责自动获取凭证；凭证由用户自行从已登录浏览器提取后粘贴。[EVID-001]
        
    - 不做实时持续监控（按需手动触发采集）。[EVID-002]
        

## 2. 结论总览

- (C1) 产品形态与交互中心明确：以“账号列表”为中心的本地 WebUI；每行账号独立配置、独立状态；支持批量启动、最多同时运行 N 个账号、其余 FIFO 排队，并在开始/继续后立即锁定该行参数。[EVID-001]
    
- (C2) 数据落地以“训练数据可追溯”为导向：账号目录固定分 `images/` 与 `videos/`；文件名统一包含 `tweetId` 与 `created_at` 日期、以及下载后内容 hash 的前 6 位；账号内按内容 hash 去重、first wins，并将重复跳过计入速度统计的“完成任务数”。[EVID-001]
    
- (C3) 抓取技术方向为“网页登录态 + 内部接口（GraphQL）”：不走官方 API；依赖用户提供的浏览器 Cookies/Token，模拟已登录浏览器请求；但平台反爬与内部接口变化频繁，研究建议优先集成开源 GraphQL 抓取库以降低维护成本，并配套限流/退避/可选代理以降低风控概率。[EVID-001][EVID-002][EVID-003][EVID-004]
    
- (C4) 合规与风控风险不可忽视：使用真实用户会话凭证进行未授权抓取存在违反平台条款、触发账号风控/封禁的风险；工具需最少做到风险提示与凭证保护（不日志输出、不二次明文展示）。[EVID-001][EVID-002]
    

## 3. 关键决策与约束

> 6b 将据此拆出决策/约束类任务与校验。

- D1. 产品形态：必须是**本地部署 WebUI**小工具（非 CLI、非纯库）。依据 [EVID-001]
    
- D2. 任务入口：输入一个或多个账号主页 URL，逐行配置并逐行启动。依据 [EVID-001]
    
- D3. 抓取方式：采用浏览器会话模拟 + X 网页内部接口（如 GraphQL）的技术方向；不使用官方开发者 API。依据 [EVID-001][EVID-002]
    
- D4. 并发策略：并发只发生在账号之间；单账号内部串行处理；全局最大并发账号数默认 3，可调整；队列 FIFO。依据 [EVID-001]
    
- D5. 任务语义分离：Start New 与 Continue 分离；Queued 取消无副作用；Running 取消需二选一（保留/删除）。依据 [EVID-001]
    
- D6. 结果呈现：不做预览墙；每账号只展示统计与“打开文件夹”。依据 [EVID-001]
    
- D7. 推荐的实现取向：优先“集成开源 GraphQL 抓取库（twscrape）+ 自己的过滤与落盘逻辑”，以降低 doc_id 等变动的维护成本。依据 [EVID-002][EVID-003][EVID-004]
    
- Z1. URL 严格校验约束：仅接受且必须严格匹配 `https://x.com/<handle>`；不接受末尾 `/`、任何 query、额外路径、`twitter.com` 域名、`@handle` 形式。依据 [EVID-001]
    
- Z2. 凭证安全约束：凭证视为敏感信息；缺失时禁止启动；无效/过期时需给出可理解错误；不写入日志、不在 UI 明文二次展示（最多“已设置”）。依据 [EVID-001]
    
- Z3. 文件与去重约束：命名规则必须包含 tweetId；hash 取下载后内容 hash；账号内去重以内容 hash 判定，first wins；重复下载的临时文件删除并计入 `skipped_duplicate`。依据 [EVID-001]
    
- Z4. 平台不确定性约束：X 内部接口变更风险高（例如 GraphQL 查询标识与参数可能频繁变化），需预留更新/替换抓取层的空间，并在失败时提示升级依赖或调整策略。依据 [EVID-002][EVID-003]
    
- Z5. 风控与限流约束：非官方调用存在隐含限流与异常行为检测风险；应实现限速、随机延迟、指数退避；必要时支持代理配置作为扩展选项。依据 [EVID-002][EVID-003]
    

## 4. 需求提炼

> 每条均含“验收要点(acceptance-hint)”便于 6b 生成 acceptance。

### 4.1 功能性需求

- FR-01：全局凭证配置。UI 提供全局凭证输入区，粘贴浏览器会话信息；保存后仅展示“已设置”。依据 [EVID-001]  
    验收要点：未配置凭证时点击开始应被阻止并提示；凭证保存后 UI 不应回显明文凭证。依据 [EVID-001]
    
- FR-02：下载根目录配置。用户可设置 Download Root；所有账号输出在该 Root 下。依据 [EVID-001]  
    验收要点：修改 Root 后新任务输出路径随之变化；无写权限时应给出明确错误。依据 [EVID-001][EVID-002]
    
- FR-03：账号 URL 严格校验与 handle 解析。账号列表每行仅接受 `https://x.com/<handle>`；合法即解析并展示 handle；非法行标红并给出原因，且禁止启动该行任务。依据 [EVID-001]  
    验收要点：以下通过 `https://x.com/shanghaixc2`；以下失败并显示对应原因：  
    `https://x.com/shanghaixc2/`、`https://twitter.com/shanghaixc2`、`https://x.com/shanghaixc2?lang=zh`、`@shanghaixc2`、`https://x.com/shanghaixc2/media`。依据 [EVID-001]
    
- FR-04：按账号建目录与媒体分类目录。每个账号输出目录固定为 `<root>/<handle>/`，并包含 `images/` 与 `videos/` 子目录。依据 [EVID-001]  
    验收要点：启动任一账号任务后目录结构创建符合约定；图片与视频落在各自子目录。依据 [EVID-001]
    
- FR-05：每账号时间段筛选。每账号配置 `start_date` 与 `end_date`（YYYY-MM-DD），按推文 `created_at` 筛选，区间为闭区间（包含 end_date 当天）。依据 [EVID-001]  
    验收要点：设置边界日期时，end_date 当天媒体应被包含；超出范围的推文媒体不应下载。依据 [EVID-001]
    
- FR-06：每账号媒体类型筛选。支持 `images` / `videos` / `both`；若一条推文同时含图与视频，选择 `both` 时两类都下载并分别计数。依据 [EVID-001]  
    验收要点：分别选择三种类型时，目录内落盘与统计符合预期。依据 [EVID-001]
    
- FR-07：每账号来源类型筛选与分类规则。来源类型为 Original/Reply/Retweet/Quote 多选；分类规则为“只要是 Reply 就归 Reply（即使同时 Quote）”；Quote 仅指“不是 Reply 但存在引用关系”的推文。依据 [EVID-001]  
    验收要点：当只勾选 Reply 时，Reply+Quote 的推文也应被纳入；当只勾选 Quote 且未勾选 Reply 时，Reply+Quote 的推文不应被纳入。依据 [EVID-001]
    
- FR-08：Reply+Quote 引用媒体下载开关。每账号提供开关：当推文是 Reply 且同时 Quote 时，OFF 仅下载该 Reply 推文本身媒体；ON 下载 Reply 本身媒体 + 被引用推文媒体。依据 [EVID-001]  
    验收要点：同一条 Reply+Quote 推文在开关 ON/OFF 下的下载集合应符合定义。依据 [EVID-001]
    
- FR-09：分辨率过滤。每账号可设置 MIN_SHORT_SIDE；若 `min(width,height) < MIN_SHORT_SIDE` 则视为低清/杂图，不进入最终下载结果，仅计入过滤/跳过统计。依据 [EVID-001]  
    验收要点：阈值提高时下载结果应减少；被过滤媒体不应落盘到最终目录。依据 [EVID-001]
    
- FR-10：配置复制与粘贴。每行提供 Copy Config（复制该行筛选参数，不含 URL/handle）与 Paste Config（覆盖该行全部筛选参数，不改变 URL/handle）。Locked（Queued/Running）期间禁止 Paste。依据 [EVID-001]  
    验收要点：Paste 后该行所有筛选参数完全被覆盖；Locked 时 Paste 按钮置灰并提示原因。依据 [EVID-001]
    
- FR-11：任务状态机。每账号任务状态包含 `Idle / Queued / Running / Done / Failed / Cancelled` 并在 UI 清晰展示。依据 [EVID-001]  
    验收要点：从开始、排队、运行、完成、失败、取消等路径均能进入且仅进入定义内状态。依据 [EVID-001]
    
- FR-12：并发、队列与锁定。全局 Max Concurrent（默认 3）；Running 数未满则立即 Running，否则进入 Queued；队列 FIFO；点击开始/继续后无论 Queued 还是 Running 均立即锁定该账号参数；任务结束或取消后解锁。依据 [EVID-001]  
    验收要点：MaxConcurrent=3 时对 5 个账号点开始应得到 3 Running + 2 Queued；任一 Running 结束后队首自动转 Running；Queued 期间参数不可编辑。依据 [EVID-001]
    
- FR-13：Queued 取消无副作用。Queued 状态点击取消：从队列移除、立即解锁、不弹窗、行为等同没发生过。依据 [EVID-001]  
    验收要点：取消 Queued 后该账号不应产生“保留/删除”语义，也不应产生部分文件。依据 [EVID-001]
    
- FR-14：Running 取消二选一。Running 状态点击取消弹窗二选：Keep（保留已下载文件与任务记录，状态 Cancelled，可 Continue）或 Delete（删除本次运行已下载文件与任务记录，状态 Cancelled）。依据 [EVID-001]  
    验收要点：选择 Keep 后目录保留且 Continue 可用；选择 Delete 后“本次下载文件”按实现定义被移除并不可继续。依据 [EVID-001]
    
- FR-15：Start New 与 Continue 分离。Start New 表示全新运行语义；Continue 表示续跑语义，要求跳过已下载内容（由去重保证）。依据 [EVID-001]  
    验收要点：Cancel(Keep) 后 Continue 可用且不会重复落盘已有媒体；Continue 时统计的 `skipped_duplicate` 随跳过增长。依据 [EVID-001]
    
- FR-16：Start New 遇历史文件弹窗三选一。当账号目录存在历史文件/历史结果时点击 Start New 必须弹窗三选：Delete & Restart、Restart + Ignore History、Pack & Restart（zip 后删除原文件，zip 留在账号目录）。依据 [EVID-001]  
    验收要点：三种选择均可复现对应文件系统效果；Pack&Restart 生成 zip 且原文件移除、zip 留存。依据 [EVID-001]
    
- FR-17：文件命名规则。图片/视频统一命名为 `<tweetId>_<YYYY-MM-DD><hash6>.<ext>`；日期来自 `created_at`；hash6 来自下载后文件内容 hash 前 6 位。依据 [EVID-001]  
    验收要点：任意下载文件名可解析出 tweetId 与日期字段；hash6 与实际内容 hash 前 6 位一致。依据 [EVID-001]
    
- FR-18：账号内去重与遍历顺序。账号内按 `created_at` 从新到旧串行遍历；按内容 hash 去重，first wins；重复内容后遇到的媒体删除新下载临时文件并计入 `skipped_duplicate`。依据 [EVID-001]  
    验收要点：同一账号下多条推文含同内容媒体时，最终目录只保留一份；`skipped_duplicate` 增长。依据 [EVID-001]
    
- FR-19：统计与打开文件夹。每账号展示：已下载图片数、已下载视频数、runtime、avg_speed；提供打开 `<root>/<handle>/` 的按钮与路径展示；目录不存在时提示而非静默失败。依据 [EVID-001]  
    验收要点：runtime 从进入 Running 计时且不包含 Queued 等待；avg_speed 计算符合公式；打开文件夹在目录缺失时给出可理解提示。依据 [EVID-001]
    
- FR-20：抓取技术实现方向。请求需模拟浏览器（必要头部、携带会话凭证）；支持分页（cursor）；媒体从推文 JSON 提取媒体链接并选择合适质量版本；可选代理用于网络受限或风控规避场景。依据 [EVID-001][EVID-002]  
    验收要点：在有效凭证下能获取目标账号的媒体推文并完成下载；在凭证无效时给出“认证失败/检查过期”等错误。依据 [EVID-001][EVID-002]
    

### 4.2 非功能性需求

- NFR-01：稳健性。网络错误/超时需要重试或优雅失败，不应“一次就炸”；任务状态必须清晰可追踪。依据 [EVID-001]  
    验收要点：模拟网络断开/超时后，任务不应崩溃；应进入 Failed 或通过重试继续；UI 状态与错误信息可理解。依据 [EVID-001][EVID-002]
    
- NFR-02：凭证安全。凭证不写入日志、不在 UI 明文展示；仅显示“已设置”；工具本地运行但需基本的敏感信息保护。依据 [EVID-001][EVID-002]  
    验收要点：检查运行日志与前端渲染，不应出现 auth_token/ct0/Bearer/Cookie 明文。依据 [EVID-001][EVID-002]
    
- NFR-03：限流与退避。实现限速、随机延迟与指数退避；对潜在限流与异常检测做防护；必要时支持代理。依据 [EVID-002][EVID-003]  
    验收要点：对 429/疑似限流错误具备退避策略（等待后重试或明确失败）；不会在短时间内以固定间隔机械打爆请求。依据 [EVID-002][EVID-003]
    
- NFR-04：可维护性与可替换抓取层。考虑到 X 内部接口与 GraphQL 查询标识可能频繁变化，抓取层需要可独立升级/替换，并在失败时可提示用户升级依赖（例如 twscrape）。依据 [EVID-002][EVID-003][EVID-004]  
    验收要点：抓取层与业务层（过滤/命名/去重/队列）边界清晰；升级抓取依赖不影响核心业务逻辑。依据 [EVID-002]
    
- NFR-05：本地部署可用性。提供一键启动的本地运行方式；部署形态以用户本地执行为主。依据 [EVID-001][EVID-002]  
    验收要点：按 README/启动脚本能在本机启动 WebUI；无需外部服务即可运行（除 X 本身）。依据 [EVID-002]
    
- NFR-06：性能验证基线。研究报告提出可作为初测指标：单账号约 100 条含媒体推文在分钟级完成、并发多账号时在数分钟量级完成，并在 1 小时级任务中无崩溃/泄漏。依据 [EVID-002]  
    验收要点：在本地网络条件下完成一次端到端压测并记录吞吐、失败率、内存占用趋势；未达标则回溯限流与下载实现。依据 [EVID-002]
    

## 5. 技术路径与方案对比

|方案|适用场景|优点|风险/代价|证据|
|---|---|---|---|---|
|A 自研 GraphQL 调用|需要高度定制且能承担持续逆向维护|无外部依赖、灵活可控|维护成本高；GraphQL 查询标识与参数可能频繁变化导致脚本失效|[EVID-002][EVID-003]|
|B 集成开源 GraphQL 抓取库|追求快速交付与降低维护压力|复用社区对抗变化；更快落地；可把精力集中在过滤/落盘/任务系统|引入第三方依赖；需关注库更新与安全审计|[EVID-002][EVID-004]|
|C 浏览器自动化|需要更接近“真实用户行为”以降低检测|可靠性相对高、行为更像人|开发/调试成本高；资源占用大；对大规模历史数据抓取效率低|[EVID-002]|

> 推荐：优先方案 B（集成 twscrape 或同类库）+ 自己实现任务系统与落盘规则；并在抓取失败时提供“升级依赖/降低频率/启用代理”的运维路径。依据 [EVID-002][EVID-003][EVID-004]

## 6. 外部依赖与阻断

- 用户提供的浏览器会话凭证（Cookies/Token 等）：**blocked**（无凭证无法启动任务）。影响面：所有抓取任务。最小解锁路径：在 UI 提供简要说明与输入校验，明确缺失/过期错误提示。依据 [EVID-001][EVID-002]
    
- X 网页内部接口（GraphQL 等）：**unknown**（平台可能变更/限流/封锁）。影响面：抓取可用性。最小解锁路径：实现退避与错误可解释提示；必要时升级抓取库或切换方案。依据 [EVID-002][EVID-003]
    
- 开源库 twscrape（或同类）：**unblocked**（可直接引入），但存在版本更新依赖。影响面：抓取层维护成本。最小解锁路径：锁定可用版本并保留升级指引；必要时准备备选库/自研应急方案。依据 [EVID-002][EVID-004]
    
- 代理服务（可选）：**unknown**（取决于用户网络与风控情况）。影响面：在网络受限或高频抓取场景的成功率。最小解锁路径：先做无代理 Spike；若触发风控再接入代理配置。依据 [EVID-001][EVID-002][EVID-003]
    
- 本地磁盘空间与写权限：**unknown**（用户环境差异）。影响面：下载落盘与归档 zip。最小解锁路径：启动前做写权限检测与剩余空间提示（可选）。依据 [EVID-001][EVID-002]
    

## 7. 风险清单

- R-01：平台接口变更导致抓取失效。概率高、影响高；触发器：请求失败、解析字段变化、查询标识失效。缓解：优先用维护活跃的库；失败时提示升级与降频；将抓取层与业务层解耦。依据 [EVID-002][EVID-003][EVID-004]
    
- R-02：风控与限流触发（429/验证码/临时锁定）。概率中、影响中到高；触发器：短时间大量请求、机械化节奏。缓解：限速、随机延迟、指数退避；必要时代理；默认并发限制在账号层面。依据 [EVID-001][EVID-002][EVID-003]
    
- R-03：账号封禁/服务限制风险。概率中、影响中到高；触发器：违反平台条款或异常访问。缓解：在 UI/文档中显著提示风险；建议使用非主账号；支持冷却与停止。依据 [EVID-002]
    
- R-04：凭证泄露。概率低、影响高；触发器：日志/前端回显/错误上报包含敏感字段。缓解：敏感字段脱敏与禁记日志；凭证仅最小化存储；提供清除/更新路径。依据 [EVID-001][EVID-002]
    
- R-05：视频下载复杂性。概率中、影响中；触发器：视频源为流媒体清单或无直链，或下载中断导致文件不完整。缓解：优先选择 JSON 中可用的最高质量版本；实现下载重试与完整性校验；必要时评估引入额外依赖。依据 [EVID-002]
    
- R-06：第三方依赖停更或下架。概率低到中、影响中；触发器：开源库停止维护/仓库不可用。缓解：锁定可用版本与本地缓存；准备备选库；必要时自研应急。依据 [EVID-002][EVID-004][EVID-005]
    

## 8. 开放问题

- Q-01：凭证输入格式的最终拍板。是粘贴完整 Cookie 字符串还是按字段输入（auth_token、ct0、Bearer 等）？是否需要可配置 User-Agent？依据 [EVID-001][EVID-002]
    
- Q-02：Start New 的 “Ignore History + Replace” 精确定义。判定“相同文件”到底按文件名、内容 hash 或组合？与跨 run 的 first-wins 去重如何交互？依据 [EVID-001][EVID-002]
    
- Q-03：分辨率过滤的最低成本实现。GraphQL 响应是否总能提供足够的原始宽高用于下载前过滤？若不足，是否接受“先下载再删除”的带宽浪费，并如何在 UI 中解释？依据 [EVID-001][EVID-002]
    
- Q-04：限流与重试参数固化。单媒体失败重试次数、退避间隔、遇到 429 的暂停策略等如何从 Spike 数据中收敛为默认配置？依据 [EVID-001][EVID-002]
    
- Q-05：GraphQL 变化应急机制。若依赖库滞后或失效，是否需要预备“解析官网请求以更新 doc_id/参数”的应急流程？依据 [EVID-002][EVID-003]
    
- Q-06：视频格式兜底策略。遇到仅提供流媒体清单的情况，是否引入额外工具链作为可选依赖，或允许降级跳过/失败列表？依据 [EVID-002]
    

## 9. 术语与域模型

- 账号行 Account Row：一个账号 URL 输入 + 一组独立配置 + 一个任务状态。依据 [EVID-001]
    
- handle：从 URL 自动解析出的账号名，用于目录命名。依据 [EVID-001]
    
- 全局设置 Global Settings：浏览器会话凭证、Download Root、Max Concurrent。依据 [EVID-001]
    
- 账号配置 Account Config：每账号独立筛选参数集合（日期范围、媒体类型、来源类型、MIN_SHORT_SIDE、Reply+Quote 开关等）。依据 [EVID-001]
    
- 任务状态 Task Status：`Idle / Queued / Running / Done / Failed / Cancelled`。依据 [EVID-001]
    
- 完成任务数 Completed Count：用于速度统计，= 成功下载文件数 + `skipped_duplicate` 数。依据 [EVID-001]
    
- 去重 Dedup：同一账号目录内按“下载后文件内容 hash”判断重复，first wins。依据 [EVID-001]
    
- 分类规则：只要是 Reply 就归 Reply（即使同时 Quote）；Quote 指非 Reply 但存在引用关系的推文。依据 [EVID-001]
    

对象关系概述：

- Global Settings 作用于全局；Account Row 引用 Global Settings 并包含 Account Config 与 Task Status；Runner 以 Account Row 为单位执行抓取与下载；Downloader 将媒体落盘到 `<root>/<handle>/{images|videos}/` 并更新统计；Queue/Scheduler 管理 Running/Queued 与锁定状态。依据 [EVID-001][EVID-002]
    

## 10. 证据一致性与时效

- ⚠️ 平台限流与反爬细节的可变性：关于“每 IP 每小时约 300 请求”“doc_id 每 2–4 周变化”等属于第三方经验总结，非官方承诺，可能随时间变化；对实现的影响是需要以 Spike 校准默认限速/退避，并保持抓取层可更新。依据 [EVID-003][EVID-002]
    
- ⚠️ 依赖版本时效：twscrape 的版本与能力描述可能随更新变化；应将“可升级”作为运维路径，而非在产品需求中硬编码具体版本。依据 [EVID-002][EVID-004]
    
- 证据覆盖范围差异：EDAD 文档给出明确的产品行为与验收用例；研究报告补充抓取环境变化、方案对比与风险建议。二者在“本地 WebUI + Cookies 模拟 + 不用官方 API”的方向上无明显冲突。依据 [EVID-001][EVID-002]
    
- 数据缺口：关于分辨率元数据可用性、视频格式分布、限流参数与失败类型，需要通过最小 Spike 在真实账号与网络环境中补齐。依据 [EVID-001][EVID-002]
    

---

## 11. Action Seeds

```yaml
action_seeds:
  - id: ACT-001
    title: "确定后端架构与异步任务模型（WebUI + 任务队列）"
    category: decision
    rationale: "抓取与下载为 I/O 密集型，且需实现账号级并发与 FIFO 队列；需先定技术栈以承载后续 FR/NFR。"
    evidence: ["EVID-001","EVID-002"]
    acceptance_hint: "给出后端框架与任务执行模型的选择结论；说明如何实现 MaxConcurrent=3、FIFO、状态轮询/推送。"
    priority_guess: P0
    depends_on: []

  - id: ACT-002
    title: "Spike：用登录 Cookies 访问 X 内部接口并抓取媒体推文样本"
    category: spike
    rationale: "验证核心路径可行性与风控阈值，校准限流/退避与字段解析方案。"
    evidence: ["EVID-002","EVID-003","EVID-004"]
    acceptance_hint: "成功获取目标账号至少 50 条含媒体推文并下载落盘；记录错误类型（如 429）与耗时；24h 内账号无明显受限迹象（观察项）。"
    priority_guess: P0
    depends_on: ["DEP-001","DEP-002","DEP-003"]

  - id: ACT-003
    title: "实现账号 URL 严格校验与 handle 解析"
    category: build
    rationale: "这是所有后续任务的入口约束，且验收用例明确。"
    evidence: ["EVID-001"]
    acceptance_hint: "严格通过/拒绝用例完全符合文档 6.1；非法输入给出可理解原因并禁用启动。"
    priority_guess: P0
    depends_on: []

  - id: ACT-004
    title: "实现全局设置页：凭证输入、Download Root、Max Concurrent"
    category: build
    rationale: "全局设置决定任务能否启动与落盘路径，且涉及敏感信息处理。"
    evidence: ["EVID-001","EVID-002"]
    acceptance_hint: "缺失凭证禁止启动；保存后仅显示“已设置”；不回显明文；Root 可被任务正确使用。"
    priority_guess: P0
    depends_on: ["DEP-001"]

  - id: ACT-005
    title: "实现账号行 UI：每账号配置项与 Copy/Paste Config"
    category: build
    rationale: "多账号批量配置是核心交互；Locked 状态下禁止粘贴是关键边界。"
    evidence: ["EVID-001"]
    acceptance_hint: "Copy 不含 URL/handle；Paste 全覆盖参数；Queued/Running 时 Paste 置灰并提示。"
    priority_guess: P0
    depends_on: ["ACT-003","ACT-004"]

  - id: ACT-006
    title: "实现调度器：MaxConcurrent 默认 3、FIFO 队列、账号级锁定"
    category: build
    rationale: "并发/队列/锁定规则是 WebUI 体验与状态一致性的核心。"
    evidence: ["EVID-001"]
    acceptance_hint: "5 账号同时开始：3 Running + 2 Queued；Running 完成后队首自动转 Running；Queued 取消无副作用且解锁。"
    priority_guess: P0
    depends_on: ["ACT-005"]

  - id: ACT-007
    title: "实现任务生命周期：Start New / Continue / Cancel 与弹窗逻辑"
    category: build
    rationale: "取消与续跑决定可恢复性；Start New 的三选弹窗涉及破坏性操作需严格流程。"
    evidence: ["EVID-001"]
    acceptance_hint: "Running Cancel 弹窗 Keep/Delete；Queued Cancel 无弹窗；Start New 遇历史必须三选且文件系统效果正确；Continue 可用性与跳过规则正确。"
    priority_guess: P0
    depends_on: ["ACT-006"]

  - id: ACT-008
    title: "实现落盘规则：目录结构、命名、内容 hash、账号内去重 first-wins"
    category: build
    rationale: "训练数据采集的关键产物与可追溯性要求集中在此。"
    evidence: ["EVID-001"]
    acceptance_hint: "文件名格式符合 `<tweetId>_<YYYY-MM-DD><hash6>.<ext>`；重复内容只保留一份且 `skipped_duplicate` 增长。"
    priority_guess: P0
    depends_on: ["ACT-004"]

  - id: ACT-009
    title: "实现抓取与过滤：日期、媒体类型、来源类型、Reply+Quote 开关、MIN_SHORT_SIDE"
    category: build
    rationale: "把抓取层数据转为符合用户意图的下载集合；过滤规则验收明确。"
    evidence: ["EVID-001","EVID-002"]
    acceptance_hint: "对同账号同条件下结果集稳定可复现；Reply/Quote 分类符合规则；MIN_SHORT_SIDE 生效且被过滤媒体不落盘。"
    priority_guess: P0
    depends_on: ["ACT-002","ACT-008","DEP-002","DEP-003"]

  - id: ACT-010
    title: "实现统计口径与展示：runtime、avg_speed、打开文件夹"
    category: build
    rationale: "UI 只展示统计与路径，统计口径已定义为验收项。"
    evidence: ["EVID-001"]
    acceptance_hint: "runtime 不含排队时间；avg_speed=(img+vid+skipped_duplicate)/runtime；打开文件夹失败给出提示。"
    priority_guess: P1
    depends_on: ["ACT-006","ACT-008"]

  - id: ACT-011
    title: "实现限流、随机延迟、指数退避与可选代理配置"
    category: build
    rationale: "降低触发风控/限流的概率，提升长任务成功率。"
    evidence: ["EVID-002","EVID-003"]
    acceptance_hint: "可配置节流参数；遇 429 触发退避；代理开启后请求走代理且不影响其他逻辑。"
    priority_guess: P1
    depends_on: ["ACT-002","DEP-004"]

  - id: ACT-012
    title: "明确并实现 Ignore History + Replace 的判定规则"
    category: decision
    rationale: "Start New 三选弹窗的第 2 项语义未决，会影响跨 run 去重与替换行为。"
    evidence: ["EVID-001","EVID-002"]
    acceptance_hint: "输出判定规则（文件名/内容 hash/组合）并在实现中可测；说明与 first-wins 的交互。"
    priority_guess: P0
    depends_on: ["ACT-007","ACT-008"]
```

## 12. External Dependencies

```yaml
external_dependencies:
  - id: DEP-001
    name: "用户提供的 X 已登录会话凭证（Cookies/Token）"
    status: blocked
    blocker: "无有效凭证无法访问受限内容或触发认证失败"
    unblock_plan: "在 UI 提供凭证输入与校验提示；缺失/过期时阻止启动并给出可理解错误"
    evidence: ["EVID-001","EVID-002"]

  - id: DEP-002
    name: "X 网页内部接口可用性（GraphQL/内部端点）"
    status: unknown
    blocker: "接口可能变更、限流或增强反爬导致抓取失败"
    unblock_plan: "先做 Spike 校准；实现退避与错误提示；必要时升级抓取库或切换备选方案"
    evidence: ["EVID-002","EVID-003"]

  - id: DEP-003
    name: "twscrape 开源库（或同类 GraphQL 抓取库）"
    status: unblocked
    blocker: "库版本可能滞后或未来停更"
    unblock_plan: "锁定可用版本并保留升级路径；必要时准备替代库或自研应急抓取层"
    evidence: ["EVID-002","EVID-004"]

  - id: DEP-004
    name: "代理服务或本地代理配置（可选）"
    status: unknown
    blocker: "是否需要取决于网络环境与风控命中情况"
    unblock_plan: "默认关闭；在触发风控/网络受限时启用；提供最小可用配置入口"
    evidence: ["EVID-001","EVID-002","EVID-003"]

  - id: DEP-005
    name: "本地文件系统写权限与磁盘空间"
    status: unknown
    blocker: "Root 不可写或磁盘不足会导致下载与归档失败"
    unblock_plan: "启动前检测写权限；运行中对写入失败给出明确错误；可选提示剩余空间"
    evidence: ["EVID-001","EVID-002"]
```

## 13. 参考文献

统一 ISO-8601；若发布日期缺失，写 published: unknown。

- [EVID-001] X 媒体采集 WebUI（本地部署）EDAD 文档 v0.2 — 作者/机构：unknown（对话上下文） — published: unknown — accessed: 2026-01-12 — URL: `in-context`
    
- [EVID-002] Research Report — X 媒体采集 WebUI（本地部署）EDAD 文档 v0.2 — 作者/机构：unknown（附件） — published: 2026-01-12 — accessed: 2026-01-12 — URL: `attachment:/mnt/data/DR结论.md`.
    
    DR结论
    
- [EVID-003] How to Scrape X.com (Twitter) in 2026 — ScrapFly（博客） — published: 2025-09-26 — accessed: 2026-01-12 — URL: `https://scrapfly.io/blog/posts/how-to-scrape-twitter`
    
- [EVID-004] twscrape 项目描述（PyPI） — Vladkens（PyPI） — published: 2025-04-29 — accessed: 2026-01-12 — URL: `https://pypi.org/project/twscrape/`
    
- [EVID-005] twint 项目仓库（GitHub） — GitHub / twintproject — published: 2023-03-30 — accessed: 2026-01-12 — URL: `https://github.com/twintproject/twint`
    

## 14. 变更记录

v0.1（{{今天的日期}}）：首次从 DR 蒸馏，建立结论与 YAML 种子。
# Research Report — X 媒体采集 WebUI（本地部署）EDAD 文档 v0.2
- 版本/时间戳：2026-01-12
- 研究窗口：近12个月（2023Q4–2025），涵盖 X 平台反爬变化与非官方抓取方案最新进展:contentReference[oaicite:0]{index=0}:contentReference[oaicite:1]{index=1}。
- 执行摘要：
  1. **官方API不可行**：Twitter已取消免费API，基础付费版年费达 $42k，且限额严苛:contentReference[oaicite:2]{index=2}；本项目明确排除官方API。
  2. **非官方抓取环境剧变**：2023年以来 X 平台频繁更新反爬策略（登录强制、Token失效、GraphQL查询ID变动等），传统抓取工具（如Twint）已因维护困难被弃用:contentReference[oaicite:3]{index=3}。
  3. **GraphQL内部接口方案**：利用已登录浏览器Cookies调用X网页内部GraphQL接口获取推文数据，可绕过官方API限制。需处理**查询ID (doc_id)** 动态更新和认证Header等细节:contentReference[oaicite:4]{index=4}:contentReference[oaicite:5]{index=5}。
  4. **开源库选型**：现有开源项目（twscrape、twitter-api-client 等）已实现X GraphQL抓取，支持登录Cookies和图形查询，MIT许可。twscrape尤为专注爬取，具2k+星，支持账号池和限流:contentReference[oaicite:6]{index=6}:contentReference[oaicite:7]{index=7}。
  5. **方案对比**：A) **自行实现GraphQL**：控制灵活但需频繁维护（doc_id每2-4周变化:contentReference[oaicite:8]{index=8}）；B) **集成开源库**：快速赋能且由维护者追踪变化，但引入依赖；C) **浏览器自动化**：模拟用户滚屏可靠性高但开发与资源成本较高。
  6. **风控绕避**：X对GraphQL调用有限制（约300请求/时/IP）并检测异常模式:contentReference[oaicite:9]{index=9}。应采用**限速、随机延迟**策略，避免短时大量请求；必要时使用**代理IP**或多账号分担负载:contentReference[oaicite:10]{index=10}。
  7. **媒体下载处理**：推文JSON含媒体URL，可直接下载。图片视频存储分目录、文件名含推文ID+哈希；需根据元数据过滤低分辨率媒体（GraphQL返回中含尺寸信息，可在下载前判断）。
  8. **断点续传与去重**：通过记录已下载媒体哈希，实现账号内去重（first-win保留）。取消任务支持续跑，利用哈希跳过重复。文件名含tweetId便于追溯来源。
  9. **合规与安全**：使用真实用户Cookies绕过登录，违反X服务条款，有被封号风险:contentReference[oaicite:11]{index=11}；工具需提示用户风险并保护好凭证（不日志输出Cookies等）。
  10. **推荐方案**：采用**开源GraphQL抓取库（twscrape）**结合自行逻辑。该方案开发效率高、维护成本低（社区快速适配变化），同时通过配置限流和代理降低被检测风险:contentReference[oaicite:12]{index=12}:contentReference[oaicite:13]{index=13}。

- 问题定义
  - **目标**：实现本地部署的Web界面工具，批量抓取指定X账号在设定时间段内发布的含媒体推文，将图片/视频按账号归类下载，并满足断点续传、去重等要求。
  - **非目标**：不开发复杂媒体资产管理系统或持久化数据库；不使用官方Twitter API接口；不涉及实时持续监控（工具按需手动触发采集）。
  - **场景与约束**：仅供个人研究（AI训练数据）使用，本地执行；用户提供已登录会话Cookies以模拟浏览器；受X平台未授权抓取限制，须避免账号封禁；最大并行任务数默认3，受限于本地带宽及平台限流。
  - **成功标准**（可量化）：针对测试账号集，在限定日期范围内**100%**抓取其发布的媒体文件；下载文件命名和目录结构符合规范（含tweetId、分类目录）；重复媒体不重复保存；大规模（如10个账号各含数千媒体）运行无崩溃，无明显限流触发（账户未被临时锁定）。

- 背景与术语
  - **X平台 GraphQL 抓取**：Twitter Web客户端使用GraphQL API获取内容，例如`UserTweets`或`UserMedia`查询。每个查询由**doc_id**标识，平台频繁更换doc_id以打击未授权调用:contentReference[oaicite:14]{index=14}:contentReference[oaicite:15]{index=15}。调用需附带**授权Header**（含固定Bearer Token和用户Cookies中的auth_token、ct0等）:contentReference[oaicite:16]{index=16}。
  - **Guest Token vs 登录**：未登录用户需获取**Guest Token**访问部分接口，该Token有效期短、绑定IP，已成为反爬重点:contentReference[oaicite:17]{index=17}:contentReference[oaicite:18]{index=18}。本项目通过登录Cookies绕过Guest机制，提高稳定性。
  - **Rate Limit**：非官方调用的隐含限流约为每IP每小时300次请求:contentReference[oaicite:19]{index=19}（具体值未公开，但经验值在此量级），超限将返回错误或触发封锁。需自实现**速率控制**和**指数退避**策略应对。
  - **检测与封锁**：X平台会检测请求模式，过于机械的调用（如固定间隔批量请求）可能被标记。2024年起还加强了TLS指纹和IP信誉校验:contentReference[oaicite:20]{index=20}:contentReference[oaicite:21]{index=21}。使用**住宅代理**或模拟浏览器指纹可降低风险。
  - **Cookies 凭证**：包括`auth_token`（用户身份）、`ct0`（CSRF Token）等，用于认证请求。需来自真实登录会话。工具应确保Cookies安全，不在前端暴露。
  - **doc_id (查询ID)**：GraphQL端点URL中用于标识特定查询操作的ID。官方前端定期更换ID值以致第三方脚本失效:contentReference[oaicite:22]{index=22}。例如UserTweets查询的doc_id在2023年多次更新。对策：使用开源库内置ID或在运行时解析最新ID。
  - **媒体URL**：推文JSON包含媒体信息。图片通常以`pbs.twimg.com`域名链接，可直接HTTP GET下载。视频通过.m3u8文件或多分辨率流，可在JSON的`video_info`字段找到最高质量的视频直链。
  - **去重 (Deduplication)**：根据文件内容哈希判断同一账号内重复媒体。采用“first wins”策略——首次下载保留，后续遇到相同哈希则跳过并计数。
  - **任务状态**：每账号任务有 Idle（未开始）、Queued（排队等待）、Running（进行中）、Done（完成）、Failed（失败）和 Cancelled（取消）等状态。Queued取消不影响已下载数据，Running取消可选择保留/删除当次成果。
  - **断点续传**：Cancelled状态下保留已下载部分，可通过 Continue 操作跳过已完成部分继续剩余下载。
  - **资料生态**：目前X平台抓取主要靠逆向GraphQL接口；社区维护了若干工具（Twint、snscrape、twscrape等）来替代官方API获取数据，但都面对平台反制持续更新的挑战:contentReference[oaicite:24]{index=24}。

  *(下图：基于浏览器Cookie的X平台非官方数据抓取流程示意)*

  :contentReference[oaicite:25]{index=25}  
  *图1：通过已登录会话调用 X GraphQL 接口抓取推文及媒体*

- 先例与对标

| 名称/项目       | 类型         | 许可    | 关键能力                       | 优势/劣势                         | 备注/适用情况               |
| -------------- | ------------ | ------- | ------------------------------ | -------------------------------- | -------------------------- |
| Twint (<=2023) | 开源抓取工具  | MIT    | 无需登录抓取推文、用户信息       | **优**：历史上功能丰富；**劣**：已停止维护，登录强制后基本失效:contentReference[oaicite:26]{index=26} | 过去流行，现仅作参考       |
| SNScrape       | 开源抓取库   | GNU AGPL | 不使用官方API获取推文（曾可匿名）| **优**：接口简单，支持多平台；**劣**：依赖公开端点，随X调整频繁中断 | 维护活跃，但未来不确定     |
| twscrape       | 开源库       | MIT    | GraphQL抓取、账号池、多账号切换  | **优**：支持登录、限流、持续维护；**劣**：需Python环境，调用需异步编程 | 本项目可直接集成:contentReference[oaicite:27]{index=27} |
| twitter-api-client | 开源库   | MIT    | 封装官方v1/v2和GraphQL API      | **优**：功能全面（含发帖等）；**劣**：相对复杂，需适配本项目特定抓取用例 | 若需更全面Twitter操作       |
| ScrapFly Scraper | 商业服务   | 专有    | 封装维护X爬虫、自动代理等       | **优**：官方监测变化及时更新:contentReference[oaicite:28]{index=28}；**劣**：收费服务，依赖第三方 | 大规模持续抓取（企业级）    |
| 手工GraphQL脚本 | 自研方案   | N/A    | 直接调用内部API                 | **优**：无外部依赖，定制灵活；**劣**：需跟踪更新doc_id和参数，开发量大 | 高度定制、有专门逆向能力时   |

- 方案空间与推荐
  - **方案A：直接实现GraphQL抓取**  
    思路：手动编写模块，通过`requests`或`httpx`发起对`https://x.com/i/api/graphql/<doc_id>/UserTweets`等端点的请求。使用用户提供的Cookies和Headers，分页获取推文JSON，解析出媒体链接下载。  
    依赖：无需额外库，但需维护GraphQL查询ID和必要的features参数。  
    复杂度：实现解析逻辑中等，但**维护复杂度高**——X频繁修改接口参数，每隔几周需更新doc_id:contentReference[oaicite:29]{index=29}、features字段:contentReference[oaicite:30]{index=30}。团队需投入逆向精力，可能需要监控官网JS或截取网络请求以获取最新ID:contentReference[oaicite:31]{index=31}:contentReference[oaicite:32]{index=32}。  
    成本：一次性开发成本中等，但后续维护成本较高（ScrapFly估计DIY每月需10-15小时更新维护:contentReference[oaicite:33]{index=33}）。无直接财务成本。  
    性能/扩展：单机可控并发3账号，瓶颈在网络IO和限流。可优化请求并行获取各账号数据。扩展到更多账号需考虑代理。  
    安全/隐私：不引入第三方，Cookies仅本地使用。但需谨慎避免过于频繁请求导致账号锁定:contentReference[oaicite:34]{index=34}。  
    团队可达性：需要具备一定逆向能力和随时调整的响应速度；对于小团队，这是一项负担。

  - **方案B：集成现有开源库**  
    思路：利用社区维护的库（如 **twscrape**）来处理GraphQL调用、登录及反爬细节。我们的工具通过调用库的API获取推文数据，再应用自身的筛选下载逻辑。  
    依赖：Python库twscrape（MIT）。该库封装了Twitter网页API调用，支持以Cookie登录、多账号池、防限流等:contentReference[oaicite:35]{index=35}:contentReference[oaicite:36]{index=36}。还可输出结构化数据模型，便于提取媒体URL。  
    复杂度：开发集成简单，按库文档调用`api.user_tweets()`或`api.search()`接口即可获取指定用户推文列表:contentReference[oaicite:37]{index=37}:contentReference[oaicite:38]{index=38}。**复杂度低**，核心难题（doc_id变化、Token获取）由库维护者解决。  
    成本：开发成本最低；需注意库本身更新及时性，可能需偶尔升级版本。无直接金钱成本。  
    性能/扩展：twscrape支持异步IO和多账户并发:contentReference[oaicite:39]{index=39}；在单账户Cookie下性能与方案A类似。多账户模式可缓解单Cookie限流，但本项目暂不考虑同时持多Cookie。  
    安全/隐私：需信任开源库代码不恶意泄露Cookies（该库2k+星信誉尚可）。Cookies仍本地存储使用。  
    团队可达性：极高——开发者只需熟悉库用法，无需深入协议细节；社区有一定支持，遇到问题可参考issue或更新。适合当前人力。  

  - **方案C：浏览器自动化 (Headless)**  
    思路：利用无头浏览器（如Playwright、Selenium）模拟用户登录X并滚动加载目标账号主页，拦截网络请求或直接解析网页DOM提取媒体链接。  
    依赖：浏览器驱动及其Python库；需Chromium内核环境。  
    复杂度：实现较高——需要编排浏览器会话登录（可导入Cookies以免人工登录）、控制滚动加载并实时提取内容。页面结构变化会导致解析脚本需调整。  
    成本：开发调试耗时，运行时资源占用大（浏览器实例消耗CPU/内存）。若批量账号并行，会占用多实例浏览器，可能性能瓶颈。  
    性能/扩展：相对慢，每个账号需模拟滚屏逐步加载（无法跳页，实测每scroll返回几十条）。不适合大量账户或深历史数据采集。  
    安全/隐私：浏览器模拟真实度高，**风控命中概率低**（因为行为类似人工操作）。但如果脚本执行过快或并行过多，也有可能被反爬检测。  
    团队可达性：需要对浏览器自动化技术有经验，增大项目技术栈复杂度。不利于后续维护。

**决策矩阵**（满分5分，5=最好）：

| 决策因素    | 方案A: 自研GraphQL |  方案B: 开源库   | 方案C: 浏览器自动化 |
| :------ | :------------: | :---------: | :---------: |
| 开发初始工作量 |       3        |    **5**    |      2      |
| 后续维护成本  |       2        |    **4**    |      3      |
| 抗封锁与稳健性 |       3        | **4** *(注)* |    **5**    |
| 性能效率    |     **5**      |    **5**    |      2      |
| 技术风险    |       3        |    **4**    |      3      |
| 合规安全    |       3        |      3      | **4** *(注)* |
| **综合**  |       16       |   **25**    |     19      |

*注：方案B抗封锁依赖库的策略（如多账号、限流），需适配使用；方案C因模拟人为操作，相对不易被发现，但不代表绝对安全。*

  - **推荐方案与放弃理由**：综合考虑，**推荐方案B（集成开源库 twscrape）**。理由：1）开发效率高，短期内即可实现主要功能；2）维护负担低，由社区跟踪X接口变化即时更新:contentReference[oaicite:40]{index=40}；3）支持Cookie登录、限流和并行特性，能较好满足项目需求:contentReference[oaicite:41]{index=41}。相比之下，方案A 虽无外部依赖但维护成本难以负担，且一旦doc_id变动工具即失效，不利于稳定性:contentReference[oaicite:42]{index=42}。方案C 在当前需求下显得过于复杂且资源开销大，不符合本项目“小工具”定位。综上，我们选择方案B，并通过严格限流和必要时手动更新库版本，尽量降低风控风险。

- 外部依赖清单

| 名称/服务               | 版本/更新时间       | 许可          | 调用配额/频率       | 兼容性         | 弃用/维护风险           | 备注                     |
| ---------------------- | ------------------- | ------------- | ------------------- | -------------- | ----------------------- | ------------------------ |
| **twscrape** 库        | 0.17.0 （2025-04-29 发布）:contentReference[oaicite:43]{index=43} | MIT (开源)  | 无官方限制，受X平台限流约300请求/小时约束:contentReference[oaicite:44]{index=44} | Python 3.10+ | 中等：高度依赖X内部实现变化，但维护者活跃，2-4周内常有更新 | 用于GraphQL抓取核心逻辑 |
| Twitter网站GraphQL接口 | 动态 (2025活跃)    | 未授权公开     | 约300请求/小时/IP:contentReference[oaicite:45]{index=45}; 单请求返回最多40推文左右 | 与X前端版本匹配 | 高：接口非公开，变更频繁:contentReference[oaicite:46]{index=46}；需监控调整 | 通过twscrape间接使用     |
| requests/HTTP客户端     | 2.31.0（2023）等   | Apache-2.0等 | N/A (本地调用，无远端限额) | 与Python 3.x兼容 | 低：HTTP库稳定维护       | 用于一般HTTP请求         |
| 浏览器Cookies（用户提供） | 动态              | N/A (用户数据)| N/A                | 与X平台Web匹配 | 高：有效期有限，需用户更新；误用可能被吊销 | X数据访问必要凭证       |
| 代理服务（可选）         | 动态              | 商用/自有     | 视供应商策略        | 需HTTP CONNECT支持 | 中：代理IP易失效或被封   | 抗封锁扩展选项           |

- 风险与不确定性
  1. **平台接口变更风险** （影响：高，概率：高）  
     *说明*：X平台可能进一步收紧未授权访问，如更频繁地更新GraphQL查询ID、要求附加验证参数，甚至完全禁止非WebUA请求。最近趋势显示doc_id每月更新，且增加必需的features参数:contentReference[oaicite:47]{index=47}。  
     *缓解策略*：持续关注相关开源项目和社区情报（如twscrape issue、Twitter反爬消息）；优先选择能自动发现新doc_id的方案:contentReference[oaicite:48]{index=48}:contentReference[oaicite:49]{index=49}。在工具内实现查询失败重试，并提示用户更新库版本或等待补丁。
  2. **账号封禁风险** （影响：中，高频使用时高；概率：中）  
     *说明*：使用真实账号Cookies批量采集违反X服务条款，可能触发账号临时锁定甚至永久封禁:contentReference[oaicite:50]{index=50}。尤其在短时抓取大量数据或使用多账号刷数据时风险上升。  
     *缓解策略*：严格遵守限流阈值，设计逐步退避算法（如接近300请求/时则暂停冷却）；模拟真人行为（随机延迟、限制并发）；可选用不重要的“小号”执行采集，以防主账号受损。明确提示用户可能的封禁后果，由用户决定投入何种账号。
  3. **多媒体处理复杂性** （影响：中，概率：中）  
     *说明*：推文中的视频需要解析最高质量源，可能涉及额外请求（如获取m3u8清单）；同时若媒体量大，下载中断、文件完整性等需处理。  
     *缓解策略*：利用tweet JSON自带的视频变体列表，选取最高bitrate直链:contentReference[oaicite:51]{index=51}直接下载，避免解析m3u8；实现下载重试和校验，对每个文件计算hash验证完整性。不合格文件列入失败清单供用户重试。
  4. **第三方依赖风险** （影响：中，概率：低）  
     *说明*：依赖的开源库twscrape倘若停止维护或被Twitter官方法律打击（例如DMCA要求下架）将使项目失去抓取功能。  
     *缓解策略*：保持备选方案预案，如转用twitter-api-client库或切换自行维护doc_id列表。尽量使用本地缓存的库版本，即使仓库下架短期内不受影响；关注社区fork动向以获取非官方支持版本。
  5. **Cookie泄露与安全** （影响：中，概率：低）  
     *说明*：用户需提供高权限Cookies，若这些凭证泄露，攻击者可劫持账号会话。工具运行中若不当记录日志、或依赖存在漏洞，可能导致Cookies外泄。  
     *缓解策略*：加强本地安全措施——Cookies只保存在内存或本地受保护配置文件，不打印输出:contentReference[oaicite:52]{index=52}。代码避免将Cookie传递给无关第三方。指导用户在完成任务后可手动失效该Cookie（如退出账号重新登录刷新Session）。

- 最小验证计划（Spike）
  - **目标**：验证在真实环境下使用登录Cookies调用GraphQL接口获取指定账号的媒体推文数据的可行性和稳定性，确认不会立即触发风控。判定阈值：成功获取目标账号最近的一定数量推文及媒体（例如50条含图/视频推文）且账号未出现访问受限提示。
  - **步骤**：
    1. **准备测试账户**：选择一个拥有不少于50条媒体推文的X账号，获取测试用Cookies（确保有效且具备浏览权限）。
    2. **调用获取推文列表**：以方案B实现为例，编写简短脚本使用twscrape库调用`api.user_media(user_id, limit=100)`获取推文对象列表:contentReference[oaicite:53]{index=53}。记录调用耗时及是否遇到Captcha或429错误。
    3. **解析媒体并下载**：从返回的数据中提取前50条推文的媒体URL，执行下载（图片直接GET，视频取最大分辨率MP4链接）。验证文件保存成功且大小合理、能打开预览。
    4. **限流测试**：在不更换IP的情况下，短时间内重复第2步（例如连续执行5次获取100条）观察是否有请求被拒绝或Cookie失效迹象。 
    5. **恢复与清理**：如有临时锁定（需验证码等）则记录现象；结束后清除Cookies痕迹或更换密码确保账号安全。
  - **产出与验收**：记录包括：每次请求返回的状态（成功/失败及错误信息）、获取推文数、下载的样本文件列表。验收标准：初次请求获取数据成功且下载媒体正确；5次高频调用中至少4次成功（允许1次失败重试），且测试账号在24小时内未被封禁或要求验证。此Spike通过将证明方案可行，反之则需调整策略（如降低频率或引入代理）。

- 评测与验收标准
  - **功能正确性**：针对若干已知媒体数量的测试账号，运行工具后人工核对下载文件数是否与账号该时间段内实际含媒体推文数一致。阈值：准确率100%（有漏则不合格）。
  - **性能指标**：在常规网络环境，单账号100条含媒体推文的抓取下载应在2分钟内完成；5个账号并行抓取（总计500~1000媒体）应在 ~5 分钟量级完成。至少达到平均每秒下载1张图片或0.2个视频的速度:contentReference[oaicite:54]{index=54}:contentReference[oaicite:55]{index=55}。如低于预期，检查限流配置。
  - **稳健性**：在长达1小时的持续抓取任务中无崩溃、内存泄漏，任务队列管理正确（验证并发3+排队机制）。遇到网络错误时应自动重试（不多于3次）或优雅跳过，不出现无限阻塞。
  - **边界测试**：验证URL校验严格性（提供不合规输入，应给出错误提示，禁止开始:contentReference[oaicite:56]{index=56}）；取消任务的处理（Queued状态取消无残留，Running状态取消后文件处理符合选项）；“重新开始”在有历史文件情形下触发正确的弹窗和对应动作（删除/保留/归档）。
  - **安全与合规**：检查日志和UI，确保不打印或暴露Cookies等敏感信息。模拟异常场景（过期Cookie、无Cookie）验证提示友好。试运行若干账号后确认测试账户未被封禁或要求验证（以24小时观察期为准）。如有则调整策略后再次测试。
  - **用户体验**：界面元素符合预期（每行账号配置项有效，状态切换正确）；在各种主要浏览器上打开WebUI无样式错误。用户设置错误操作（如未设Cookie就开始）有明确错误提示，不出现未知异常。

- 合规/隐私/安全要点
  - **服务条款**：通过Cookies抓取违反X平台的Terms of Service和开发者政策:contentReference[oaicite:57]{index=57}。理论上，用户已同意平台TOS，爬取属于违约行为，有被单方面终止服务甚至法律追责可能:contentReference[oaicite:58]{index=58}:contentReference[oaicite:59]{index=59}。建议仅将工具用于学术研究，不公开发布采集数据，并提醒用户自担风险。
  - **数据隐私**：获取的是公开发布内容（公开推文和媒体），不存在个人敏感信息处理。但应尊重目标账户的版权和隐私设定（若账号受限或内容被删除，工具不应绕过权限获取）。
  - **跨境数据**：工具本地运行，不涉及数据跨境传输。用户应遵守所在地关于数据爬取和使用的法律法规（例如GDPR下的大规模社交数据收集需匿名化处理）。
  - **安全**：强调用户不要在不可信环境下使用此工具，避免Cookies泄露。我们不存储Cookie，仅在运行时内存使用，并提供方便的删除/更新接口。代码需防范典型Web安全问题（XSS/CSRF不太涉及因无多用户服务端，但前端表单要防注入崩溃）。
  - **可解释性**：提供适当日志或报告，使用户了解抓取了哪些推文ID及对应媒体文件，以便审计和删除。遇到封禁风险事件时（如出现验证码要求），提示原因并建议冷却等待。
  - **遵循robots协议**：虽属自主工具，但应尊重X robots.txt（然而X的robots.txt通常禁止爬虫访问/api等）。此工具定位个人用途，未额外考虑robots限制。

- 开发影响面
  - **接口设计**：使用twscrape则需要在Python服务端集成异步事件循环（twscrape基于asyncio）。我们可采用Quart或FastAPI等支持async的Web框架实现WebUI后端，以便同时进行抓取IO操作和响应UI请求。前端通过Ajax轮询任务状态。
  - **数据存储**：大文件保存需考虑磁盘空间管理。支持用户配置下载根目录，确保有写权限。归档旧数据功能需要Zip压缩模块支持（Python标准库zipfile足够）。
  - **部署**：本地部署以用户手动运行为主，提供一键启动脚本。依赖Python环境和浏览器Cookies输入。可以考虑打包为Docker镜像以简化环境配置（包含Chrome和twscrape依赖），但用户需要提供Cookies环境变量。
  - **监控**：由于工具本地使用，没有服务端监控。但我们可添加本地日志记录（调试级别可选）用于问题诊断。日志注意不要记录敏感Cookie，只记录操作摘要和错误。
  - **CI/CD**：项目作为个人工具，CI主要用于lint和基本功能测试（可模拟一个公开账号的数据抓取验证）。CD非强需求，但可提供GitHub Actions生成Release版本的zip供下载。
  - **互操作**：未来若要扩展支持其他平台（如Instagram等），应抽象出抓取接口层。目前专注X平台，不做泛化设计。
  - **多语言**：暂假定用户懂中文/英文界面。如需国际化，可引入i18n框架。但MVP不考虑。

- 未决问题
  1. **GraphQL查询ID获取**：当前通过开源库内部维护，需信任其更新。如库滞后，我们是否实现备用方案（例如解析官网JS获取doc_id）？*解锁条件：当库连续>2周未更新且接口失效时，启动自研doc_id抓取应急方案调研*。
  2. **“忽略历史重新开始”语义**：当重新开始任务且不删除历史时，“相同文件”判定基准未明确。是依据文件名(tweetId+哈希)匹配，还是重新计算内容哈希比对？这一点影响续跑逻辑。*解锁条件：实际实现续跑时，根据实现简便性和可靠性决定：倾向于用文件名匹配跳过（简单但可能漏判），如需更精确则对比hash。通过小规模实验验证两方案性能后决定*。
  3. **视频下载质量**：目前设想取最高分辨率MP4，但某些推视频只有流媒体m3u8格式。是否引入ffmpeg下载流？这增加依赖和复杂度。*解锁条件：遇到无法直接下载的视频格式时，再决定是否集成ffmpeg或降级下载次高清版本*。
  4. **分辨率过滤实现**：GraphQL返回的图片元数据中有不同size（如small, large），需确定如何获取原始分辨率。如果接口不给原始尺寸，只提供缩略图信息，则需下载后检查。这将浪费带宽。*解锁条件：调研GraphQL返回结构确认是否含原始宽高字段。如有则直接比较，否则考虑提供“先下载再删”实现，并在文档中告知可能多耗流量*。
  5. **异常重试策略**：未决定对于单个媒体文件下载失败（网络抖动）时重试次数及间隔，也未明确遇到429限流时全局暂停多久。这些参数需根据测试调整。*解锁条件：在Spike或内部测试中收集典型错误发生频率，制定合理的重试上限（如单文件重试3次，每次间隔5秒；遇429暂停5分钟等），再固化到实现*。

- 参考资料（Evidence Table）

| 主张 / 结论                           | 证据摘录                                                       | 来源标题                                      | 发布者      | 链接                                          | 内容日期    | 访问日期    | 可信度 |
| ------------------------------------ | ------------------------------------------------------------ | --------------------------------------------- | ----------- | --------------------------------------------- | ----------- | ----------- | ------ |
| 官方免费API关闭，付费昂贵且抓取频繁破坏 | “X.com's free API is gone; the paid version costs $42,000/year minimum… Guest tokens, doc_ids… break scrapers every 2-4 weeks”:contentReference[oaicite:60]{index=60} | How to Scrape X.com (Twitter) in 2026         | ScrapFly博客 | https://scrapfly.io/blog/posts/how-to-scrape-twitter | 2025-09-26 | 2026-01-12 | 高    |
| GraphQL查询使用doc_id标识且频繁旋转    | “GraphQL queries use doc_ids… These: * Rotate every 2-4 weeks”:contentReference[oaicite:61]{index=61} | How to Scrape X.com (Twitter) in 2026         | ScrapFly博客 | https://scrapfly.io/blog/posts/how-to-scrape-twitter | 2025-09-26 | 2026-01-12 | 高    |
| 非官方调用限流约300请求/小时，X会检测异常行为 | “Rate limit: 300 requests per hour per IP… Detection: X.com tracks request patterns and flags suspicious behavior”:contentReference[oaicite:62]{index=62} | How to Scrape X.com (Twitter) in 2026         | ScrapFly博客 | https://scrapfly.io/blog/posts/how-to-scrape-twitter | 2025-09-26 | 2026-01-12 | 高    |
| 开源库支持Cookies登录，多账号和代理   | “Cookie-based accounts… fewer login issues… recommend using proxies… Terms of Service discourage using multiple accounts… common practice for data collection”:contentReference[oaicite:63]{index=63} | twscrape 项目描述 (PyPI)                     | Vladkens (PyPI) | https://pypi.org/project/twscrape/           | 2025-04-29 | 2026-01-12 | 高    |
| 违反服务条款可能导致账户被关          | “Twitter could deny service to you meaning it's probably going to close your account because you may break the TOS policy”:contentReference[oaicite:64]{index=64} | Reddit帖子：使用Cookies抓取数据是否合法？     | Reddit用户   | https://www.reddit.com/r/programming/comments/10ssyig/.../ | 2023-02 (约) | 2026-01-12 | 中    |
| 著名抓取工具Twint已停止维护            | “This repository was archived by the owner on Mar 30, 2023. It is now read-only.”:contentReference[oaicite:65]{index=65} | twint 项目仓库 (GitHub)                      | GitHub       | https://github.com/twintproject/twint         | 2023-03-30 | 2026-01-12 | 高    |

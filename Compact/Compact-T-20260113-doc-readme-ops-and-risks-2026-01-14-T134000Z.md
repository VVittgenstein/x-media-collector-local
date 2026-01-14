# Compact — T-20260113-doc-readme-ops-and-risks

- generated_at_utc: 2026-01-14T13:40:00Z
- subtask_type: doc
- record_status: done

## 1) Scope（对齐范围）

- 目标：编写完整的 README.md，提供一键启动路径（含依赖安装与启动命令）。
- 目标：说明凭证来自用户浏览器、工具不自动获取、"已设置"不回显明文的安全原则。
- 目标：显著提示风控/封禁风险与建议（使用非主账号、控制频率）。
- 目标：创建详细的故障排查指南 `docs/ops/troubleshooting.md`，给出排障步骤：检查凭证→降频→启用代理→升级抓取库。
- 非目标：不涉及代码实现，仅文档编写。

## 2) 已确认事实（Repo 落地 + 验证）

- [FACT] `record.json` 中 `T-20260113-doc-readme-ops-and-risks` 已更新为 `status: done`，`updated_at: 2026-01-14T13:40:00Z`，`owner: claude`。
- [FACT] `README.md` 已完整编写，包含以下章节：
  - 风险提示（Risk Warning）：显著提示会话模拟可能违反服务条款、账号封禁风险、建议使用非主账号。
  - 快速开始（Quick Start）：系统要求、ffmpeg 安装、一键启动命令（虚拟环境+依赖安装+uvicorn）。
  - 凭证配置（Credentials Setup）：获取步骤、安全说明（不回显明文、不记录日志）、失效处理。
  - 使用建议（Best Practices）：降低风控风险的建议、默认限流参数说明。
  - 故障排查（Troubleshooting）：检查凭证→降频→启用代理→升级抓取库的排障流程。
  - 功能特性、目录结构、技术栈、许可说明。
- [FACT] `docs/ops/troubleshooting.md` 已创建，包含以下章节：
  - 排障流程总览与检索图。
  - 认证相关问题（401/403）的诊断与解决。
  - 限流相关问题（429/超时）的诊断与解决，含推荐保守配置参数表。
  - 代理配置方法与常见问题。
  - 抓取库相关问题（解析错误/scraper error）的诊断与解决。
  - 文件系统问题（目录不可写/磁盘空间不足）。
  - ffmpeg 相关问题（未安装/处理失败）。
  - 常见错误代码速查表。
- [TEST] `README.md` 与 `docs/ops/troubleshooting.md` 均为合法 Markdown 文件。

## 3) 已落实的关键行为（验收对齐）

- [CONTRACT] 一键启动路径：`git clone` → `python3 -m venv` → `pip install -r requirements.txt` → `uvicorn src.backend.app:app --host 127.0.0.1 --port 8000`。
- [CONTRACT] 风险提示位于 README 顶部显著位置，使用 blockquote 格式强调。
- [CONTRACT] 凭证说明：明确工具不自动获取凭证、保存后仅显示"已设置"不回显明文、凭证不记录日志。
- [CONTRACT] 排障步骤：1) 检查凭证 → 2) 降低频率 → 3) 启用代理 → 4) 升级抓取库，每步给出症状/原因/解决方案。

## 4) 接口/行为变更对其他模块的影响（实现时必须对齐）

- [IMPACT] 无代码变更，仅文档更新。
- [IMPACT] 文档中引用的命令与路径（`uvicorn src.backend.app:app`、`pip install --upgrade twscrape`）需与实际项目结构保持一致。

## 5) 显式限制 / 风险 / 未完成 TODO

- [LIMIT] README 中的 `<repository-url>` 占位符需在实际发布时替换为真实仓库地址。
- [LIMIT] 故障排查指南中的 twscrape GitHub Issues 链接假设用户能访问外网。
- [RISK] 平台接口变更时，文档中的排障建议可能需要同步更新。


# Agent 接入实测 · 2026-09-27

结论：本地资源与调用链路通过；线上四种方法目前均不可用，不能标为“接入完成”。

## 实测结果

| 方式 | 本地验证 | 公网验证 |
|---|---|---|
| Skill | 经 HTTP 下载 ZIP，核对 SKILL.md / README、技能名称、数据地址；按说明读取 health / items / briefing | ZIP 与安装说明均 HTTP 404；未在实际 Agent 客户端安装并测试触发 |
| MCP | 下载 ZIP，解压后使用真实 MCP SDK 启动 stdio；发现三个工具，成功调用健康、论文筛选、日报和空结果。16 条论文筛选结果均来自本地发布快照 | 使用生产代码及固定公网地址调用 sih_health，返回工具错误；依赖的 health.json 为 HTTP 404 |
| RSS | HTTP 下载，解析 RSS 2.0，检查原文链接、带时区日期及 GUID；28 条与 JSON 当前集合一致 | feed.xml 为 HTTP 404；未测试第三方阅读器订阅 |
| API | HTTP 读取三个 JSON，逐一通过 OpenAPI 响应结构校验；MCP 读取相同 HTTP 数据 | health/items/briefing 三个端点均 HTTP 404 |

本地测试使用临时回环 HTTP 服务，路径保留 `/ai-health-intel/`。MCP 使用下载包中的原始 server.py，测试进程内仅将数据根地址指向该回环服务；没有改写生产配置，没有使用 stub loader 代替 HTTP 请求。

首轮公网探测的 10 个资源均返回 HTTP 404。16:40 北京时间复测时，8 个资源仍为 404，items.json 和 Skill ZIP 遇到网络连接错误；本地检查再次全部通过，公网仍未验证可用。

公网探测还检查了 `sih-mcp.zip`、`sih-mcp/README.md`、`openapi.json`、`llms.txt`，同样为 HTTP 404。代码尚未部署，页面上的接入文案不等于公网已可用。本地预览的接入页已增加此说明。

## 复现

先构建页面，再使用 MCP 虚拟环境运行：

```powershell
python scripts/build_site.py
.venv-mcp\Scripts\python.exe scripts/verify_access.py
```

依赖来自 `integrations/mcp/requirements.txt`。详细 JSON 结果写入 `output/access-verification.json`；脚本不写用户 Skill 目录、不改客户端 MCP 设置。

部署后需重新执行公网检查，并在选定 Agent 客户端完成 Skill 安装/触发和 MCP 接入，在 RSS 阅读器完成订阅。当前结果不能替代这些验收。

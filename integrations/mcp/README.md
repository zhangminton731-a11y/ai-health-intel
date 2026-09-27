# 循证人初本地 MCP

只读访问本站固定的公开 JSON 地址，不需要 API Key。适用于支持本地 stdio MCP 的桌面 Agent；手机客户端只有在自身支持此类接入时才可使用。没有远程 MCP URL。

## 安装

需要 Python 3.10+。下载并解压 sih-mcp.zip，在 sih-mcp 目录运行：

```sh
python -m venv .venv
```

Windows：`.venv\Scripts\python.exe -m pip install -r requirements.txt`

macOS/Linux：`.venv/bin/python -m pip install -r requirements.txt`

在 Agent 的 MCP 设置中新增本地 stdio 服务。以下是常见 JSON 配置形状，具体设置入口依客户端而定；替换两个绝对路径：

```json
{"mcpServers":{"sih-intel":{"command":"/absolute/path/to/.venv/bin/python","args":["/absolute/path/to/sih-mcp/server.py"]}}}
```

Windows 的 command 使用虚拟环境内 python.exe 的绝对路径，JSON 路径可以使用正斜杠。

## 验证

连接后应看到 sih_health、sih_items、sih_briefing 三个工具。先调用 sih_health，再询问“给我最近一周医学科研论文精选，最多 5 条，附来源和原文”。不足 5 条如实返回。

section: research / industry / all；category: papers / methods / policy / products / technology / business / regulation / overview / all；stage: design / data / analysis / validation / all；keyword 在本地过滤，不发送给本站；limit 1–30；days 0–10，按北京日期回看，不支持精确小时窗口。

读取失败会返回工具错误；超过 36 小时会带 stale 和 warning，不能当作实时结果。网站部署完成前若接口不存在，也会明确报错。

更新：下载新包，比较改动后替换本目录，再按 requirements.txt 安装依赖并重启 MCP。本站不会自动修改用户现有 MCP 配置。

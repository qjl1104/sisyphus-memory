# Sisyphus Memory

给多个 AI 助手共享的本地记忆工具。助手可以读取 Markdown 摘要恢复上下文，也可以搜索已保存的记忆和导入的 Codex 对话，再按记录 ID 读取原文。

| 层级 | 默认位置 | 用途 |
| --- | --- | --- |
| 摘要 | `~/.omo/memory.md` | 保存稳定的偏好、项目索引和关键决定 |
| 语义库 | `~/.omo/chroma/` | 保存原文、时间、会话标识和检索向量 |

## Windows 安装

在安装了 Python 3.12 和 `py` 启动器的 Windows 上，从仓库目录运行 PowerShell 脚本。

```powershell
.\install.ps1
```

脚本在 `~/.omo` 下准备 CLI、Python 虚拟环境和空白摘要。已有安装用 `.\install.ps1 -Update` 更新命令和依赖，摘要和数据库会保留。可以用 `-OmoHome` 安装到其他位置，运行时将 `OMO_HOME` 设为同一个目录。

## Linux 和 macOS 安装

在仓库目录中运行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

以下示例中的 `python` 指安装了这些依赖的 Python。Windows 安装脚本默认使用 `$HOME/.omo/venv/Scripts/python.exe`。

## 导入和查找 Codex 历史

```bash
python memory_tool.py import-codex
python memory_tool.py search '上次为什么改了发布流程'
python memory_tool.py get '搜索结果里的记录 ID'
```

- 导入默认扫描 `CODEX_HOME`（未设置时为 `~/.codex`）下的 `sessions/` 和 `archived_sessions/`。可用 `import-codex --codex-home 路径` 将另一个本地 Codex 目录导入同一个记忆库。只导入你愿意向该库使用者开放的历史。
- 导入用户和助手文本消息，保存会话 ID、消息时间和项目路径（日志提供时）。工具调用、推理、系统与开发者消息、非文本附件和仅保存在云端的会话不在导入范围内。
- 可以定期重跑同一条命令。读取位置保存在 `OMO_HOME/codex-import.sqlite3`，新增行在下次运行时处理，重复导入、归档移动和中断重试通过稳定的消息 ID 去重。
- `search --json` 返回 ID、预览、分数和来源字段，`get --json` 返回完整文本和来源字段。向量模型对长文本只编码开头的一段，`get` 仍返回完整原文。

## 只读 MCP

MCP 提供 `memory_search`、`memory_get` 和 `memory_summary`。写入、导入和清空仍通过本地 CLI 执行。每个已授权的 MCP 客户端都能查询该 `OMO_HOME` 的全部内容。

在仓库目录中为 Codex 注册本地 stdio MCP：

```bash
codex mcp add sisyphus-memory --env OMO_HOME="$HOME/.omo" -- "$PWD/.venv/bin/python" "$PWD/memory_tool.py" mcp
codex mcp list
```

其他支持 stdio MCP 的客户端使用同样的命令、参数和环境变量：

```json
{
  "mcpServers": {
    "sisyphus-memory": {
      "command": "/absolute/path/to/python",
      "args": ["/absolute/path/to/memory_tool.py", "mcp"],
      "env": {"OMO_HOME": "/absolute/path/to/memory-home"}
    }
  }
}
```

切换 Codex 账号后，新会话仍可使用同一个本地配置和记忆目录。若账号使用不同的配置目录，分别添加 MCP，并指向同一个 `OMO_HOME`。启动新会话后用 `/mcp` 确认连接，可让助手先搜索，再按 ID 引用原文。

跨设备可在存有记忆库的机器上启动 Streamable HTTP：

```bash
# 先在服务进程环境中设置 SISYPHUS_MCP_TOKEN 为随机生成的长令牌。
python memory_tool.py mcp --transport streamable-http --port 7332
```

服务监听 `127.0.0.1:7332/mcp`，要求 `Authorization: Bearer <token>`。跨设备可用 SSH 端口转发，或用受信任的 HTTPS 反向代理转发到本机端口（上游 Host 使用 `127.0.0.1:7332`）。支持配置 Bearer 令牌的客户端可直接连接。Codex 示例：

```bash
# 在 Codex 的进程环境中设置同一个 SISYPHUS_MCP_TOKEN。
codex mcp add sisyphus-memory --url http://127.0.0.1:7332/mcp --bearer-token-env-var SISYPHUS_MCP_TOKEN
```

如果有多台设备，让它们连接同一个服务进程。导入和手动写入在服务所在机器执行。

## 在独立目录试用

在仓库目录中运行以下命令。示例复用安装好的 Python 环境，并在当前 PowerShell 会话中通过 `OMO_HOME` 指向临时数据目录。

```powershell
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$omoDir = Join-Path $env:USERPROFILE '.omo'
$omoPython = Join-Path $omoDir 'venv\Scripts\python.exe'
$omoPreviousDataDir = $env:OMO_HOME
$env:OMO_HOME = Join-Path ([IO.Path]::GetTempPath()) ('sisyphus-demo-' + [guid]::NewGuid().ToString('N'))

try {
    & $omoPython .\memory_tool.py stats
    & $omoPython .\memory_tool.py add '示例项目使用 Markdown 维护发布清单。' --role assistant --session demo
    & $omoPython .\memory_tool.py search '发布前要检查什么' --n 5
    & $omoPython .\memory_tool.py list --limit 10
} finally {
    $env:OMO_HOME = $omoPreviousDataDir
}
```

首次写入或搜索时，Sentence Transformers 会加载 `all-MiniLM-L6-v2`。本机尚未缓存模型时需要下载。可以在运行前设置 `HF_ENDPOINT`，让 Hugging Face Hub 使用指定的服务地址。

`clear` 会清空所选目录中的语义记忆。运行前可用 `stats` 查看当前数据目录。

## 接入助手

将 [通用接入模板](docs/AGENTS.example.md) 按需合并到助手自己的指令文件。会话开始时读取摘要并按需检索，形成需要保留的决定后再写回。摘要结构可参考 [虚构记忆示例](examples/memory.example.md)。

Kimi Code 可额外安装 [Stop 提醒钩子](integrations/kimi/README.md)，在会话结束时提醒助手记录有长期价值的结论。

仓库用于分发代码与示例。真实摘要、向量库、日志和虚拟环境放在本地数据目录，单独管理和备份。

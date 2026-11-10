# Sisyphus Memory

给同一台电脑上的多个 AI 助手用的本地记忆工具。助手可以读取 Markdown 摘要恢复上下文，再按任务关键词搜索 ChromaDB 中的详细记录。

| 层级 | 默认位置 | 用途 |
| --- | --- | --- |
| 摘要 | `~/.omo/memory.md` | 保存稳定的偏好、项目索引和关键决定 |
| 语义库 | `~/.omo/chroma/` | 保存原文、时间、会话标识和检索向量 |

## Windows 安装

在安装了 Python 3.12 和 `py` 启动器的 Windows 上，从仓库目录运行 PowerShell 脚本。

```powershell
.\install.ps1
```

脚本在 `~/.omo` 下准备 CLI、Python 虚拟环境和空白摘要。它会保留已有的 CLI、虚拟环境、摘要和数据库。可以用 `-OmoHome` 安装到其他位置，运行时将 `OMO_HOME` 设为同一个目录。直接运行仓库内的 CLI 时，也可以在自己的 Python 环境中安装 `requirements.txt`。

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

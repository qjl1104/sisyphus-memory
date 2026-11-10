# Sisyphus 共享记忆接入模板

将本模板合并到支持本地文件和命令执行的 AI 助手指令中。多位助手在同一台电脑上使用同一个记忆目录。

## 会话开始

先读取 UTF-8 的 `memory.md`。当任务涉及旧项目、偏好或决定时，用任务关键词补查语义库。将记忆作为历史背景，遇到可能变化的事实时核对现状。

```powershell
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$omoDir = if ($env:OMO_HOME) { $env:OMO_HOME } else { Join-Path $env:USERPROFILE '.omo' }
$omoPython = Join-Path $omoDir 'venv\Scripts\python.exe'
$omoCli = Join-Path $omoDir 'memory_tool.py'
$omoSummary = Join-Path $omoDir 'memory.md'

if (Test-Path -LiteralPath $omoSummary) {
    Get-Content -LiteralPath $omoSummary -Raw -Encoding UTF8
}
& $omoPython $omoCli search '项目名和任务关键词' --n 5
```

上例假设 CLI 和虚拟环境也安装在记忆目录中。如果只把 `OMO_HOME` 用作数据目录，则让 `$omoPython` 和 `$omoCli` 指向实际安装位置。

## 会话结束

按用户的记忆规则记录关键决定、状态变化或后续步骤。将可长期复用的结论写进摘要的对应段落，需要按主题检索的细节存入语义库。更新摘要时保留原有结构，并在会话日志表中追加一行。

```powershell
& $omoPython $omoCli add '已确认的决定及其适用范围' --role assistant --session 'session-id'
```

只保存任务需要的内容。真实摘要和语义库留在本地，示例和代码可以进入版本控制。

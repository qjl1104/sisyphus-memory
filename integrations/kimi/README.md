# Kimi Code 记忆提醒

安装记忆工具后，将 [示例配置](config.example.toml) 中的 `[[hooks]]` 区块添加到 `~/.kimi-code/config.toml`。把命令里的 Bash 和仓库路径改成实际位置，然后重启 Kimi Code。Windows 示例使用 Git for Windows 自带的 Bash。

钩子在同一个会话首次结束时提醒助手检查是否需要保存新记忆。再次结束时，钩子通过 SQLite 数据文件和 WAL 文件的修改时间判断共享语义库是否有写入，最近 4 小时内有写入时保持安静。状态文件保存在 `hook_state/` 下，超过 7 天会自动清理。

默认从 `~/.omo` 读取数据目录并使用其中的虚拟环境和 `memory_tool.py`。如果用自定义目录，请在启动 Kimi Code 前设置 `OMO_HOME`，让钩子和记忆工具使用同一个数据目录。已有独立环境时可通过 `OMO_PYTHON` 和 `OMO_MEMORY_TOOL` 指定解释器和脚本的绝对路径。

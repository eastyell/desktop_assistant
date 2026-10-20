# AI 桌面办公助手

一个基于 Python 的桌面虚拟办公助手，具备 AI 智能对话、语音输入、桌面操作、远程 MCP 工具调用等功能。

## 功能特性

- **桌面卡通角色**：透明悬浮角色，可拖拽移动，点击打开对话窗口
- **AI 智能对话**：接入 GLM 大模型，支持自然语言交互
- **语音输入**：基于 Vosk 离线中文语音识别 + LLM 自动校正
- **桌面操作**：打开计算器、记事本、浏览器等系统应用
- **MCP 工具调用**：支持本地工具 + 远程 MCP 服务器工具
- **主题切换**：白天/夜间双主题
- **输入法支持**：Win32 API 强制焦点 + IME 关联，确保中文输入法正常工作

## 环境要求

- **操作系统**：Windows 10/11
- **Python**：3.8 及以上版本
- **麦克风**：语音输入功能需要

## 快速部署

### 方式一：一键启动（推荐）

1. 双击 `run.bat` 文件
2. 首次运行会自动安装依赖
3. 安装完成后自动启动程序

### 方式二：手动部署

```bash
# 1. 进入项目目录
cd AI_assistant

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动程序
python main.py
```

## 配置说明

编辑 `config.json` 进行个性化配置：

### LLM 大模型配置

```json
{
    "llm": {
        "provider": "auto",
        "api_key": "你的API密钥",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "GLM-5.2",
        "temperature": 0.7,
        "system_prompt": "你是一个名叫小蓝的桌面办公助手..."
    }
}
```

> 获取 GLM API Key：访问 https://open.bigmodel.cn/ 注册并创建 API Key

### MCP 远程服务器配置

```json
{
    "mcp": {
        "enabled": true,
        "servers": [
            {
                "name": "desktop_assistant",
                "type": "local",
                "description": "本地桌面操作工具集"
            },
            {
                "name": "my_remote_mcp",
                "type": "remote",
                "url": "http://your-server:port/mcp",
                "description": "远程 MCP 服务器"
            }
        ]
    }
}
```

## 目录结构

```
AI_assistant/
├── main.py                    # 程序入口
├── assistant.py               # UI 界面（Tkinter）
├── agent.py                   # AI 智能体（LLM + 工具调用）
├── mcp_client.py              # MCP 远程客户端
├── mcp_tools.py               # 本地 MCP 工具定义
├── voice_input.py             # 语音识别模块（Vosk）
├── command_executor.py        # 命令执行器
├── config.json                # 配置文件
├── requirements.txt           # 依赖列表
├── run.bat                    # Windows 启动脚本
├── README.md                  # 说明文档
└── vosk-model-small-cn-0.22/  # Vosk 中文语音模型
```

## 使用方法

1. **打开对话**：点击桌面右下角的卡通角色
2. **输入指令**：在输入框输入文字，按回车或点击"发送"
3. **语音输入**：点击 🎙️ 按钮开始录音，再次点击结束
4. **快捷操作**：底部有计算器、记事本、截图等快捷按钮
5. **拖拽窗口**：拖动对话窗口顶部标题栏可移动窗口
6. **主题切换**：点击标题栏 ☀️/🌙 按钮切换白天/夜间模式
7. **右键菜单**：右键点击卡通角色可打开菜单（对话/帮助/退出）

## 支持的桌面操作

| 指令关键词 | 功能 |
|-----------|------|
| 计算器 | 打开 Windows 计算器 |
| 记事本 | 打开记事本 |
| 画图 | 打开画图工具 |
| 资源管理器 | 打开文件资源管理器 |
| 浏览器 | 打开默认浏览器 |
| cmd / 终端 | 打开命令提示符 |
| 任务管理器 | 打开任务管理器 |
| 截图 | 打开截图工具 |
| 几点了 | 查看当前时间 |
| 今天几号 | 查看当前日期 |

## 常见问题

### Q: 语音输入不工作？
A: 确保麦克风已连接，且已安装 vosk 和 sounddevice 依赖。语音模型已内置在 `vosk-model-small-cn-0.22/` 目录中。

### Q: 中文输入法无法使用？
A: 请在系统终端（PowerShell 或 CMD）中运行程序，不要在 IDE 内置终端中运行。

### Q: AI 对话报错 429？
A: 这是 API 速率限制，程序已内置自动重试机制（最多3次）。如频繁出现，请检查 API 额度。

### Q: MCP 远程服务器连接失败？
A: 检查 `config.json` 中的 MCP 服务器 URL 是否可达，确保网络通畅。

# -*- coding: utf-8 -*-
"""MCP 工具定义：将本地桌面操作暴露为标准化工具接口，供 LLM/MCP Agent 调用。"""

import os
import subprocess
import datetime


# ── 工具注册表：每个工具遵循 MCP Tool Schema ──

TOOLS = [
    {
        "name": "open_calculator",
        "description": "打开 Windows 计算器应用",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "open_notepad",
        "description": "打开 Windows 记事本应用",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "open_paint",
        "description": "打开 Windows 画图应用",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "open_explorer",
        "description": "打开 Windows 文件资源管理器",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "open_browser",
        "description": "打开默认浏览器并可访问指定网址",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要打开的网址，默认 https://www.bing.com",
                }
            },
        },
    },
    {
        "name": "open_cmd",
        "description": "打开 Windows 命令提示符（CMD）",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "open_task_manager",
        "description": "打开 Windows 任务管理器",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "open_snipping_tool",
        "description": "打开 Windows 截图工具",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_current_time",
        "description": "获取当前系统时间",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_current_date",
        "description": "获取当前系统日期",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_command",
        "description": "执行任意 Windows 系统命令（如 dir, ipconfig 等）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 Windows 命令",
                }
            },
            "required": ["command"],
        },
    },
    {
        "name": "search_files",
        "description": "在指定目录下搜索文件名包含关键词的文件",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "文件名搜索关键词",
                },
                "path": {
                    "type": "string",
                    "description": "搜索根目录，默认为用户主目录",
                },
            },
            "required": ["keyword"],
        },
    },
    {
        "name": "list_directory",
        "description": "列出指定目录下的文件和子目录",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "目录路径，默认为当前目录",
                }
            },
        },
    },
]


def list_tools():
    """返回所有可用工具的列表。"""
    return TOOLS


def call_tool(name, args=None):
    """调用指定工具，返回 (success: bool, result: str)。"""
    args = args or {}
    handlers = {
        "open_calculator": _tool_open_calculator,
        "open_notepad": _tool_open_notepad,
        "open_paint": _tool_open_paint,
        "open_explorer": _tool_open_explorer,
        "open_browser": _tool_open_browser,
        "open_cmd": _tool_open_cmd,
        "open_task_manager": _tool_open_task_manager,
        "open_snipping_tool": _tool_open_snipping_tool,
        "get_current_time": _tool_get_current_time,
        "get_current_date": _tool_get_current_date,
        "run_command": _tool_run_command,
        "search_files": _tool_search_files,
        "list_directory": _tool_list_directory,
    }

    if name not in handlers:
        return False, f"未知工具: {name}"

    try:
        return handlers[name](args)
    except Exception as e:
        return False, f"工具执行错误: {str(e)}"


# ── 工具实现 ──

def _tool_open_calculator(_args):
    os.system("start calc")
    return True, "已打开计算器"


def _tool_open_notepad(_args):
    os.system("start notepad")
    return True, "已打开记事本"


def _tool_open_paint(_args):
    os.system("start mspaint")
    return True, "已打开画图"


def _tool_open_explorer(_args):
    os.system("start explorer")
    return True, "已打开文件资源管理器"


def _tool_open_browser(args):
    url = args.get("url", "https://www.bing.com")
    os.system(f'start "" "{url}"')
    return True, f"已打开浏览器：{url}"


def _tool_open_cmd(_args):
    os.system("start cmd")
    return True, "已打开命令提示符"


def _tool_open_task_manager(_args):
    os.system("start taskmgr")
    return True, "已打开任务管理器"


def _tool_open_snipping_tool(_args):
    os.system("start snippingtool")
    return True, "已打开截图工具"


def _tool_get_current_time(_args):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    return True, f"当前时间：{now}"


def _tool_get_current_date(_args):
    today = datetime.datetime.now().strftime("%Y年%m月%d日")
    return True, f"今天是：{today}"


def _tool_run_command(args):
    cmd = args.get("command", "")
    if not cmd:
        return False, "缺少 command 参数"
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=10
        )
        output = result.stdout or result.stderr or "(无输出)"
        if len(output) > 2000:
            output = output[:2000] + "\n... (输出已截断)"
        return True, f"命令执行结果：\n{output}"
    except subprocess.TimeoutExpired:
        return False, "命令执行超时（10秒）"
    except Exception as e:
        return False, f"命令执行失败: {str(e)}"


def _tool_search_files(args):
    keyword = args.get("keyword", "")
    path = args.get("path", os.path.expanduser("~"))
    if not keyword:
        return False, "缺少 keyword 参数"
    try:
        results = []
        for root, dirs, files in os.walk(path):
            for f in files:
                if keyword.lower() in f.lower():
                    results.append(os.path.join(root, f))
            if len(results) >= 20:
                break
        if not results:
            return True, f"在 {path} 下未找到包含「{keyword}」的文件"
        preview = "\n".join(results[:20])
        return True, f"找到 {len(results)} 个文件（最多显示20个）：\n{preview}"
    except Exception as e:
        return False, f"搜索失败: {str(e)}"


def _tool_list_directory(args):
    path = args.get("path", os.getcwd())
    try:
        entries = os.listdir(path)
        lines = []
        for e in sorted(entries)[:50]:
            full = os.path.join(path, e)
            prefix = "[DIR]" if os.path.isdir(full) else "[FILE]"
            lines.append(f"  {prefix} {e}")
        return True, f"目录 {path} 内容（共 {len(entries)} 项）：\n" + "\n".join(lines)
    except Exception as e:
        return False, f"列出目录失败: {str(e)}"

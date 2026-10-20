# -*- coding: utf-8 -*-
"""命令执行器：解析用户输入并执行对应的系统命令。"""

import os
import subprocess
import datetime


class CommandExecutor:
    """根据对话关键词匹配并执行系统命令。"""

    def __init__(self):
        # keyword -> (执行函数, 描述)
        self._commands = {
            "计算器": (self._open_calculator, "计算器"),
            "calculator": (self._open_calculator, "计算器"),
            "calc": (self._open_calculator, "计算器"),
            "记事本": (self._open_notepad, "记事本"),
            "notepad": (self._open_notepad, "记事本"),
            "画图": (self._open_paint, "画图"),
            "paint": (self._open_paint, "画图"),
            "mspaint": (self._open_paint, "画图"),
            "资源管理器": (self._open_explorer, "文件资源管理器"),
            "explorer": (self._open_explorer, "文件资源管理器"),
            "文件管理": (self._open_explorer, "文件资源管理器"),
            "浏览器": (self._open_browser, "浏览器"),
            "browser": (self._open_browser, "浏览器"),
            "网页": (self._open_browser, "浏览器"),
            "cmd": (self._open_cmd, "命令提示符"),
            "命令提示符": (self._open_cmd, "命令提示符"),
            "终端": (self._open_cmd, "命令提示符"),
            "任务管理器": (self._open_taskmgr, "任务管理器"),
            "taskmgr": (self._open_taskmgr, "任务管理器"),
            "截图": (self._open_snipping, "截图工具"),
            "snipping": (self._open_snipping, "截图工具"),
            "录音": (self._open_soundrecorder, "录音机"),
            "录音机": (self._open_soundrecorder, "录音机"),
            "soundrecorder": (self._open_soundrecorder, "录音机"),
            "时间": (self._show_time, "当前时间"),
            "time": (self._show_time, "当前时间"),
            "几点": (self._show_time, "当前时间"),
            "日期": (self._show_date, "当前日期"),
            "date": (self._show_date, "当前日期"),
            "今天": (self._show_date, "当前日期"),
            "帮助": (self._show_help, "帮助信息"),
            "help": (self._show_help, "帮助信息"),
            "你能做什么": (self._show_help, "帮助信息"),
        }

    # ---- 系统命令 ----
    def _open_calculator(self):
        os.system("start calc")

    def _open_notepad(self):
        os.system("start notepad")

    def _open_paint(self):
        os.system("start mspaint")

    def _open_explorer(self):
        os.system("start explorer")

    def _open_browser(self):
        os.system("start https://www.bing.com")

    def _open_cmd(self):
        os.system("start cmd")

    def _open_taskmgr(self):
        os.system("start taskmgr")

    def _open_snipping(self):
        os.system("start snippingtool")

    def _open_soundrecorder(self):
        # Windows 10/11 使用 UWP 录音机
        os.system('start "" "explorer.exe" "shell:AppsFolder\\Microsoft.WindowsSoundRecorder_8wekyb3d8bbwe!App"')

    def _show_time(self):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        return f"现在是 {now}"

    def _show_date(self):
        today = datetime.datetime.now().strftime("%Y年%m月%d日")
        return f"今天是 {today}"

    def _show_help(self):
        return (
            '我可以帮你做这些事情：\n'
            '  • 打开计算器（说"计算器"）\n'
            '  • 打开记事本（说"记事本"）\n'
            '  • 打开画图（说"画图"）\n'
            '  • 打开文件资源管理器（说"资源管理器"）\n'
            '  • 打开浏览器（说"浏览器"）\n'
            '  • 打开命令提示符（说"cmd"或"终端"）\n'
            '  • 打开任务管理器（说"任务管理器"）\n'
            '  • 打开截图工具（说"截图"）\n'
            '  • 打开录音机（说"录音"）\n'
            '  • 查看时间（说"几点了"）\n'
            '  • 查看日期（说"今天几号"）\n'
            '  • 查看帮助（说"帮助"）'
        )

    def execute(self, text):
        """解析输入文本，匹配命令并执行。

        Returns:
            (success: bool, reply: str)
        """
        lower = text.lower().strip()
        if not lower:
            return False, "请输入您想让我做的事情～"

        # 退出 / 关闭对话
        if lower in ("退出", "再见", "拜拜", "bye", "quit", "exit", "关闭"):
            return True, "__CLOSE__"

        for keyword, (func, desc) in self._commands.items():
            if keyword in lower:
                result = func()
                if isinstance(result, str):
                    return True, result
                return True, f"好的，已为您打开{desc}～"

        return False, (
            '抱歉，我还不太理解"{}"的意思。\n'
            '输入"帮助"可以查看我能做的事情哦～'
        ).format(text)

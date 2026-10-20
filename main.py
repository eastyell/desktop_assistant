# -*- coding: utf-8 -*-
"""桌面虚拟办公助手 - 入口文件。

功能：
  1. 桌面上显示一个透明卡通角色，可拖拽移动
  2. 左键点击角色打开对话窗口
  3. 在对话框输入指令（如"打开计算器"），助手会执行对应系统命令
  4. 右键角色可弹出菜单（对话 / 帮助 / 退出）

运行方式：
    python main.py

依赖：仅使用 Python 标准库（tkinter），无需安装任何第三方包。
"""

from assistant import DesktopAssistant


def main():
    app = DesktopAssistant()
    app.run()


if __name__ == "__main__":
    main()

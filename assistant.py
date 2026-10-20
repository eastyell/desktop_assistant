# -*- coding: utf-8 -*-
"""桌面虚拟办公助手：透明卡通角色 + 对话窗口。"""

import math
import sys
import ctypes
import tkinter as tk

from command_executor import CommandExecutor
from agent import Agent
import voice_input

_IS_WINDOWS = sys.platform == "win32"

# Win32 IME 结构体：用于把候选窗口/组合串窗口定位到输入框光标旁
if _IS_WINDOWS:
    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    class _RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    class _CANDIDATEFORM(ctypes.Structure):
        _fields_ = [("dwIndex", ctypes.c_ulong), ("dwStyle", ctypes.c_ulong),
                    ("ptCurrentPos", _POINT), ("rcArea", _RECT)]

    class _COMPOSITIONFORM(ctypes.Structure):
        _fields_ = [("dwStyle", ctypes.c_ulong),
                    ("ptCurrentPos", _POINT), ("rcArea", _RECT)]

    _CFS_POINT = 0x0002     # 组合串定位到指定点
    _CFS_FORCE_POSITION = 0x0020   # 强制组合串窗口到指定点
    _CFS_CANDIDATEPOS = 0x0040     # 候选窗口定位到指定点
    _CFS_EXCLUDE = 0x0080   # 候选窗口避开指定矩形区域

# 透明色（将被系统设为完全透明 + 鼠标穿透区域）
TRANSPARENT_COLOR = "#01a2b1"
BODY_COLOR = "#5BC0EB"
BODY_DARK = "#3A9BD5"
CHEEK_COLOR = "#FF9AA2"
EYE_COLOR = "#2C3E50"
MOUTH_COLOR = "#E74C3C"
TEXT_COLOR = "#2C3E50"


class DesktopAssistant:
    """桌面卡通助手角色窗口。"""

    SIZE = 160  # 角色画布尺寸

    def __init__(self):
        # 根窗口：普通窗口（不用 overrideredirect，避免 WS_POPUP 导致输入法失效；
        # 也不用 withdraw()，否则应用无活动窗口、子 Toplevel 无法获取键盘焦点）。
        # 缩为 1x1 并移到屏幕外，保持"已映射"状态。用 -toolwindow 隐藏任务栏图标。
        self.root = tk.Tk()
        self.root.title("")
        self.root.geometry("1x1+-10000+-10000")
        try:
            self.root.attributes("-toolwindow", True)
        except Exception:
            pass

        # 角色窗口：Toplevel + 无边框 + 透明色
        self.char_window = tk.Toplevel(self.root)
        self.char_window.title("智能办公助手")
        self.char_window.geometry(
            f"{self.SIZE}x{self.SIZE}+{self._center_x()}+{self._center_y()}"
        )
        self.char_window.overrideredirect(True)       # 无边框
        self.char_window.attributes("-topmost", True)  # 置顶
        self.char_window.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
        self.char_window.config(bg=TRANSPARENT_COLOR)

        self.executor = CommandExecutor()
        self.agent = Agent()
        self._dialogue = None

        # 拖拽状态
        self._drag_x = 0
        self._drag_y = 0
        self._drag_start = None  # 用于区分点击与拖拽

        # 动画状态
        self._blink = False
        self._frame = 0
        self._happy = 0  # 高兴表情计时（执行命令后短暂微笑）
        self._animate_paused = False  # 点击后暂停动画

        self.canvas = tk.Canvas(
            self.char_window, width=self.SIZE, height=self.SIZE,
            bg=TRANSPARENT_COLOR, highlightthickness=0
        )
        self.canvas.pack()

        self._bind_events()
        self._animate()

    # ---- 位置计算 ----
    def _center_x(self):
        return max(0, (self.root.winfo_screenwidth() - self.SIZE) - 80)

    def _center_y(self):
        return max(0, (self.root.winfo_screenheight() - self.SIZE) - 120)

    # ---- 事件绑定 ----
    def _bind_events(self):
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.char_window.bind("<Button-3>", self._on_right_click)

    def _on_press(self, event):
        self._drag_x = event.x
        self._drag_y = event.y
        self._drag_start = (event.x_root, event.y_root)

    def _on_drag(self, event):
        x = self.char_window.winfo_x() + (event.x - self._drag_x)
        y = self.char_window.winfo_y() + (event.y - self._drag_y)
        self.char_window.geometry(f"+{x}+{y}")

    def _on_release(self, event):
        if self._drag_start is None:
            return
        dx = abs(event.x_root - self._drag_start[0])
        dy = abs(event.y_root - self._drag_start[1])
        self._drag_start = None
        # 移动距离很小 → 视为点击
        if dx < 6 and dy < 6:
            self._open_dialogue()

    def _on_right_click(self, event):
        menu = tk.Menu(self.char_window, tearoff=0)
        menu.add_command(label="💬 对话", command=self._open_dialogue)
        menu.add_command(label="❓ 帮助", command=self._show_help)
        menu.add_separator()
        menu.add_command(label="🚪 退出", command=self._quit)
        menu.post(event.x_root, event.y_root)

    # ---- 绘制角色 ----
    def _draw_character(self):
        c = self.canvas
        c.delete("all")
        s = self.SIZE
        cx, cy = s // 2, s // 2 + 6

        # 上下浮动
        bob = math.sin(self._frame * 0.06) * 4
        cy += bob

        # 阴影
        c.create_oval(cx - 48, cy + 46, cx + 48, cy + 56,
                      fill="#000000", stipple="gray25", outline="")

        # 天线
        c.create_line(cx, cy - 52, cx, cy - 68, fill=EYE_COLOR, width=3)
        c.create_oval(cx - 7, cy - 78, cx + 7, cy - 64,
                      fill="#F7DC6F", outline=EYE_COLOR, width=2)

        # 身体（圆角矩形效果用椭圆）
        body_r = 50
        c.create_oval(cx - body_r, cy - body_r, cx + body_r, cy + body_r,
                      fill=BODY_COLOR, outline=BODY_DARK, width=3)

        # 高光
        c.create_oval(cx - 32, cy - 38, cx - 10, cy - 18,
                      fill="#FFFFFF", stipple="gray50", outline="")

        # 脸颊
        c.create_oval(cx - 34, cy + 6, cx - 20, cy + 18,
                      fill=CHEEK_COLOR, outline="")
        c.create_oval(cx + 20, cy + 6, cx + 34, cy + 18,
                      fill=CHEEK_COLOR, outline="")

        # 眼睛
        if self._blink:
            c.create_line(cx - 20, cy - 8, cx - 8, cy - 8,
                          fill=EYE_COLOR, width=3, capstyle="round")
            c.create_line(cx + 8, cy - 8, cx + 20, cy - 8,
                          fill=EYE_COLOR, width=3, capstyle="round")
        else:
            c.create_oval(cx - 22, cy - 16, cx - 8, cy - 2,
                          fill="white", outline=EYE_COLOR, width=2)
            c.create_oval(cx + 8, cy - 16, cx + 22, cy - 2,
                          fill="white", outline=EYE_COLOR, width=2)
            # 眼珠（朝向随机方向增加灵动感）
            look = math.sin(self._frame * 0.02) * 2
            c.create_oval(cx - 17 + look, cy - 12, cx - 11 + look, cy - 6,
                          fill=EYE_COLOR, outline="")
            c.create_oval(cx + 13 + look, cy - 12, cx + 19 + look, cy - 6,
                          fill=EYE_COLOR, outline="")

        # 嘴巴
        if self._happy > 0:
            c.create_arc(cx - 14, cy + 6, cx + 14, cy + 26,
                         start=0, extent=180, style="arc",
                         outline=MOUTH_COLOR, width=3)
        else:
            c.create_arc(cx - 12, cy + 8, cx + 12, cy + 22,
                         start=20, extent=140, style="arc",
                         outline=MOUTH_COLOR, width=3)

        # 小手
        hand_swing = math.sin(self._frame * 0.08) * 6
        c.create_oval(cx - body_r - 8, cy - 6 + hand_swing,
                      cx - body_r + 6, cy + 8 + hand_swing,
                      fill=BODY_COLOR, outline=BODY_DARK, width=2)
        c.create_oval(cx + body_r - 6, cy - 6 - hand_swing,
                      cx + body_r + 8, cy + 8 - hand_swing,
                      fill=BODY_COLOR, outline=BODY_DARK, width=2)

    # ---- 动画循环 ----
    def _animate(self):
        if not self._animate_paused:
            self._frame += 1
            # 每 ~3 秒眨一次眼
            if self._frame % 180 == 0:
                self._blink = True
                self.char_window.after(150, self._unblink)
            if self._happy > 0:
                self._happy -= 1
            self._draw_character()
        self.char_window.after(40, self._animate)

    def _unblink(self):
        self._blink = False

    def _set_happy(self):
        self._happy = 40

    # ---- 对话窗口 ----
    def _open_dialogue(self):
        if self._dialogue is not None and self._dialogue.winfo_exists():
            # 窗口仍存在（可能只是被隐藏）：恢复显示，保留聊天记录
            self._dialogue.deiconify()
            self._dialogue.attributes("-topmost", True)
            self._dialogue.lift()
            self._dialogue.after(100, self._dialogue._focus_input)
            return
        # 对话窗口的父级是 self.root（隐藏的普通窗口），
        # 而非 char_window（无边框透明窗口），这样键盘/输入法才能正常工作。
        # ref_window 用于定位（放在角色旁边）。
        self._dialogue = DialogueWindow(
            self.root, self.executor, self, ref_window=self.char_window
        )
        # 对话关闭时清理引用
        self._dialogue.protocol("WM_DELETE_WINDOW", self._on_dialogue_closed)

    def _on_dialogue_closed(self):
        """对话窗口关闭：隐藏而非销毁，保留聊天记录。"""
        if self._dialogue and self._dialogue.winfo_exists():
            self._dialogue.withdraw()

    def _show_help(self):
        self._open_dialogue()
        if self._dialogue and self._dialogue.winfo_exists():
            self._dialogue.receive("帮助")

    def _quit(self):
        try:
            if self._dialogue and self._dialogue.winfo_exists():
                self._dialogue.destroy()
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


class DialogueWindow(tk.Toplevel):
    """对话窗口：显示聊天记录 + 输入框。"""

    # 主题配置：白天 / 晚上（柔和配色，降低刺眼感）
    THEMES = {
        "day": {
            "bg": "#F2F4F8", "chat_bg": "#FAFBFC", "header_bg": "#6FA8C8",
            "entry_bg": "#FFFFFF", "btn_bg": "#E4E7EE", "btn_active": "#CFD4DE",
            "text": "#37474F", "assistant_fg": "#1976D2", "user_fg": "#388E3C",
            "system_fg": "#78909C", "scroll_bg": "#CFD4DE", "scroll_active": "#6FA8C8",
            "entry_border": "#B8C0CC",
            "assistant_bg": "#EAF4FB", "user_bg": "#EEF6EE", "system_bg": "",
        },
        "night": {
            "bg": "#252537", "chat_bg": "#323246", "header_bg": "#5B8DB0",
            "entry_bg": "#323246", "btn_bg": "#3C3C52", "btn_active": "#4A4A63",
            "text": "#C8CCD4", "assistant_fg": "#7FB3E0", "user_fg": "#81C784",
            "system_fg": "#9098B0", "scroll_bg": "#3C3C52", "scroll_active": "#5B8DB0",
            "entry_border": "#4A4A63",
            "assistant_bg": "#23394D", "user_bg": "#253D33", "system_bg": "",
        },
    }

    def __init__(self, parent, executor, assistant, ref_window=None):
        super().__init__(parent)
        self.executor = executor
        self.assistant = assistant
        self.agent = assistant.agent
        self._waiting = False
        self._theme = "day"  # 当前主题
        self._maximized = False  # 最大化状态
        self._prev_geometry = None  # 最大化前的窗口位置/尺寸
        self._listening = False  # 录音中标记
        self._transcribing = False  # 转写中标记
        self._voice_sent = False  # 语音转文字是否已发送（防止校正结果重填）
        self._recognizer = voice_input.VoiceRecognizer()

        self.overrideredirect(True)  # 去除系统标题栏
        self.geometry("460x460")
        self.attributes("-topmost", True)
        self.config(bg=self.THEMES[self._theme]["bg"])
        self.pack_propagate(False)

        self._build_ui()
        self.update_idletasks()

        # 窗口位置：放在悬浮头像左侧，对话框底部与头像垂直中心对齐
        win_w, win_h = 460, 480
        char_w = 160  # 与 DesktopAssistant.SIZE 一致
        scr_w = self.winfo_screenwidth()
        scr_h = self.winfo_screenheight()
        # 头像位置（右下角）：与 DesktopAssistant._center_x/_center_y 保持一致
        char_x = max(0, scr_w - char_w - 80)
        char_y = max(0, scr_h - char_w - 120)
        # 头像垂直中心点
        char_cy = char_y + char_w // 2
        # 对话框底部对齐头像垂直中心：y + win_h = char_cy → y = char_cy - win_h
        x = char_x - win_w - 12
        y = char_cy - win_h
        # 如果左边放不下，则放在头像上方（底部仍对齐头像中心）
        if x < 10:
            x = max(10, char_x)
            y = char_cy - win_h
        # 确保整个窗口在屏幕内
        x = max(10, min(x, scr_w - win_w - 10))
        y = max(10, min(y, scr_h - win_h - 10))
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")

        self.receive(None, greet="你好呀！我是你的桌面办公助手小蓝～\n点击下方输入框告诉我想做什么吧！")

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._focus_input)

    def _build_ui(self):
        t = self.THEMES[self._theme]

        # ── 先排底部元素（side="bottom"），确保始终可见 ──

        # 快捷按钮（最底行：常用命令）
        self._quick_frame = tk.Frame(self, bg=t["bg"])
        self._quick_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 8))
        self._quick_btns = []
        for label in ["计算器", "记事本", "截图", "录音", "帮助"]:
            btn = tk.Button(
                self._quick_frame, text=label, font=("微软雅黑", 9),
                bg=t["btn_bg"], fg=t["text"], relief="flat", bd=0,
                activebackground=t["btn_active"], activeforeground=t["text"],
                padx=12, pady=5, cursor="hand2",
                command=lambda l=label: self.receive(l)
            )
            btn.pack(side="left", padx=3)
            self._quick_btns.append(btn)

        # 输入区（输入框 + 发送按钮）
        self._input_frame = tk.Frame(self, bg=t["bg"])
        self._input_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 10))

        # 输入框：Frame 做边框 + Entry 内嵌
        self._entry_wrap = tk.Frame(self._input_frame, bg=t["entry_border"],
                                    highlightthickness=0)
        self._entry_wrap.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.entry = tk.Entry(
            self._entry_wrap, font=("微软雅黑", 12), relief="flat",
            bg=t["entry_bg"], fg=t["text"], insertbackground=t["text"],
            takefocus=1, bd=6, highlightthickness=0
        )
        self.entry.pack(fill="x")
        self.entry.bind("<Return>", lambda e: self._on_send())
        self.entry.bind("<Button-1>", lambda e: (self.entry.focus_set(), self._win32_force_focus()), add="+")
        self.entry.bind("<FocusIn>", lambda e: (self._entry_wrap.config(bg=self.THEMES[self._theme]["header_bg"]), self._win32_force_focus()), add="+")
        self.entry.bind("<FocusOut>", lambda e: self._entry_wrap.config(bg=self.THEMES[self._theme]["entry_border"]), add="+")
        # 输入/光标移动时刷新 IME 位置，使候选框跟随光标
        # （KeyPress 在候选框弹出前更新，KeyRelease 覆盖输入法接管按键的情况）
        self.entry.bind("<KeyPress>", self._win32_refresh_ime, add="+")
        self.entry.bind("<KeyRelease>", self._win32_refresh_ime, add="+")
        self.entry.bind("<ButtonRelease-1>", self._win32_refresh_ime, add="+")
        self.bind("<Configure>", lambda e: self._win32_refresh_ime() if e.widget is self else None, add="+")

        # 发送按钮
        self._send_btn = tk.Button(
            self._input_frame, text="发送", font=("微软雅黑", 11),
            bg=t["header_bg"], fg="white", relief="flat", bd=0,
            activebackground="#3A9BD5", activeforeground="white",
            padx=18, pady=7, cursor="hand2",
            command=self._on_send
        )
        self._send_btn.pack(side="right")

        # ── 顶部标题栏（可拖拽 + 窗口控制按钮 + 主题切换）──
        self._header = tk.Frame(self, bg=t["header_bg"], height=40)
        self._header.pack(side="top", fill="x")
        self._header.pack_propagate(False)
        self._header_label = tk.Label(
            self._header, text="🤖 智能办公助手", font=("微软雅黑", 12, "bold"),
            bg=t["header_bg"], fg="white"
        )
        self._header_label.pack(side="left", padx=12)

        # 主题切换按钮
        self._theme_btn = tk.Button(
            self._header, text="☀️", font=("Arial", 11),
            bg=t["header_bg"], fg="white", relief="flat", bd=0,
            activebackground="#3A9BD5", activeforeground="white",
            padx=8, pady=0, cursor="hand2",
            command=self._toggle_theme
        )
        self._theme_btn.pack(side="right", padx=2)

        # 最大化/还原按钮
        self._max_btn = tk.Button(
            self._header, text="▢", font=("Arial", 11),
            bg=t["header_bg"], fg="white", relief="flat", bd=0,
            activebackground="#3A9BD5", activeforeground="white",
            padx=8, pady=0, cursor="hand2",
            command=self._toggle_maximize
        )
        self._max_btn.pack(side="right", padx=2)

        # 关闭按钮
        self._close_btn = tk.Button(
            self._header, text="✕", font=("Arial", 11),
            bg=t["header_bg"], fg="white", relief="flat", bd=0,
            activebackground="#E74C3C", activeforeground="white",
            padx=8, pady=0, cursor="hand2",
            command=self._on_close
        )
        self._close_btn.pack(side="right", padx=2)

        # 拖拽移动窗口 + 双击最大化/还原
        self._drag_data = {"x": 0, "y": 0}
        self._header.bind("<Button-1>", self._start_drag)
        self._header.bind("<B1-Motion>", self._on_drag)
        self._header.bind("<Double-Button-1>", lambda e: self._toggle_maximize())
        self._header_label.bind("<Double-Button-1>", lambda e: self._toggle_maximize())

        # ── 聊天记录区（Frame + 滚动条）──
        self._chat_frame = tk.Frame(self, bg=t["chat_bg"], highlightthickness=0)
        self._chat_frame.pack(side="top", fill="both", expand=True, padx=10, pady=(10, 5))

        self._scrollbar = tk.Scrollbar(self._chat_frame, bg=t["scroll_bg"],
                                       troughcolor=t["scroll_bg"],
                                       activebackground=t["scroll_active"], width=10)
        self._scrollbar.pack(side="right", fill="y")

        self.chat_text = tk.Text(
            self._chat_frame, wrap="word", font=("微软雅黑", 11),
            bg=t["chat_bg"], fg=t["text"], relief="flat",
            padx=12, pady=12, spacing1=4, spacing3=4,
            state="disabled", yscrollcommand=self._scrollbar.set,
            highlightthickness=0, bd=0
        )
        self.chat_text.pack(side="left", fill="both", expand=True)
        self._scrollbar.config(command=self.chat_text.yview)

        # 配置标签样式
        self._update_text_tags()

    def _start_drag(self, event):
        self._drag_data["x"] = event.x_root
        self._drag_data["y"] = event.y_root

    def _on_drag(self, event):
        dx = event.x_root - self._drag_data["x"]
        dy = event.y_root - self._drag_data["y"]
        x = self.winfo_x() + dx
        y = self.winfo_y() + dy
        self.geometry(f"+{x}+{y}")
        self._drag_data["x"] = event.x_root
        self._drag_data["y"] = event.y_root

    def _focus_input(self):
        self.focus_force()        # 强制将对话窗口设为前台活动窗口
        self.entry.focus_set()    # 再将焦点设到输入框
        self._win32_force_focus() # Win32 API 兜底：强制焦点 + 关联输入法

    def _win32_force_focus(self):
        """用 Win32 API 强制焦点 + 关联IME + 定位候选窗口到输入框旁边。"""
        if not _IS_WINDOWS:
            return
        try:
            user32 = ctypes.windll.user32
            imm32 = ctypes.windll.imm32

            GA_ROOT = 2
            root_hwnd = user32.GetAncestor(self.winfo_id(), GA_ROOT)

            fore_hwnd = user32.GetForegroundWindow()
            fore_tid = user32.GetWindowThreadProcessId(fore_hwnd, None)
            cur_tid = ctypes.windll.kernel32.GetCurrentThreadId()
            attached = False
            if fore_tid and fore_tid != cur_tid:
                attached = bool(user32.AttachThreadInput(cur_tid, fore_tid, True))

            user32.SetForegroundWindow(root_hwnd)
            if user32.IsIconic(root_hwnd):
                user32.ShowWindow(root_hwnd, 9)  # SW_RESTORE

            entry_hwnd = self.entry.winfo_id()
            user32.SetFocus(entry_hwnd)

            # 确保 IME 上下文已关联
            himc = imm32.ImmGetContext(entry_hwnd)
            if not himc:
                himc = imm32.ImmCreateContext()
                imm32.ImmAssociateContext(entry_hwnd, himc)
                himc = imm32.ImmGetContext(entry_hwnd)
            if himc:
                imm32.ImmReleaseContext(entry_hwnd, himc)

            # 定位 IME 候选窗口
            self._win32_set_ime_position(entry_hwnd)

            if attached:
                user32.AttachThreadInput(cur_tid, fore_tid, False)
        except Exception as e:
            print(f"[Win32 focus] {e}")

    def _win32_set_ime_position(self, entry_hwnd):
        """聚焦时强制设置一次 IME 位置（组合串 + 候选窗口）。"""
        self._win32_update_ime(entry_hwnd, force=True)

    def _win32_refresh_ime(self, _event=None):
        """输入/移动窗口时：位置有变化才重新设置，避免抖动。"""
        self._win32_update_ime(self.entry.winfo_id(), force=False)

    def _win32_update_ime(self, entry_hwnd, force=False):
        """把 IME 组合串窗口和候选窗口定位到输入框光标下方。"""
        if not _IS_WINDOWS:
            return
        try:
            # 窗口屏幕位置仅用于变化检测（窗口移动后即使客户区坐标不变，
            # 也必须重新通知 IME，否则候选框停留在旧屏幕位置）
            wx = self.winfo_rootx()
            wy = self.winfo_rooty()
            rw = self.entry.winfo_width()
            rh = self.entry.winfo_height()
            if rw <= 1 or rh <= 1:
                return

            # 插入光标在输入框内的像素位置（客户区坐标）
            cx = self.entry.index("insert")
            try:
                bbox = self.entry.bbox(cx)  # 光标处字符的 (x, y, w, h)
            except Exception:
                bbox = None
            if bbox:
                caret_x, caret_y, _, caret_h = bbox
            else:
                try:
                    caret_x = tk.Font(font=self.entry.cget("font")).measure(
                        self.entry.get()[:cx])
                except Exception:
                    caret_x = 0
                caret_h = min(20, rh - 4)
                caret_y = max(2, (rh - caret_h) // 2)

            # 客户区坐标：贴近输入框底边（候选框从此点向下展开，不遮挡文字）。
            # 注意：pt 必须在客户区内，越界坐标会被输入法忽略并回退到默认位置。
            pt_x = min(caret_x + 2, rw - 4)
            pt_y = rh - 2

            # 输入法跟随的是系统光标的"屏幕位置"。窗口移动后光标的客户区
            # 坐标不变，SetCaretPos 坐标不变时系统不发位置通知，输入法会一直
            # 用旧的屏幕位置——所以窗口移动后必须销毁重建光标来强制通知。
            # 但 IMM32 位置设置必须每次都调用（输入法每次开始新组合串都会
            # 重新读取，跳过会导致第二次输入回到旧位置）。
            pos = (wx, wy, int(caret_x), int(caret_y))
            last = getattr(self, "_ime_last_pos", None)
            window_moved = force or last is None or last[0] != wx or last[1] != wy
            self._ime_last_pos = pos

            user32 = ctypes.windll.user32
            caret_changed = last is None or last[2:] != pos[2:]
            if window_moved:
                user32.DestroyCaret()  # 强制输入法重新读取光标屏幕位置
                user32.CreateCaret(entry_hwnd, None, 2, max(int(caret_h), 4))
                user32.SetCaretPos(int(caret_x), int(caret_y))
                user32.ShowCaret(entry_hwnd)
            elif caret_changed:
                # 光标移动（打字/点击）但窗口没动：直接更新位置即可
                user32.SetCaretPos(int(caret_x), int(caret_y))

            imm32 = ctypes.windll.imm32
            himc = imm32.ImmGetContext(entry_hwnd)
            if not himc:
                return
            try:
                pt = _POINT(pt_x, pt_y)
                rc = _RECT(0, 0, rw, rh)

                # 组合串窗口：强制定位到光标点（CFS_FORCE_POSITION）
                cf = _COMPOSITIONFORM()
                cf.dwStyle = _CFS_FORCE_POSITION
                cf.ptCurrentPos = pt
                cf.rcArea = rc
                imm32.ImmSetCompositionWindow(himc, ctypes.byref(cf))

                # 候选窗口：定位到光标下方（CFS_CANDIDATEPOS）
                cand = _CANDIDATEFORM()
                cand.dwIndex = 0
                cand.dwStyle = _CFS_CANDIDATEPOS
                cand.ptCurrentPos = pt
                cand.rcArea = rc
                imm32.ImmSetCandidateWindow(himc, ctypes.byref(cand))
            finally:
                imm32.ImmReleaseContext(entry_hwnd, himc)
        except Exception as e:
            print(f"[IME pos] {e}")

    def _toggle_theme(self):
        """切换白天/晚上主题。"""
        self._theme = "night" if self._theme == "day" else "day"
        self._theme_btn.config(text="🌙" if self._theme == "night" else "☀️")
        self._apply_theme()

    def _apply_theme(self):
        """应用当前主题到所有控件。"""
        t = self.THEMES[self._theme]
        # 窗口背景
        self.config(bg=t["bg"])
        # 各 Frame
        self._quick_frame.config(bg=t["bg"])
        self._input_frame.config(bg=t["bg"])
        self._entry_wrap.config(bg=t["entry_border"])
        self._chat_frame.config(bg=t["chat_bg"])
        # 标题栏
        self._header.config(bg=t["header_bg"])
        self._header_label.config(bg=t["header_bg"])
        for btn in (self._theme_btn, self._max_btn, self._close_btn):
            btn.config(bg=t["header_bg"])
        # 快捷按钮
        for btn in self._quick_btns:
            btn.config(bg=t["btn_bg"], fg=t["text"], activebackground=t["btn_active"])
        # 输入框
        self.entry.config(bg=t["entry_bg"], fg=t["text"], insertbackground=t["text"])
        # 发送按钮
        self._send_btn.config(bg=t["header_bg"])
        # 聊天区文字
        self.chat_text.config(bg=t["chat_bg"], fg=t["text"])
        # 滚动条
        self._scrollbar.config(bg=t["scroll_bg"], troughcolor=t["scroll_bg"],
                               activebackground=t["scroll_active"])
        # 更新文本标签（含背景色）
        self._update_text_tags()

    def _update_text_tags(self):
        """更新聊天文本标签的颜色和背景色。"""
        t = self.THEMES[self._theme]
        self.chat_text.tag_config("assistant", foreground=t["assistant_fg"],
                                  background=t["assistant_bg"], lmargin1=10, lmargin2=10,
                                  spacing1=6, spacing3=6)
        self.chat_text.tag_config("user", foreground=t["user_fg"],
                                  background=t["user_bg"], lmargin1=10, lmargin2=10,
                                  spacing1=6, spacing3=6)
        self.chat_text.tag_config("system", foreground=t["system_fg"],
                                  lmargin1=10, lmargin2=10, spacing1=4, spacing3=4)

    def _toggle_maximize(self):
        """切换最大化/还原。"""
        if self._maximized:
            # 还原
            if self._prev_geometry:
                self.geometry(self._prev_geometry)
            self._maximized = False
            self._max_btn.config(text="▢")
        else:
            # 最大化
            self._prev_geometry = self.geometry()
            scr_w = self.winfo_screenwidth()
            scr_h = self.winfo_screenheight()
            self.geometry(f"{scr_w}x{scr_h}+0+0")
            self._maximized = True
            self._max_btn.config(text="❐")

    def _append(self, who, text):
        self.chat_text.config(state="normal")
        icons = {"assistant": "🤖", "user": "👤", "system": "💡"}
        names = {"assistant": "小蓝", "user": "你", "system": ""}
        icon = icons.get(who, "")
        name = names.get(who, "")
        if who == "system":
            line = f"{icon} {text}\n\n"
        else:
            line = f"{icon} {name}：{text}\n\n"
        self.chat_text.insert("end", line, who)
        self.chat_text.see("end")
        self.chat_text.config(state="disabled")

    def receive(self, text=None, greet=None):
        """接收用户输入并回复，或显示问候语。"""
        if greet:
            self._append("assistant", greet)
            return

        if not text:
            return

        # 退出命令
        if text.lower() in ("退出", "再见", "拜拜", "bye", "quit", "exit", "关闭"):
            self._append("user", text)
            self._append("assistant", "再见！期待下次为你服务～ 👋")
            self.after(500, self._on_close)
            return

        self._append("user", text)
        self._handle_ai_chat(text)

    def _handle_ai_chat(self, text):
        """调用 Agent 进行 LLM + 工具调用。"""
        if self._waiting:
            self._append("system", "请稍候，我正在思考中...")
            return

        self._waiting = True
        # 插入"思考中"提示，加 thinking 标签以便后续精确删除（不破坏历史消息的 assistant/user 标签）
        self.chat_text.config(state="normal")
        self.chat_text.insert("end", "💡 🤔 思考中...\n\n", ("system", "thinking"))
        self.chat_text.see("end")
        self.chat_text.config(state="disabled")

        def on_reply(reply_text):
            self.after(0, lambda: self._append("assistant", reply_text))

        def on_tool_call(name, args):
            arg_str = ", ".join(f"{k}={v}" for k, v in args.items()) if args else ""
            self.after(0, lambda: self._append("system", f"🔧 调用工具: {name}({arg_str})"))

        def on_done(final_reply):
            self.after(0, self._on_ai_done)

        self.agent.chat(text, on_reply=on_reply, on_tool_call=on_tool_call, on_done=on_done)

    def _on_ai_done(self):
        """AI 回复完成后清理状态。"""
        self._waiting = False
        # 仅删除带 thinking 标签的"思考中"提示（保留 assistant/user 标签，确保主题切换时历史底色仍分层）
        self.chat_text.config(state="normal")
        ranges = self.chat_text.tag_ranges("thinking")
        if ranges:
            for i in range(0, len(ranges), 2):
                self.chat_text.delete(ranges[i], ranges[i + 1])
        self.chat_text.config(state="disabled")
        self.assistant._set_happy()

    def _on_send(self):
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        # 标记语音已发送，防止 LLM 校正结果再写回输入框
        self._voice_sent = True
        self.receive(text)

    def _on_voice_toggle(self):
        """点击话筒按钮：切换录音状态（点击开始，再点击停止）。"""
        if getattr(self, "_transcribing", False):
            return

        try:
            if not self._listening:
                # 开始录音
                if not voice_input.is_available():
                    return
                self._listening = True
                self._mic_btn.config(text="🔴", bg="#E74C3C",
                                     activebackground="#C0392B", cursor="arrow",
                                     font=("Arial", 13))

                def on_partial(text):
                    def _update():
                        self.entry.delete(0, "end")
                        self.entry.insert(0, text)
                    self.after(0, _update)

                self._recognizer.start(on_result=on_partial, on_status=None)
            else:
                # 停止录音 → 立即显示原始结果 + 后台 LLM 校正
                self._listening = False
                self._transcribing = True
                self._mic_btn.config(text="⏳", bg="#95A5A6",
                                     activebackground="#7F8C8D", cursor="arrow",
                                     state="disabled", font=("Arial", 13))

                self._voice_sent = False  # 标记此轮语音未发送

                def on_final(text):
                    def _update():
                        # 立即显示原始识别结果
                        self._transcribing = False
                        t = self.THEMES[self._theme]
                        self._mic_btn.config(text="🎙️", bg=t["header_bg"],
                                             activebackground="#3A9BD5",
                                             cursor="hand2", state="normal",
                                             font=("Arial", 13))
                        if text and not getattr(self, "_voice_sent", False):
                            self.entry.delete(0, "end")
                            self.entry.insert(0, text)
                            self.entry.focus_set()
                    self.after(0, _update)

                def on_corrected(text):
                    def _update():
                        # LLM 校正完成后替换文字（如果用户还没发送）
                        if text and not getattr(self, "_voice_sent", False):
                            self.entry.delete(0, "end")
                            self.entry.insert(0, text)
                    self.after(0, _update)

                self._recognizer.stop(on_result=on_final, on_status=None,
                                      on_corrected=on_corrected)
        except Exception:
            # 任何异常都恢复按钮状态，防止卡死
            self._listening = False
            self._transcribing = False
            t = self.THEMES[self._theme]
            self._mic_btn.config(text="🎙️", bg=t["header_bg"],
                                 activebackground="#3A9BD5",
                                 cursor="hand2", state="normal",
                                 font=("Arial", 13))

    def _on_close(self):
        """关闭 = 隐藏窗口（withdraw），聊天记录保留，再次打开时恢复。"""
        self.withdraw()

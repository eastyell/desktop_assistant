# -*- coding: utf-8 -*-
"""语音输入模块：基于 Vosk 的本地中文语音识别 + LLM 自动校正。

微信式体验：边说边输入 + 自动矫正。
- 录音中实时显示部分识别结果（边说边输入）
- 识别到完整句子后自动更新
- 停止后 LLM 校正同音字错误（1-3秒）
- 纯 Python Vosk，不会 native 崩溃
"""

import sys
import os
import json
import threading
import numpy as np

_IS_WINDOWS = sys.platform == "win32"

# 模型路径（与 voice_input.py 同目录）
_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "vosk-model-small-cn-0.22")

_MODEL = None
_MODEL_LOCK = threading.Lock()

# LLM 校正配置（从 config.json 读取）
_LLM_CONFIG = None


def is_available():
    """是否支持语音输入（Vosk + sounddevice + 模型文件）。"""
    try:
        import vosk  # noqa
        import sounddevice  # noqa
        return os.path.exists(os.path.join(_MODEL_DIR, "am", "final.mdl"))
    except ImportError:
        return False


def _get_model():
    """懒加载 Vosk 模型。"""
    global _MODEL
    if _MODEL is None:
        with _MODEL_LOCK:
            if _MODEL is None:
                from vosk import Model
                _MODEL = Model(_MODEL_DIR)
    return _MODEL


def _load_llm_config():
    """加载 LLM 配置。"""
    global _LLM_CONFIG
    if _LLM_CONFIG is not None:
        return _LLM_CONFIG
    try:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        _LLM_CONFIG = cfg.get("llm", {})
    except Exception:
        _LLM_CONFIG = {}
    return _LLM_CONFIG


def correct_with_llm(text, on_done=None):
    """用 LLM 校正语音识别结果（异步，不阻塞）。

    on_done(corrected_text): 校正完成回调。失败时回调原始文本。
    """
    if not text or not text.strip():
        if on_done:
            on_done(text)
        return

    llm_cfg = _load_llm_config()
    api_key = llm_cfg.get("api_key", "")
    base_url = llm_cfg.get("base_url", "").rstrip("/")
    model = llm_cfg.get("model", "")

    if not api_key or not base_url:
        if on_done:
            on_done(text)
        return

    def _worker():
        try:
            import requests
            url = f"{base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是语音识别校正助手。请纠正以下中文语音识别结果中的同音字错误和明显错误，保持原意不变，只输出校正后的纯文字，不要加任何解释、标点或引号。"
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 512,
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            corrected = data["choices"][0]["message"]["content"].strip()
            # 去除可能的引号包裹
            corrected = corrected.strip('"').strip("'").strip(""").strip(""")
            if on_done:
                on_done(corrected if corrected else text)
        except Exception:
            if on_done:
                on_done(text)

    threading.Thread(target=_worker, daemon=True).start()


class VoiceRecognizer:
    """点击式语音识别：点击开始录音，再点击停止。

    录音中实时显示部分结果（边说边输入），完整句子后自动更新。
    停止后 LLM 校正同音字错误。
    """

    def __init__(self):
        self._running = False
        self._stream = None
        self._thread = None
        self._lock = threading.Lock()
        self._text_buffer = ""
        self._confirmed = ""
        self._recognizer = None
        self._stop_event = threading.Event()

    @property
    def is_running(self):
        return self._running

    def start(self, on_result=None, on_status=None):
        """开始录音 + 流式识别。

        on_result(text): 识别结果回调（录音中被多次调用）
        on_status(msg):  状态通知
        """
        if self._running:
            return
        if not is_available():
            return

        with self._lock:
            self._text_buffer = ""
            self._confirmed = ""
        self._running = True
        self._stop_event.clear()

        # 预加载模型 + 创建识别器
        try:
            model = _get_model()
            from vosk import KaldiRecognizer
            self._recognizer = KaldiRecognizer(model, 16000)
            self._recognizer.SetWords(True)
        except Exception:
            self._running = False
            return

        # 启动录音流（16kHz 单声道 16bit，Vosk 要求）
        try:
            import sounddevice as sd

            def callback(indata, frames, time_info, status):
                if self._running:
                    # 将 float32 转 int16 bytes 给 Vosk
                    audio_bytes = (indata * 32767).astype(np.int16).tobytes()
                    if self._recognizer.AcceptWaveform(audio_bytes):
                        # 完整句子识别完成
                        result = json.loads(self._recognizer.Result())
                        text = result.get("text", "").strip()
                        if text:
                            with self._lock:
                                self._confirmed = (self._confirmed + " " + text) if self._confirmed else text
                                self._text_buffer = self._confirmed
                            if on_result:
                                on_result(self._confirmed)
                    else:
                        # 部分结果（边说边输入）
                        partial = json.loads(self._recognizer.PartialResult())
                        ptext = partial.get("partial", "").strip()
                        if ptext:
                            with self._lock:
                                display = self._confirmed
                                display = (display + " " + ptext) if display else ptext
                                self._text_buffer = display
                            if on_result:
                                on_result(display)

            self._stream = sd.InputStream(
                samplerate=16000, channels=1, dtype="float32",
                callback=callback, blocksize=4000
            )
            self._stream.start()
        except Exception:
            self._running = False
            return

    def stop(self, on_result=None, on_status=None, on_corrected=None):
        """停止录音，返回最终文字。

        on_result(text): 原始识别结果（立即回调）
        on_corrected(text): LLM 校正后的结果（1-3秒后回调，失败时回调原始文本）
        """
        if not self._running:
            with self._lock:
                text = self._text_buffer
            if on_result:
                on_result(text)
            if on_corrected and text:
                correct_with_llm(text, on_done=on_corrected)
            elif on_corrected:
                on_corrected(text)
            return

        self._running = False

        # 停止录音流
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        # 获取最终结果
        if self._recognizer:
            try:
                result = json.loads(self._recognizer.FinalResult())
                text = result.get("text", "").strip()
                if text:
                    with self._lock:
                        self._confirmed = (self._confirmed + " " + text) if self._confirmed else text
                        self._text_buffer = self._confirmed
            except Exception:
                pass
            self._recognizer = None

        with self._lock:
            text = self._text_buffer

        # 立即返回原始识别结果
        if on_result:
            on_result(text)

        # 异步 LLM 校正
        if on_corrected and text:
            correct_with_llm(text, on_done=on_corrected)
        elif on_corrected:
            on_corrected(text)

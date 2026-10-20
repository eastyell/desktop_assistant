# -*- coding: utf-8 -*-
"""智能体 Agent：封装 LLM 对话 + MCP 工具调用循环。

支持：
  - 多 LLM 提供商（OpenAI / Anthropic / 本地模拟）
  - Function Calling / Tool Use 循环（LLM 自动决定调用工具）
  - 本地 MCP 工具（通过 mcp_tools 模块暴露桌面操作）
  - 远程 MCP 服务器（通过 mcp_client 连接 HTTP/SSE 远程服务）
  - 异步调用（后台线程 + UI 回调，不阻塞界面）
"""

import json
import os
import threading
import datetime
import time

from mcp_tools import list_tools, call_tool
from mcp_client import MCPClient


# ── 配置加载 ──

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=4)


# ── 提供商适配 ──

class LLMProvider:
    """LLM 提供商基类。"""

    def chat(self, messages, tools=None):
        """发送消息，返回 (reply_text, tool_calls_list)。
        tool_calls_list: [{"name": str, "arguments": dict}] 或 None
        """
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    """OpenAI / 兼容兼容协议的提供商。"""

    def __init__(self, api_key, base_url, model, temperature=0.7):
        try:
            import requests
        except ImportError:
            raise ImportError("请先安装 requests: pip install requests")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self._session = requests.Session()

    def chat(self, messages, tools=None):
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 429 速率限制时自动重试（指数退避）
        max_retries = 3
        for attempt in range(max_retries + 1):
            resp = self._session.post(url, json=payload, headers=headers, timeout=60)
            if resp.status_code == 429 and attempt < max_retries:
                wait = 2 ** attempt  # 1s, 2s, 4s
                print(f"[LLM] 速率限制(429)，{wait}秒后重试 ({attempt+1}/{max_retries})")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            break

        data = resp.json()

        choice = data["choices"][0]
        msg = choice["message"]
        reply_text = msg.get("content", "") or ""
        tool_calls = msg.get("tool_calls")

        parsed_calls = None
        if tool_calls:
            parsed_calls = []
            for tc in tool_calls:
                fn = tc.get("function", {})
                parsed_calls.append({
                    "name": fn.get("name", ""),
                    "arguments": json.loads(fn.get("arguments", "{}")),
                })
        return reply_text, parsed_calls


class AnthropicProvider(LLMProvider):
    """Anthropic Claude 提供商。"""

    def __init__(self, api_key, base_url, model, temperature=0.7):
        try:
            import requests
        except ImportError:
            raise ImportError("请先安装 requests: pip install requests")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self._session = requests.Session()

    def chat(self, messages, tools=None):
        url = f"{self.base_url}/messages"
        # 转换 role 格式
        api_messages = []
        for m in messages:
            role = m["role"]
            if role == "system":
                continue
            api_messages.append({"role": role, "content": m["content"]})

        payload = {
            "model": self.model,
            "messages": api_messages,
            "temperature": self.temperature,
            "max_tokens": 1024,
        }
        # 处理 system prompt
        system_msg = next((m for m in messages if m["role"] == "system"), None)
        if system_msg:
            payload["system"] = system_msg["content"]

        if tools:
            payload["tools"] = tools

        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        resp = self._session.post(url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        reply_text = ""
        tool_calls = []
        for block in data.get("content", []):
            if block["type"] == "text":
                reply_text += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append({
                    "name": block["name"],
                    "arguments": block.get("input", {}),
                })

        parsed_calls = tool_calls if tool_calls else None
        return reply_text, parsed_calls


class LocalFallbackProvider(LLMProvider):
    """本地降级：无 LLM 时的简单规则匹配。"""

    def chat(self, messages, tools=None):
        # 如果最后一条消息是 tool 结果，返回最终文本回复
        if messages and messages[-1]["role"] == "tool":
            tool_content = json.loads(messages[-1]["content"])
            result = tool_content.get("result", "")
            success = tool_content.get("success", False)
            tool_name = tool_content.get("tool_name", "")
            if success:
                return f"已为你完成操作：{result}", None
            else:
                return f"操作失败：{result}", None

        user_text = ""
        for m in reversed(messages):
            if m["role"] == "user":
                user_text = m["content"]
                break

        # 简单关键词匹配
        keyword_map = {
            ("时间", "几点", "time"): ("get_current_time", {}),
            ("日期", "几号", "date"): ("get_current_date", {}),
            ("计算器", "calculator"): ("open_calculator", {}),
            ("记事本", "notepad"): ("open_notepad", {}),
            ("画图", "paint"): ("open_paint", {}),
            ("资源管理器", "explorer", "文件管理"): ("open_explorer", {}),
            ("浏览器", "browser", "网页"): ("open_browser", {}),
            ("cmd", "终端", "命令提示符"): ("open_cmd", {}),
            ("任务管理器", "taskmgr"): ("open_task_manager", {}),
            ("截图", "snipping"): ("open_snipping_tool", {}),
        }

        for keywords, (tool_name, args) in keyword_map.items():
            if any(kw.lower() in user_text.lower() for kw in keywords):
                return f"好的，我来帮你处理。", [{"name": tool_name, "arguments": args}]

        # 无匹配 → 通用回复
        if user_text:
            return f"我收到了你的消息：「{user_text}」。目前我还没有配置 AI 大模型，你可以在 config.json 中配置 API Key 来启用 AI 智能对话。", None
        return None, None


# ── Agent 主体 ──

class Agent:
    """智能体：管理 LLM 对话 + 工具调用循环。"""

    def __init__(self):
        self.config = load_config()
        self.provider = self._create_provider()
        self.conversation_history = []
        self.max_tool_rounds = self.config.get("features", {}).get("max_tool_rounds", 5)

        # MCP 服务器连接管理
        self._mcp_clients = {}  # {server_name: MCPClient}
        self._remote_tools = []  # 从远程服务器获取的工具列表
        self._connect_mcp_servers()

        # 合并工具 schema（本地 + 远程）
        self._tool_schemas = self._build_tool_schemas()

        # 工具路由表：{tool_name: backend}  backend="local" 或 MCPClient
        self._tool_routes = self._build_tool_routes()

    def _connect_mcp_servers(self):
        """连接配置中所有远程 MCP 服务器。"""
        mcp_cfg = self.config.get("mcp", {})
        if not mcp_cfg.get("enabled", True):
            return

        servers = mcp_cfg.get("servers", [])
        for srv in servers:
            if srv.get("type") != "remote":
                continue
            url = srv.get("url", "")
            name = srv.get("name", "")
            if not url:
                continue

            try:
                client = MCPClient(url, name)
                success, info = client.initialize()
                if not success:
                    print(f"[MCP] 连接 {name} ({url}) 失败: {info}")
                    client.close()
                    continue

                success, tools = client.list_tools()
                if not success:
                    print(f"[MCP] 获取 {name} 工具列表失败: {tools}")
                    client.close()
                    continue

                self._mcp_clients[name] = client
                self._remote_tools.extend(tools)
                print(f"[MCP] 已连接 {name} ({url})，发现 {len(tools)} 个工具")
                for t in tools:
                    print(f"      - {t['name']}: {t['description']}")
            except Exception as e:
                print(f"[MCP] 连接 {name} 异常: {str(e)}")

    def _create_provider(self):
        """根据配置创建 LLM 提供商实例。"""
        llm_cfg = self.config.get("llm", {})
        provider = llm_cfg.get("provider", "auto")
        api_key = llm_cfg.get("api_key", "")
        base_url = llm_cfg.get("base_url", "")
        model = llm_cfg.get("model", "")
        temperature = llm_cfg.get("temperature", 0.7)

        # 无 api_key 或 model → 本地降级
        if not api_key or not model:
            return LocalFallbackProvider()

        # 自动识别 provider 并补全 base_url
        if provider == "auto":
            # 根据已填的 base_url 判断
            if base_url:
                if "anthropic" in base_url:
                    provider = "anthropic"
                elif "bigmodel" in base_url or "zhipu" in base_url:
                    provider = "zhipu"
                else:
                    provider = "openai"
            # 根据 model 名判断（GLM 系列 → 智谱）
            elif model.upper().startswith("GLM"):
                provider = "zhipu"
            else:
                provider = "openai"

        # 为各提供商设置默认 base_url
        default_urls = {
            "zhipu": "https://open.bigmodel.cn/api/paas/v4",
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com",
        }
        if not base_url and provider in default_urls:
            base_url = default_urls[provider]

        if not base_url:
            return LocalFallbackProvider()

        if provider == "zhipu":
            # 智谱使用 OpenAI 兼容协议
            return OpenAIProvider(api_key, base_url, model, temperature)
        elif provider == "openai":
            return OpenAIProvider(api_key, base_url, model, temperature)
        elif provider == "anthropic":
            return AnthropicProvider(api_key, base_url, model, temperature)
        else:
            return LocalFallbackProvider()

    def _build_tool_schemas(self):
        """构建 LLM 可识别的工具 schema（本地 + 远程）。"""
        schemas = []
        # 本地工具
        for tool in list_tools():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["inputSchema"],
                },
            })
        # 远程工具
        for tool in self._remote_tools:
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": f"[远程:{tool.get('server', '')}] {tool['description']}",
                    "parameters": tool["inputSchema"],
                },
            })
        return schemas

    def _build_tool_routes(self):
        """构建工具路由表，将工具名映射到对应的执行后端。"""
        routes = {}
        # 本地工具
        for tool in list_tools():
            routes[tool["name"]] = "local"
        # 远程工具
        for tool in self._remote_tools:
            server = tool.get("server", "")
            client = self._mcp_clients.get(server)
            if client:
                routes[tool["name"]] = client
        return routes

    def execute_tool(self, tool_name, arguments):
        """执行工具调用，根据路由表分发到本地或远程后端。"""
        backend = self._tool_routes.get(tool_name, "local")
        if backend == "local":
            return call_tool(tool_name, arguments)
        elif isinstance(backend, MCPClient):
            return backend.call_tool(tool_name, arguments)
        else:
            return False, f"未知的工具后端: {tool_name}"

    def get_all_tools(self):
        """返回所有可用工具（本地 + 远程）的列表。"""
        all_tools = list_tools()
        all_tools.extend(self._remote_tools)
        return all_tools

    def reset_chat(self):
        """重置对话历史。"""
        self.conversation_history = []

    def _get_system_prompt(self):
        return self.config.get("llm", {}).get("system_prompt", "")

    def chat(self, user_text, on_reply=None, on_tool_call=None, on_done=None):
        """异步发送消息，通过回调返回结果。"""
        thread = threading.Thread(
            target=self._chat_loop,
            args=(user_text, on_reply, on_tool_call, on_done),
            daemon=True,
        )
        thread.start()

    def _chat_loop(self, user_text, on_reply, on_tool_call, on_done):
        """内部：执行 LLM + 工具调用循环。"""
        try:
            self.conversation_history.append({"role": "user", "content": user_text})
            messages = self._build_messages()

            final_reply = ""
            for round_idx in range(self.max_tool_rounds):
                reply_text, tool_calls = self.provider.chat(
                    messages, tools=self._tool_schemas
                )

                if reply_text:
                    final_reply += reply_text
                    if on_reply:
                        on_reply(reply_text)

                if not tool_calls:
                    break

                assistant_msg = {"role": "assistant", "content": reply_text}
                if tool_calls:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": f"call_{round_idx}_{i}",
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])},
                        }
                        for i, tc in enumerate(tool_calls)
                    ]
                self.conversation_history.append(assistant_msg)
                messages = self._build_messages()

                for tc in tool_calls:
                    if on_tool_call:
                        on_tool_call(tc["name"], tc["arguments"])
                    success, result = self.execute_tool(tc["name"], tc["arguments"])

                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": f"call_{round_idx}_{tool_calls.index(tc)}",
                        "content": json.dumps({
                            "tool_name": tc["name"],
                            "success": success,
                            "result": result,
                        }, ensure_ascii=False),
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": f"call_{round_idx}_{tool_calls.index(tc)}",
                        "content": json.dumps({
                            "tool_name": tc["name"],
                            "success": success,
                            "result": result,
                        }, ensure_ascii=False),
                    })

            if final_reply:
                self.conversation_history.append({
                    "role": "assistant",
                    "content": final_reply,
                })

            if on_done:
                on_done(final_reply)

        except Exception as e:
            error_msg = f"智能体出错: {str(e)}"
            if on_reply:
                on_reply(error_msg)
            if on_done:
                on_done(error_msg)

    def _build_messages(self):
        """构建发送给 LLM 的消息列表。"""
        messages = []
        system_prompt = self._get_system_prompt()
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(self.conversation_history)
        return messages

    def is_available(self):
        """检查 Agent 是否已配置可用。"""
        return isinstance(self.provider, LocalFallbackProvider) or (
            self.config.get("llm", {}).get("api_key", "")
            and self.config.get("llm", {}).get("model", "")
        )

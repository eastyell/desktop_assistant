# -*- coding: utf-8 -*-
"""MCP 远程客户端：通过 HTTP/SSE 连接远程 MCP 服务器。

支持 MCP (Model Context Protocol) 协议的核心操作：
  - initialize: 与服务器握手、协商协议版本
  - tools/list: 获取服务器暴露的工具列表
  - tools/call: 调用指定工具并返回结果

参考协议: https://spec.modelcontextprotocol.io/
"""

import json
import threading
import time


class MCPClient:
    """MCP 远程服务器客户端（HTTP/SSE transport）。"""

    def __init__(self, url, name=None, timeout=30):
        """
        Args:
            url: MCP 服务器地址，如 http://192.168.0.182:8000/mcp
            name: 服务器名称，用于工具名前缀
            timeout: 请求超时秒数
        """
        self.url = url.rstrip("/")
        self.name = name or url.split("//")[-1].split("/")[0].replace(".", "_").replace(":", "_")
        self.timeout = timeout
        self._session = None
        self._next_id = 1
        self._lock = threading.Lock()
        self._initialized = False
        self._server_info = None
        self._session_id = None  # MCP Streamable HTTP 会话 ID

    def _get_session(self):
        if self._session is None:
            import requests
            self._session = requests.Session()
        return self._session

    def _next_request_id(self):
        with self._lock:
            req_id = self._next_id
            self._next_id += 1
            return req_id

    def _send_jsonrpc(self, method, params=None):
        """发送 JSON-RPC 请求并解析响应。"""
        import requests

        req_id = self._next_request_id()
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": req_id,
        }
        if params is not None:
            payload["params"] = params

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        # 后续请求需携带会话 ID（MCP Streamable HTTP 协议要求）
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        try:
            resp = self._get_session().post(
                self.url, json=payload, headers=headers, timeout=self.timeout
            )
            resp.raise_for_status()

            # 捕获服务器返回的会话 ID（initialize 响应中携带）
            session_id = resp.headers.get("Mcp-Session-Id")
            if session_id:
                self._session_id = session_id

            content_type = resp.headers.get("Content-Type", "")

            if "text/event-stream" in content_type:
                return self._parse_sse_response(resp.text, req_id)
            else:
                data = resp.json()
                if "error" in data:
                    return False, str(data["error"])
                return True, data.get("result", {})

        except requests.exceptions.ConnectionError as e:
            return False, f"连接失败: {str(e)}"
        except requests.exceptions.Timeout:
            return False, "请求超时"
        except requests.exceptions.HTTPError as e:
            return False, f"HTTP 错误: {e.response.status_code}"
        except Exception as e:
            return False, f"请求异常: {str(e)}"

    def _parse_sse_response(self, sse_text, target_id):
        """解析 SSE 流式响应，找到目标请求的结果。"""
        result = None
        for line in sse_text.split("\n"):
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if not data_str:
                continue
            try:
                data = json.loads(data_str)
                if "id" in data and data["id"] == target_id:
                    if "error" in data:
                        return False, str(data["error"])
                    result = data.get("result", {})
            except json.JSONDecodeError:
                continue

        if result is not None:
            return True, result
        return False, "未找到对应响应"

    def initialize(self, client_name="desktop_assistant", client_version="1.0.0"):
        """与 MCP 服务器握手，协商协议版本。

        Returns:
            (success: bool, server_info: dict | error_msg: str)
        """
        params = {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {
                "name": client_name,
                "version": client_version,
            },
        }
        success, result = self._send_jsonrpc("initialize", params)
        if success:
            self._initialized = True
            self._server_info = result
            return True, result
        return False, result

    def list_tools(self):
        """获取服务器暴露的工具列表。

        Returns:
            (success: bool, tools: list | error_msg: str)
            tools: [{"name": str, "description": str, "inputSchema": dict}, ...]
        """
        if not self._initialized:
            success, result = self.initialize()
            if not success:
                return False, result

        success, result = self._send_jsonrpc("tools/list")
        if success:
            tools = result.get("tools", [])
            # 标准化工具格式，加上前缀避免与本地工具冲突
            normalized = []
            for tool in tools:
                normalized.append({
                    "name": f"{self.name}__{tool.get('name', 'unknown')}",
                    "original_name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "inputSchema": tool.get("inputSchema", {"type": "object", "properties": {}}),
                    "source": "remote",
                    "server": self.name,
                })
            return True, normalized
        return False, result

    def call_tool(self, tool_name, arguments=None):
        """调用远程 MCP 工具。

        Args:
            tool_name: 工具名（含前缀，如 my_server__tool_name）
            arguments: 工具参数 dict

        Returns:
            (success: bool, result_text: str)
        """
        original_name = tool_name
        # 如果有前缀，提取原始名称
        prefix = f"{self.name}__"
        if tool_name.startswith(prefix):
            original_name = tool_name[len(prefix):]

        params = {
            "name": original_name,
            "arguments": arguments or {},
        }

        if not self._initialized:
            self.initialize()

        success, result = self._send_jsonrpc("tools/call", params)
        if not success:
            return False, f"远程工具调用失败: {result}"

        # 解析 MCP 工具返回结果
        if isinstance(result, dict):
            # MCP 结果可能是 content 数组
            content = result.get("content", [])
            if isinstance(content, list):
                texts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            texts.append(item.get("text", ""))
                        elif item.get("type") == "image":
                            texts.append("[图片数据]")
                        else:
                            texts.append(str(item))
                if texts:
                    return True, "\n".join(texts)
            # 直接返回文本
            if "result" in result:
                return True, str(result["result"])
            return True, json.dumps(result, ensure_ascii=False, indent=2)
        elif isinstance(result, str):
            return True, result
        else:
            return True, str(result)

    def is_connected(self):
        """检查连接状态。"""
        return self._initialized

    def close(self):
        """关闭会话。"""
        if self._session:
            self._session.close()
            self._session = None
        self._initialized = False
        self._session_id = None


def connect_mcp_server(url, name=None):
    """便捷函数：连接 MCP 服务器并获取工具列表。

    Args:
        url: MCP 服务器地址
        name: 可选的服务器名称

    Returns:
        (client, tools, error_msg)
        client: MCPClient 实例（连接失败时为 None）
        tools: 工具列表（连接失败时为空列表）
        error_msg: 错误信息（成功时为 None）
    """
    client = MCPClient(url, name)
    success, info = client.initialize()
    if not success:
        return None, [], f"初始化失败: {info}"

    success, tools = client.list_tools()
    if not success:
        client.close()
        return None, [], f"获取工具列表失败: {tools}"

    return client, tools, None

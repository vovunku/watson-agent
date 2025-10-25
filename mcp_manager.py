"""MCP client manager for handling multiple MCP servers."""

import asyncio
import os
from typing import Dict, List, Optional, Any

from loguru import logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import create_mcp_http_client

from mcp_config import MCPConfig, MCPServerConfig


class MockHTTPSession:
    """Mock MCP session for HTTP transport."""
    
    def __init__(self, base_url: str, http_client):
        self.base_url = base_url.rstrip('/')
        self.http_client = http_client
    
    async def initialize(self):
        """Initialize the session."""
        pass
    
    async def list_tools(self):
        """List available tools using JSON-RPC."""
        try:
            # JSON-RPC request for tools/list
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            }
            
            response = await self.http_client.post(
                self.base_url,
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
            )
            
            if response.status_code == 200:
                # Handle Server-Sent Events (SSE) response
                content = response.text
                logger.info(f"Response content from {self.base_url}: {content[:200]}...")
                
                if "event: message" in content and "data: " in content:
                    # Extract JSON from SSE format
                    lines = content.split('\n')
                    json_str = None
                    for line in lines:
                        if line.startswith("data: "):
                            json_str = line[6:]  # Remove "data: " prefix
                            break
                    
                    if json_str:
                        logger.info(f"Extracted JSON string: {json_str[:100]}...")
                        try:
                            import json
                            data = json.loads(json_str)
                            if "result" in data and "tools" in data["result"]:
                                tools = []
                                for tool_data in data["result"]["tools"]:
                                    from mcp.types import Tool
                                    tool = Tool(
                                        name=tool_data["name"],
                                        description=tool_data.get("description", ""),
                                        inputSchema=tool_data.get("inputSchema", {})
                                    )
                                    tools.append(tool)
                                logger.info(f"Found {len(tools)} tools from {self.base_url}")
                                return type('ToolsResult', (), {'tools': tools})()
                            else:
                                logger.warning(f"No tools in response from {self.base_url}: {data}")
                                return type('ToolsResult', (), {'tools': []})()
                        except Exception as e:
                            logger.error(f"Failed to parse SSE JSON from {self.base_url}: {e}")
                            return type('ToolsResult', (), {'tools': []})()
                    else:
                        logger.warning(f"No data line found in SSE response from {self.base_url}")
                        return type('ToolsResult', (), {'tools': []})()
                else:
                    # Regular JSON response
                    data = response.json()
                    if "result" in data and "tools" in data["result"]:
                        tools = []
                        for tool_data in data["result"]["tools"]:
                            from mcp.types import Tool
                            tool = Tool(
                                name=tool_data["name"],
                                description=tool_data.get("description", ""),
                                inputSchema=tool_data.get("inputSchema", {})
                            )
                            tools.append(tool)
                        logger.info(f"Found {len(tools)} tools from {self.base_url}")
                        return type('ToolsResult', (), {'tools': tools})()
                    else:
                        logger.warning(f"No tools in response from {self.base_url}: {data}")
                        return type('ToolsResult', (), {'tools': []})()
            else:
                logger.warning(f"HTTP {response.status_code} from {self.base_url}: {response.text}")
                return type('ToolsResult', (), {'tools': []})()
        except Exception as e:
            logger.error(f"Failed to list tools from {self.base_url}: {e}")
            return type('ToolsResult', (), {'tools': []})()
    
    async def list_resources(self):
        """List available resources using JSON-RPC."""
        try:
            # JSON-RPC request for resources/list
            payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/list",
                "params": {}
            }
            
            response = await self.http_client.post(
                self.base_url,
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if "result" in data and "resources" in data["result"]:
                    resources = []
                    for resource_data in data["result"]["resources"]:
                        from mcp.types import Resource
                        resource = Resource(
                            uri=resource_data["uri"],
                            name=resource_data.get("name", ""),
                            description=resource_data.get("description", ""),
                            mimeType=resource_data.get("mimeType", "text/plain")
                        )
                        resources.append(resource)
                    logger.info(f"Found {len(resources)} resources from {self.base_url}")
                    return type('ResourcesResult', (), {'resources': resources})()
                else:
                    return type('ResourcesResult', (), {'resources': []})()
            else:
                return type('ResourcesResult', (), {'resources': []})()
        except Exception as e:
            logger.error(f"Failed to list resources from {self.base_url}: {e}")
            return type('ResourcesResult', (), {'resources': []})()
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]):
        """Call a tool using JSON-RPC."""
        try:
            # JSON-RPC request for tools/call
            payload = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": name,
                    "arguments": arguments
                }
            }
            
            response = await self.http_client.post(
                self.base_url,
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    from mcp.types import TextContent
                    content = []
                    for item in data["result"].get("content", []):
                        if item.get("type") == "text":
                            content.append(TextContent(type="text", text=item["text"]))
                    return type('ToolResult', (), {
                        'content': content,
                        'isError': data["result"].get("isError", False)
                    })()
                else:
                    from mcp.types import TextContent
                    return type('ToolResult', (), {
                        'content': [TextContent(type="text", text=f"Error in response: {data}")],
                        'isError': True
                    })()
            else:
                from mcp.types import TextContent
                return type('ToolResult', (), {
                    'content': [TextContent(type="text", text=f"HTTP {response.status_code}: {response.text}")],
                    'isError': True
                })()
        except Exception as e:
            from mcp.types import TextContent
            return type('ToolResult', (), {
                'content': [TextContent(type="text", text=f"Error: {str(e)}")],
                'isError': True
            })()
    
    async def close(self):
        """Close the session."""
        await self.http_client.aclose()


def convert_mcp_tool_to_langchain(tool_info: Dict[str, Any], session: ClientSession) -> Any:
    """Convert MCP tool to LangChain tool."""
    from langchain_core.tools import BaseTool
    from typing import Dict, Any
    
    class MCPLangChainTool(BaseTool):
        name: str = tool_info["name"]
        description: str = tool_info.get("description", "")
        args_schema: Optional[Any] = None
        
        def __init__(self, tool_info: Dict[str, Any], session: ClientSession):
            super().__init__()
            self.tool_info = tool_info
            self.session = session
            self.name = tool_info["name"]
            self.description = tool_info.get("description", "")
        
        def _run(self, **kwargs) -> str:
            """Synchronous version - not supported for MCP tools."""
            raise NotImplementedError("MCP tools require async execution")
        
        async def _arun(self, **kwargs) -> str:
            """Asynchronous execution of the MCP tool."""
            try:
                result = await self.session.call_tool(self.name, kwargs)
                if result.isError:
                    return f"Error: {result.content[0].text if result.content else 'Unknown error'}"
                else:
                    return result.content[0].text if result.content else "No output"
            except Exception as e:
                return f"Error calling tool {self.name}: {str(e)}"
    
    return MCPLangChainTool(tool_info, session)


class MCPServerConnection:
    """Represents a connection to a single MCP server."""
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.session: Optional[ClientSession] = None
        self.tools: List[Dict[str, Any]] = []
        self.resources: List[Dict[str, Any]] = []
        self.connected = False
        self.last_error: Optional[str] = None
    
    async def connect(self) -> bool:
        """Connect to the MCP server."""
        try:
            if self.config.transport == "stdio":
                await self._connect_stdio()
            elif self.config.transport == "http":
                await self._connect_http()
            elif self.config.transport == "sse":
                await self._connect_sse()
            else:
                raise ValueError(f"Unsupported transport: {self.config.transport}")
            
            self.connected = True
            logger.info(f"Connected to MCP server: {self.config.name}")
            return True
            
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Failed to connect to MCP server {self.config.name}: {e}")
            return False
    
    async def _connect_stdio(self):
        """Connect via stdio transport."""
        if not self.config.cmd:
            raise ValueError("stdio transport requires cmd configuration")
        
        # Get authentication token if needed
        token = None
        if self.config.token_env:
            token = os.getenv(self.config.token_env)
            if not token:
                logger.warning(f"No token found for {self.config.name} in {self.config.token_env}")
        
        # Prepare command with token if available
        cmd = self.config.cmd.copy()
        if token:
            cmd.extend(["--token", token])
        
        # Create stdio server parameters
        server_params = StdioServerParameters(
            command=cmd[0],
            args=cmd[1:] if len(cmd) > 1 else [],
        )
        
        # Connect using stdio client
        self.session = await stdio_client(server_params)
        
        # Initialize the session
        await self.session.initialize()
        
        # List available tools and resources
        await self._list_capabilities()
    
    async def _connect_http(self):
        """Connect via HTTP transport."""
        if not self.config.url:
            raise ValueError("HTTP transport requires url configuration")
        
        # Объединяем config.headers и Authorization
        headers = dict(getattr(self.config, 'headers', {}) or {})
        
        # Get authentication token if needed
        if self.config.token_env:
            token = os.getenv(self.config.token_env)
            if token:
                headers.setdefault("Authorization", f"Bearer {token}")
            else:
                logger.warning(f"No token found for {self.config.name} in {self.config.token_env}")
        
        # Create HTTP client using official MCP library
        http_client = create_mcp_http_client(headers=headers)
        
        # Test connection by making a request to the MCP server
        try:
            # Try to connect to the MCP server
            response = await http_client.get(f"{self.config.url}/health")
            if response.status_code not in [200, 404]:  # 404 is OK if no health endpoint
                raise Exception(f"Connection test failed: {response.status_code}")
            
            logger.info(f"Successfully connected to HTTP MCP server: {self.config.name}")
        except Exception as e:
            logger.error(f"Failed to connect to HTTP MCP server {self.config.name}: {e}")
            raise
        
        # For now, we'll create a mock session that implements the MCP interface
        # In a real implementation, you'd need to implement the full MCP protocol over HTTP
        self.session = MockHTTPSession(str(self.config.url), http_client)
        
        # List available tools and resources
        await self._list_capabilities()
    
    async def _connect_sse(self):
        """Connect via SSE transport."""
        # Similar to HTTP but with Server-Sent Events
        logger.warning(f"SSE transport for {self.config.name} not implemented")
        raise NotImplementedError("SSE transport not implemented")
    
    async def _list_capabilities(self):
        """List available tools and resources from the server."""
        if not self.session:
            return
        
        try:
            # List tools
            tools_result = await self.session.list_tools()
            self.tools = tools_result.tools
            
            # List resources
            resources_result = await self.session.list_resources()
            self.resources = resources_result.resources
            
            logger.info(
                f"MCP server {self.config.name} provides {len(self.tools)} tools "
                f"and {len(self.resources)} resources"
            )
            
        except Exception as e:
            logger.error(f"Failed to list capabilities for {self.config.name}: {e}")
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on this MCP server."""
        if not self.session:
            raise Exception(f"No active session for {self.config.name}")
        
        try:
            result = await self.session.call_tool(tool_name, arguments)
            return {
                "content": result.content,
                "is_error": result.isError,
            }
        except Exception as e:
            logger.error(f"Tool call failed on {self.config.name}: {e}")
            return {
                "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                "is_error": True,
            }
    
    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self.session:
            try:
                await self.session.close()
            except Exception as e:
                logger.error(f"Error disconnecting from {self.config.name}: {e}")
            finally:
                self.session = None
                self.connected = False


class MCPManager:
    """Manages multiple MCP server connections."""
    
    def __init__(self, config: MCPConfig):
        self.config = config
        self.servers: Dict[str, MCPServerConnection] = {}
        self.connected_servers: List[str] = []
        self.all_tools: List[Dict[str, Any]] = []
        self.all_resources: List[Dict[str, Any]] = []
    
    async def initialize(self) -> bool:
        """Initialize all MCP servers."""
        if not self.config.enable_mcp:
            logger.info("MCP functionality is disabled")
            return False
        
        logger.info(f"Initializing {len(self.config.servers)} MCP servers...")
        
        # Create server connections
        for server_config in self.config.servers:
            if not server_config.enabled:
                logger.info(f"Skipping disabled server: {server_config.name}")
                continue
            
            connection = MCPServerConnection(server_config)
            self.servers[server_config.name] = connection
        
        # Connect to all servers in parallel
        connection_tasks = []
        for name, connection in self.servers.items():
            task = asyncio.create_task(self._connect_server(name, connection))
            connection_tasks.append(task)
        
        # Wait for all connections
        results = await asyncio.gather(*connection_tasks, return_exceptions=True)
        
        # Process results
        successful_connections = 0
        for i, result in enumerate(results):
            server_name = list(self.servers.keys())[i]
            if isinstance(result, Exception):
                logger.error(f"Connection to {server_name} failed: {result}")
            elif result:
                self.connected_servers.append(server_name)
                successful_connections += 1
        
        # Collect all tools and resources
        await self._collect_capabilities()
        
        logger.info(
            f"MCP initialization complete: {successful_connections}/{len(self.servers)} "
            f"servers connected, {len(self.all_tools)} tools available"
        )
        
        return successful_connections > 0
    
    async def _connect_server(self, name: str, connection: MCPServerConnection) -> bool:
        """Connect to a single server with timeout."""
        try:
            return await asyncio.wait_for(
                connection.connect(),
                timeout=connection.config.timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Connection to {name} timed out")
            return False
        except Exception as e:
            logger.error(f"Connection to {name} failed: {e}")
            return False
    
    async def _collect_capabilities(self):
        """Collect all tools and resources from connected servers."""
        self.all_tools = []
        self.all_resources = []
        
        for server_name in self.connected_servers:
            connection = self.servers[server_name]
            
            # Add tools with server prefix
            for tool in connection.tools:
                # Convert Tool object to dict and add server info
                tool_dict = tool.model_dump() if hasattr(tool, 'model_dump') else tool.__dict__
                tool_dict["server"] = server_name
                tool_dict["priority"] = connection.config.priority
                self.all_tools.append(tool_dict)
            
            # Add resources with server prefix
            for resource in connection.resources:
                # Convert Resource object to dict and add server info
                resource_dict = resource.model_dump() if hasattr(resource, 'model_dump') else resource.__dict__
                resource_dict["server"] = server_name
                self.all_resources.append(resource_dict)
        
        # Sort tools by priority (higher priority first)
        self.all_tools.sort(key=lambda x: x.get("priority", 0), reverse=True)
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any], server: Optional[str] = None) -> Dict[str, Any]:
        """Call a tool by name, finding the appropriate server."""
        if server:
            # Строгий выбор по серверу
            if server not in self.connected_servers:
                raise Exception(f"Server '{server}' is not connected")
            connection = self.servers[server]
            return await connection.call_tool(tool_name, arguments)
        
        # Старое поведение (по имени/приоритету), если server не указан
        tool_info = None
        for tool in self.all_tools:
            if tool["name"] == tool_name:
                tool_info = tool
                break
        
        if not tool_info:
            raise ValueError(f"Tool '{tool_name}' not found")
        
        server_name = tool_info["server"]
        if server_name not in self.connected_servers:
            raise Exception(f"Server '{server_name}' is not connected")
        
        connection = self.servers[server_name]
        return await connection.call_tool(tool_name, arguments)
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of all available tools."""
        return self.all_tools.copy()
    
    def get_available_resources(self) -> List[Dict[str, Any]]:
        """Get list of all available resources."""
        return self.all_resources.copy()
    
    def get_langchain_tools(self) -> List[Any]:
        """Get all MCP tools converted to LangChain tools."""
        langchain_tools = []
        
        for tool_info in self.all_tools:
            try:
                # Convert MCP tool to LangChain tool
                langchain_tool = convert_mcp_tool_to_langchain(
                    tool_info, 
                    self.servers[tool_info["server"]].session
                )
                langchain_tools.append(langchain_tool)
                logger.debug(f"Converted MCP tool '{tool_info['name']}' to LangChain tool")
            except Exception as e:
                logger.warning(f"Failed to convert MCP tool '{tool_info['name']}' to LangChain: {e}")
        
        logger.info(f"Converted {len(langchain_tools)} MCP tools to LangChain tools")
        return langchain_tools
    
    async def shutdown(self):
        """Shutdown all MCP connections."""
        logger.info("Shutting down MCP connections...")
        
        disconnect_tasks = []
        for connection in self.servers.values():
            if connection.connected:
                task = asyncio.create_task(connection.disconnect())
                disconnect_tasks.append(task)
        
        if disconnect_tasks:
            await asyncio.gather(*disconnect_tasks, return_exceptions=True)
        
        self.connected_servers.clear()
        self.all_tools.clear()
        self.all_resources.clear()
        
        logger.info("MCP shutdown complete")


# Global MCP manager instance
mcp_manager: Optional[MCPManager] = None


async def get_mcp_manager() -> Optional[MCPManager]:
    """Get the global MCP manager instance."""
    return mcp_manager


async def initialize_mcp_manager(config: MCPConfig) -> MCPManager:
    """Initialize the global MCP manager."""
    global mcp_manager
    
    if mcp_manager is None:
        mcp_manager = MCPManager(config)
        await mcp_manager.initialize()
    
    return mcp_manager


async def shutdown_mcp_manager():
    """Shutdown the global MCP manager."""
    global mcp_manager
    
    if mcp_manager:
        await mcp_manager.shutdown()
        mcp_manager = None

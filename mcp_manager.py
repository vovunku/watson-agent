"""MCP client manager for handling multiple MCP servers."""

import asyncio
import os
import subprocess
from typing import Dict, List, Optional, Any, Tuple
from contextlib import asynccontextmanager

import httpx
from loguru import logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mcp_config import MCPConfig, MCPServerConfig


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
            raise ValueError("http transport requires url configuration")
        
        # For HTTP transport, we'll use httpx client
        # This is a simplified implementation
        headers = self.config.headers or {}
        
        if self.config.token_env:
            token = os.getenv(self.config.token_env)
            if token:
                headers["Authorization"] = f"Bearer {token}"
        
        # Create HTTP client session
        async with httpx.AsyncClient(
            base_url=self.config.url,
            headers=headers,
            timeout=self.config.timeout
        ) as client:
            # Test connection
            response = await client.get("/health")
            if response.status_code != 200:
                raise Exception(f"Health check failed: {response.status_code}")
        
        # For now, create a mock session for HTTP
        # In a real implementation, you'd create an HTTP-based MCP client
        self.session = None  # Placeholder for HTTP MCP client
        logger.warning(f"HTTP transport for {self.config.name} not fully implemented")
    
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
                tool_with_server = tool.copy()
                tool_with_server["server"] = server_name
                tool_with_server["priority"] = connection.config.priority
                self.all_tools.append(tool_with_server)
            
            # Add resources with server prefix
            for resource in connection.resources:
                resource_with_server = resource.copy()
                resource_with_server["server"] = server_name
                self.all_resources.append(resource_with_server)
        
        # Sort tools by priority (higher priority first)
        self.all_tools.sort(key=lambda x: x.get("priority", 0), reverse=True)
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool by name, finding the appropriate server."""
        # Find the tool and its server
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

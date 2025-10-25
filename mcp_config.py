"""MCP configuration schemas and settings."""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server."""
    
    name: str = Field(..., description="Unique name for the MCP server")
    transport: Literal["stdio", "http", "sse"] = Field(..., description="Transport protocol")
    
    # Transport-specific configurations
    cmd: Optional[List[str]] = Field(None, description="Command for stdio transport")
    url: Optional[str] = Field(None, description="URL for http/sse transport")
    
    # Authentication
    token_env: Optional[str] = Field(None, description="Environment variable name for auth token")
    headers: Optional[Dict[str, str]] = Field(None, description="Additional headers")
    
    # Connection settings
    timeout: int = Field(30, description="Connection timeout in seconds")
    retry_attempts: int = Field(3, description="Number of retry attempts")
    
    # Server capabilities
    enabled: bool = Field(True, description="Whether this server is enabled")
    priority: int = Field(0, description="Priority for tool selection (higher = more priority)")


class AgentConfig(BaseModel):
    """Configuration for the agent behavior."""
    
    model: str = Field("anthropic/claude-3.5-sonnet", description="LLM model to use")
    max_tools_per_turn: int = Field(3, description="Maximum tools to use per turn")
    max_iterations: int = Field(10, description="Maximum agent iterations")
    temperature: float = Field(0.1, description="LLM temperature")
    max_tokens: int = Field(8000, description="Maximum tokens per response")
    
    # Agent behavior
    enable_reasoning: bool = Field(True, description="Enable step-by-step reasoning")
    enable_tool_selection: bool = Field(True, description="Enable automatic tool selection")
    enable_parallel_tools: bool = Field(False, description="Enable parallel tool execution")


class MCPConfig(BaseModel):
    """Main MCP configuration."""
    
    servers: List[MCPServerConfig] = Field(default_factory=list, description="List of MCP servers")
    agent: AgentConfig = Field(default_factory=AgentConfig, description="Agent configuration")
    
    # Global settings
    enable_mcp: bool = Field(True, description="Enable MCP functionality")
    fallback_to_direct: bool = Field(True, description="Fallback to direct LLM if MCP fails")
    debug_mode: bool = Field(False, description="Enable debug logging")


# Default MCP server configurations
DEFAULT_MCP_SERVERS = [
    MCPServerConfig(
        name="blockscout",
        transport="http",
        url="https://mcp.blockscout.com/mcp",
        priority=10,
        enabled=True,
    ),
    MCPServerConfig(
        name="foundry",
        transport="http",
        url="https://b103bb987957.ngrok-free.app/mcp",
        priority=10,
        enabled=True,
    ),
    MCPServerConfig(
        name="github",
        transport="stdio",
        cmd=["python", "-m", "mcp_github_server"],
        token_env="GITHUB_TOKEN",
        priority=5,
        enabled=False,
    ),
    MCPServerConfig(
        name="filesystem",
        transport="stdio",
        cmd=["python", "-m", "mcp_filesystem_server"],
        priority=3,
        enabled=False,
    ),
    MCPServerConfig(
        name="web_search",
        transport="http",
        url="https://mcp.websearch.example",
        token_env="WEBSEARCH_TOKEN",
        priority=2,
        enabled=False,
    ),
    MCPServerConfig(
        name="http_audit_server",
        transport="http",
        url="http://localhost:8001",
        priority=1,
        enabled=False,  # Enable for testing with local HTTP server
    ),
]


def load_mcp_config() -> MCPConfig:
    """Load MCP configuration from environment or use defaults."""
    import os
    
    # Get model from environment or use default
    model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")
    
    # For now, return default config
    # In production, this could load from YAML/JSON config files
    return MCPConfig(
        servers=DEFAULT_MCP_SERVERS,
        agent=AgentConfig(model=model),
        enable_mcp=os.getenv("ENABLE_MCP", "true").lower() == "true",
        fallback_to_direct=os.getenv("MCP_FALLBACK_TO_DIRECT", "true").lower() == "true",
        debug_mode=os.getenv("MCP_DEBUG", "false").lower() == "true",
    )

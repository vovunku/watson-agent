# MCP Agent Integration

This audit agent now supports Model Context Protocol (MCP) for enhanced smart contract auditing capabilities.

## Overview

The agent uses LangGraph with a ReAct (Reasoning and Acting) pattern to orchestrate multiple MCP servers and tools for comprehensive smart contract analysis.

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │   LangGraph      │    │   MCP Manager   │
│                 │    │   Agent          │    │                 │
│  - Job Creation │───▶│  - ReAct Pattern │───▶│  - Multi-Server │
│  - Status Check │    │  - Tool Calling  │    │  - Tool Routing │
│  - Report Fetch │    │  - State Mgmt    │    │  - Fallback     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   MCP Servers   │
                       │                 │
                       │  - BlockScout   │
                       │  - GitHub       │
                       │  - FileSystem   │
                       │  - WebSearch    │
                       │  - Solc         │
                       │  - Slither      │
                       │  - Mythril      │
                       └─────────────────┘
```

## Features

### 1. Multi-Server MCP Support
- Connect to multiple MCP servers simultaneously
- Automatic tool discovery and registration
- Priority-based tool selection
- Graceful fallback on server failures

### 2. LangGraph Agent
- ReAct pattern for reasoning and tool use
- State management across iterations
- Conversation memory
- Configurable max iterations and tool calls

### 3. Tool Integration
- Automatic conversion of MCP tools to LangChain tools
- Tool result aggregation and formatting
- Error handling and retry logic

### 4. Fallback Mechanisms
- MCP agent → Direct LLM → DRY_RUN mode
- Configurable fallback behavior
- Error recovery and logging

## Configuration

### Environment Variables

```bash
# MCP Settings
ENABLE_MCP=true
MCP_FALLBACK_TO_DIRECT=true
MCP_DEBUG=false

# API Keys for MCP Servers
BLOCKSCOUT_API_KEY=your_key
GITHUB_TOKEN=your_token
WEBSEARCH_API_KEY=your_key
ETHERSCAN_API_KEY=your_key
```

### MCP Server Configuration

Edit `mcp_config.py` or use YAML configuration:

```yaml
mcp:
  enable_mcp: true
  fallback_to_direct: true
  servers:
    - name: blockscout
      transport: http
      url: "https://api.blockscout.com/api/v2"
      token_env: "BLOCKSCOUT_API_KEY"
      priority: 10
      enabled: true
    - name: github
      transport: stdio
      cmd: ["python", "-m", "mcp_github_server"]
      token_env: "GITHUB_TOKEN"
      priority: 8
      enabled: true
```

## Available MCP Servers

### 1. BlockScout Integration
- **Purpose**: Blockchain data and transaction analysis
- **Transport**: HTTP
- **Tools**: Contract verification, transaction history, token info
- **Priority**: High (10)

### 2. GitHub Integration
- **Purpose**: Repository analysis and code history
- **Transport**: STDIO
- **Tools**: File access, commit history, issue tracking
- **Priority**: High (8)

### 3. File System Access
- **Purpose**: Local file operations
- **Transport**: STDIO
- **Tools**: File reading, directory listing
- **Priority**: Medium (5)

### 4. Web Search
- **Purpose**: Vulnerability database lookup
- **Transport**: HTTP
- **Tools**: CVE search, security advisory lookup
- **Priority**: Medium (6)

### 5. Solidity Compiler
- **Purpose**: Code compilation and analysis
- **Transport**: STDIO
- **Tools**: Compilation, AST analysis, bytecode generation
- **Priority**: High (9)

### 6. Slither Integration
- **Purpose**: Static analysis
- **Transport**: STDIO
- **Tools**: Vulnerability detection, code analysis
- **Priority**: High (7)

### 7. Mythril Integration
- **Purpose**: Symbolic execution
- **Transport**: STDIO
- **Tools**: Symbolic analysis, vulnerability detection
- **Priority**: Medium (6)

## Example MCP Server

See `examples/mcp_servers/simple_audit_server.py` for a complete example of how to create an MCP server with audit tools.

### Key Features:
- Reentrancy detection
- Access control analysis
- ERC20 compliance checking
- Vulnerability information lookup

## Usage

### 1. Enable MCP Mode

```bash
export ENABLE_MCP=true
export MCP_FALLBACK_TO_DIRECT=true
```

### 2. Configure MCP Servers

Edit the server list in `mcp_config.py` or use environment variables.

### 3. Start the Agent

```bash
make run
```

### 4. Create Audit Job

```bash
curl -X POST http://localhost:8081/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "source": {
      "type": "inline",
      "inline_code": "contract Test { function test() public {} }"
    },
    "audit_profile": "erc20_basic_v1"
  }'
```

## Agent Behavior

### 1. Initialization
1. Load MCP configuration
2. Connect to configured MCP servers
3. Discover and register available tools
4. Initialize LangGraph agent with tools

### 2. Audit Process
1. Receive audit request
2. Initialize agent state
3. Start ReAct loop:
   - **Reason**: Analyze code and decide next action
   - **Act**: Call appropriate tools
   - **Observe**: Process tool results
   - **Repeat**: Until audit complete or max iterations

### 3. Tool Selection
- Tools are prioritized by server priority
- Agent can use multiple tools per iteration
- Parallel tool execution (if enabled)
- Automatic error handling and retry

### 4. Report Generation
- Aggregate all tool results
- Generate comprehensive audit report
- Include tool usage metrics
- Provide actionable recommendations

## Monitoring and Debugging

### Logs
```bash
# Enable debug mode
export MCP_DEBUG=true

# View agent logs
docker logs audit-agent | grep "MCP\|Agent"
```

### Metrics
The agent provides detailed metrics:
- Tool usage count
- Iteration count
- Server connection status
- Error rates

### Health Checks
```bash
curl http://localhost:8081/healthz
```

## Development

### Adding New MCP Servers

1. Create MCP server implementation
2. Add configuration to `mcp_config.py`
3. Update server list in `DEFAULT_MCP_SERVERS`
4. Test with example contracts

### Custom Tools

1. Implement tool in MCP server
2. Tool will be automatically discovered
3. Agent will learn to use it through ReAct pattern

### Agent Customization

Modify `agent.py` to:
- Change reasoning prompts
- Adjust tool selection logic
- Customize report format
- Add new state management

## Troubleshooting

### Common Issues

1. **MCP Server Connection Failed**
   - Check server configuration
   - Verify API keys and tokens
   - Check network connectivity

2. **No Tools Available**
   - Ensure MCP servers are running
   - Check server initialization logs
   - Verify tool discovery process

3. **Agent Timeout**
   - Increase max iterations
   - Check tool response times
   - Enable parallel tool execution

4. **Fallback to Direct LLM**
   - Check MCP server status
   - Review error logs
   - Verify fallback configuration

### Debug Commands

```bash
# Check MCP server status
docker exec audit-agent python -c "
from mcp_manager import get_mcp_manager
import asyncio
async def check():
    manager = await get_mcp_manager()
    if manager:
        print(f'Connected servers: {manager.connected_servers}')
        print(f'Available tools: {len(manager.get_available_tools())}')
asyncio.run(check())
"

# Test MCP tool directly
docker exec audit-agent python -c "
from mcp_manager import get_mcp_manager
import asyncio
async def test():
    manager = await get_mcp_manager()
    if manager:
        result = await manager.call_tool('check_reentrancy', {'code': 'contract Test {}'})
        print(result)
asyncio.run(test())
"
```

## Performance Considerations

### Optimization Tips

1. **Tool Priority**: Set higher priority for faster tools
2. **Parallel Execution**: Enable for independent tools
3. **Caching**: Implement tool result caching
4. **Connection Pooling**: Reuse MCP connections

### Resource Usage

- Memory: ~100MB per MCP server
- CPU: Varies by tool complexity
- Network: Depends on server communication
- Storage: Minimal (state and logs)

## Security

### Best Practices

1. **API Keys**: Use environment variables
2. **Network**: Secure MCP server connections
3. **Validation**: Validate all tool inputs
4. **Sandboxing**: Run MCP servers in containers

### Access Control

- MCP servers run with limited permissions
- Tool access is controlled by server configuration
- Agent can only use explicitly configured tools

## Future Enhancements

### Planned Features

1. **Dynamic Tool Discovery**: Auto-discover new tools
2. **Tool Composition**: Chain multiple tools
3. **Learning**: Improve tool selection over time
4. **Visualization**: Tool usage graphs and metrics

### Integration Opportunities

1. **CI/CD**: Integrate with build pipelines
2. **IDE**: Real-time audit feedback
3. **Monitoring**: Continuous security monitoring
4. **Reporting**: Advanced report formats

## Contributing

### Adding New Tools

1. Fork the repository
2. Create MCP server with new tools
3. Add configuration examples
4. Submit pull request

### Testing

```bash
# Run MCP-specific tests
make test-mcp

# Test with example MCP server
python examples/mcp_servers/simple_audit_server.py
```

## Support

For issues and questions:
- Check logs: `docker logs audit-agent`
- Enable debug mode: `export MCP_DEBUG=true`
- Review configuration: `mcp_config.py`
- Test MCP servers individually

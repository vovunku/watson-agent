#!/usr/bin/env python3
"""
Simple MCP server for smart contract auditing.
This is an example of how to create an MCP server that provides audit tools.
"""

import asyncio
import json
import sys
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    Tool,
    TextContent,
)


class SimpleAuditServer:
    """Simple MCP server providing basic audit tools."""
    
    def __init__(self):
        self.server = Server("simple-audit-server")
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup MCP request handlers."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available audit tools."""
            return [
                Tool(
                    name="check_reentrancy",
                    description="Check for reentrancy vulnerabilities in smart contract code",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Solidity contract code to analyze"
                            }
                        },
                        "required": ["code"]
                    }
                ),
                Tool(
                    name="check_access_control",
                    description="Check for access control issues in smart contract code",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Solidity contract code to analyze"
                            }
                        },
                        "required": ["code"]
                    }
                ),
                Tool(
                    name="check_erc20_compliance",
                    description="Check ERC20 standard compliance",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Solidity contract code to analyze"
                            }
                        },
                        "required": ["code"]
                    }
                ),
                Tool(
                    name="get_vulnerability_info",
                    description="Get information about a specific vulnerability type",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "vulnerability_type": {
                                "type": "string",
                                "description": "Type of vulnerability to get info about"
                            }
                        },
                        "required": ["vulnerability_type"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
            """Handle tool calls."""
            try:
                if name == "check_reentrancy":
                    return await self._check_reentrancy(arguments)
                elif name == "check_access_control":
                    return await self._check_access_control(arguments)
                elif name == "check_erc20_compliance":
                    return await self._check_erc20_compliance(arguments)
                elif name == "get_vulnerability_info":
                    return await self._get_vulnerability_info(arguments)
                else:
                    return CallToolResult(
                        content=[TextContent(
                            type="text",
                            text=f"Unknown tool: {name}"
                        )],
                        isError=True
                    )
            except Exception as e:
                return CallToolResult(
                    content=[TextContent(
                        type="text",
                        text=f"Error executing tool {name}: {str(e)}"
                    )],
                    isError=True
                )
    
    async def _check_reentrancy(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Check for reentrancy vulnerabilities."""
        code = arguments.get("code", "")
        
        # Simple reentrancy detection
        issues = []
        
        # Check for external calls before state changes
        lines = code.split('\n')
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            
            # Look for external calls
            if any(call in line_lower for call in ['.call(', '.send(', '.transfer(']):
                # Check if state is modified after this line
                for j in range(i + 1, min(i + 10, len(lines))):
                    next_line = lines[j].lower().strip()
                    if any(op in next_line for op in ['=', '+=', '-=', '*=', '/=']):
                        issues.append({
                            "line": i + 1,
                            "severity": "high",
                            "description": "Potential reentrancy vulnerability: external call before state change",
                            "recommendation": "Use checks-effects-interactions pattern"
                        })
                        break
        
        result = {
            "vulnerability_type": "reentrancy",
            "issues_found": len(issues),
            "issues": issues,
            "summary": f"Found {len(issues)} potential reentrancy issues"
        }
        
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        )
    
    async def _check_access_control(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Check for access control issues."""
        code = arguments.get("code", "")
        
        issues = []
        
        # Check for functions without access control
        lines = code.split('\n')
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            
            # Look for public/external functions
            if 'function' in line_lower and ('public' in line_lower or 'external' in line_lower):
                # Check if function has access control
                has_access_control = False
                for j in range(max(0, i - 5), i):
                    prev_line = lines[j].lower().strip()
                    if any(mod in prev_line for mod in ['onlyowner', 'onlyadmin', 'onlyrole']):
                        has_access_control = True
                        break
                
                if not has_access_control:
                    # Extract function name
                    func_name = line.split('function')[1].split('(')[0].strip()
                    issues.append({
                        "line": i + 1,
                        "severity": "medium",
                        "description": f"Function '{func_name}' lacks access control",
                        "recommendation": "Add appropriate access control modifier"
                    })
        
        result = {
            "vulnerability_type": "access_control",
            "issues_found": len(issues),
            "issues": issues,
            "summary": f"Found {len(issues)} access control issues"
        }
        
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        )
    
    async def _check_erc20_compliance(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Check ERC20 standard compliance."""
        code = arguments.get("code", "")
        
        # Required ERC20 functions
        required_functions = [
            'totalSupply',
            'balanceOf',
            'transfer',
            'transferFrom',
            'approve',
            'allowance'
        ]
        
        # Required events
        required_events = ['Transfer', 'Approval']
        
        issues = []
        code_lower = code.lower()
        
        # Check for required functions
        for func in required_functions:
            if f'function {func.lower()}' not in code_lower:
                issues.append({
                    "severity": "high",
                    "description": f"Missing required ERC20 function: {func}",
                    "recommendation": f"Implement the {func} function according to ERC20 standard"
                })
        
        # Check for required events
        for event in required_events:
            if f'event {event.lower()}' not in code_lower:
                issues.append({
                    "severity": "high",
                    "description": f"Missing required ERC20 event: {event}",
                    "recommendation": f"Declare the {event} event according to ERC20 standard"
                })
        
        result = {
            "vulnerability_type": "erc20_compliance",
            "issues_found": len(issues),
            "issues": issues,
            "summary": f"Found {len(issues)} ERC20 compliance issues"
        }
        
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        )
    
    async def _get_vulnerability_info(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Get information about a specific vulnerability type."""
        vuln_type = arguments.get("vulnerability_type", "").lower()
        
        vulnerability_info = {
            "reentrancy": {
                "description": "Reentrancy attacks occur when external calls allow attackers to re-enter the contract and manipulate state",
                "common_patterns": [
                    "External calls before state changes",
                    "Using .call() or .send() without proper checks",
                    "Not following checks-effects-interactions pattern"
                ],
                "prevention": [
                    "Use checks-effects-interactions pattern",
                    "Use reentrancy guards",
                    "Avoid external calls in state-changing functions"
                ],
                "severity": "high"
            },
            "access_control": {
                "description": "Access control issues occur when functions lack proper authorization checks",
                "common_patterns": [
                    "Public functions without modifiers",
                    "Missing onlyOwner or similar modifiers",
                    "Incorrect role-based access control"
                ],
                "prevention": [
                    "Use appropriate access control modifiers",
                    "Implement role-based access control",
                    "Validate caller permissions"
                ],
                "severity": "medium"
            },
            "erc20_compliance": {
                "description": "ERC20 compliance issues occur when contracts don't properly implement the ERC20 standard",
                "common_patterns": [
                    "Missing required functions",
                    "Incorrect function signatures",
                    "Missing required events"
                ],
                "prevention": [
                    "Follow ERC20 standard specification",
                    "Implement all required functions",
                    "Emit required events"
                ],
                "severity": "high"
            }
        }
        
        info = vulnerability_info.get(vuln_type, {
            "description": f"No information available for vulnerability type: {vuln_type}",
            "common_patterns": [],
            "prevention": [],
            "severity": "unknown"
        })
        
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=json.dumps(info, indent=2)
            )]
        )
    
    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main():
    """Main entry point."""
    server = SimpleAuditServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())

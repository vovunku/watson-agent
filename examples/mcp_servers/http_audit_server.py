#!/usr/bin/env python3
"""
Simple HTTP MCP Server for Audit Agent
This server provides basic audit tools via HTTP endpoints.
"""

import asyncio
import json
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="HTTP MCP Audit Server", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock tools data
TOOLS = [
    {
        "name": "analyze_contract",
        "description": "Analyze a smart contract for security vulnerabilities",
        "inputSchema": {
            "type": "object",
            "properties": {
                "contract_code": {
                    "type": "string",
                    "description": "The Solidity contract code to analyze",
                },
                "contract_type": {
                    "type": "string",
                    "description": "Type of contract (ERC20, ERC721, etc.)",
                    "default": "general",
                },
            },
            "required": ["contract_code"],
        },
    },
    {
        "name": "check_vulnerability_db",
        "description": "Check known vulnerability databases for specific patterns",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Pattern or vulnerability type to search for",
                }
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "get_gas_estimation",
        "description": "Estimate gas usage for contract functions",
        "inputSchema": {
            "type": "object",
            "properties": {
                "contract_code": {
                    "type": "string",
                    "description": "The contract code to analyze",
                },
                "function_name": {
                    "type": "string",
                    "description": "Specific function to analyze (optional)",
                },
            },
            "required": ["contract_code"],
        },
    },
]

# Mock resources data
RESOURCES = [
    {
        "uri": "vulnerability-db",
        "name": "Vulnerability Database",
        "description": "Database of known smart contract vulnerabilities",
        "mimeType": "application/json",
    },
    {
        "uri": "gas-patterns",
        "name": "Gas Usage Patterns",
        "description": "Common gas usage patterns and optimizations",
        "mimeType": "application/json",
    },
]


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "HTTP MCP Audit Server"}


@app.get("/tools")
async def list_tools():
    """List available tools."""
    return {"tools": TOOLS}


@app.get("/resources")
async def list_resources():
    """List available resources."""
    return {"resources": RESOURCES}


@app.post("/tools/call")
async def call_tool(request: Dict[str, Any]):
    """Call a tool."""
    tool_name = request.get("name")
    arguments = request.get("arguments", {})

    if tool_name == "analyze_contract":
        contract_code = arguments.get("contract_code", "")
        contract_type = arguments.get("contract_type", "general")

        # Mock analysis
        analysis_result = {
            "vulnerabilities": [
                {
                    "severity": "medium",
                    "type": "reentrancy",
                    "description": "Potential reentrancy vulnerability detected",
                    "line": 15,
                    "recommendation": "Use checks-effects-interactions pattern",
                }
            ],
            "gas_optimizations": [
                {
                    "type": "storage_optimization",
                    "description": "Consider using packed structs",
                    "line": 8,
                }
            ],
            "summary": f"Analysis of {contract_type} contract completed. Found 1 vulnerability and 1 optimization opportunity.",
        }

        return {
            "content": [
                {"type": "text", "text": json.dumps(analysis_result, indent=2)}
            ],
            "isError": False,
        }

    elif tool_name == "check_vulnerability_db":
        pattern = arguments.get("pattern", "")

        # Mock vulnerability check
        vulnerabilities = [
            {
                "id": "CVE-2023-1234",
                "title": f"Vulnerability related to {pattern}",
                "severity": "high",
                "description": f"Known vulnerability pattern: {pattern}",
                "references": ["https://example.com/vuln1"],
            }
        ]

        return {
            "content": [
                {"type": "text", "text": json.dumps(vulnerabilities, indent=2)}
            ],
            "isError": False,
        }

    elif tool_name == "get_gas_estimation":
        contract_code = arguments.get("contract_code", "")
        function_name = arguments.get("function_name")

        # Mock gas estimation
        gas_estimate = {
            "total_gas": 21000,
            "function_estimates": {
                "deploy": 150000,
                "transfer": 21000,
                "approve": 46000,
            },
            "optimization_suggestions": [
                "Consider using assembly for gas-critical operations",
                "Use events instead of storage for non-critical data",
            ],
        }

        if function_name:
            gas_estimate["specific_function"] = {
                "name": function_name,
                "estimated_gas": gas_estimate["function_estimates"].get(
                    function_name, 21000
                ),
            }

        return {
            "content": [{"type": "text", "text": json.dumps(gas_estimate, indent=2)}],
            "isError": False,
        }

    else:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")


@app.get("/resources/{uri}")
async def read_resource(uri: str):
    """Read a resource."""
    if uri == "vulnerability-db":
        data = {
            "vulnerabilities": [
                {
                    "id": "reentrancy",
                    "name": "Reentrancy Attack",
                    "severity": "high",
                    "description": "External calls before state changes can lead to reentrancy attacks",
                },
                {
                    "id": "integer-overflow",
                    "name": "Integer Overflow/Underflow",
                    "severity": "medium",
                    "description": "Arithmetic operations without proper bounds checking",
                },
            ]
        }
    elif uri == "gas-patterns":
        data = {
            "patterns": [
                {
                    "name": "storage_optimization",
                    "description": "Pack structs to reduce storage slots",
                    "example": "struct Packed { uint128 a; uint128 b; }",
                },
                {
                    "name": "loop_optimization",
                    "description": "Avoid loops with external calls",
                    "example": "Use batch operations instead of loops",
                },
            ]
        }
    else:
        raise HTTPException(status_code=404, detail=f"Resource '{uri}' not found")

    return {
        "contents": [{"type": "text", "text": json.dumps(data, indent=2)}],
        "mimeType": "application/json",
    }


if __name__ == "__main__":
    print("Starting HTTP MCP Audit Server on http://localhost:8001")
    print("Available endpoints:")
    print("  GET  /health - Health check")
    print("  GET  /tools - List available tools")
    print("  GET  /resources - List available resources")
    print("  POST /tools/call - Call a tool")
    print("  GET  /resources/{uri} - Read a resource")

    uvicorn.run(app, host="0.0.0.0", port=8001)

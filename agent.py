"""LangGraph agent with ReAct pattern for smart contract auditing."""

import json
import asyncio
from typing import Dict, List, Any, Optional, TypedDict, Annotated
from datetime import datetime

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from loguru import logger

from mcp_config import MCPConfig, AgentConfig
from mcp_manager import MCPManager


class AgentState(TypedDict):
    """State for the audit agent."""

    messages: Annotated[List[BaseMessage], "The conversation messages"]
    current_task: str
    audit_code: str
    audit_profile: str
    job_id: str
    iteration: int
    max_iterations: int
    tools_used: List[str]
    final_report: Optional[str]
    error: Optional[str]


class MCPToolWrapper(BaseTool):
    """Wrapper to convert MCP tools to LangChain tools."""

    # Pydantic fields
    tool_info: Dict[str, Any]
    mcp_manager: MCPManager

    def __init__(self, tool_info: Dict[str, Any], mcp_manager: MCPManager):
        # Extract tool details
        name = tool_info["name"]
        description = tool_info.get("description", f"MCP tool: {name}")
        server = tool_info.get("server", "unknown")

        super().__init__(
            name=f"{server}_{name}",
            description=f"[{server}] {description}",
            args_schema=None,  # We'll handle this dynamically
            tool_info=tool_info,
            mcp_manager=mcp_manager,
        )

    def _run(self, **kwargs) -> str:
        """Synchronous run method (not used in async context)."""
        raise NotImplementedError("Use async version")

    async def _arun(self, **kwargs) -> str:
        """Async run method."""
        try:
            # Call the MCP tool with server info
            server = self.tool_info.get("server")
            result = await self.mcp_manager.call_tool(
                self.tool_info["name"], kwargs, server=server
            )

            # Format the result
            if result.get("is_error"):
                return f"Error: {result['content']}"

            # Convert content to string
            content = result.get("content", [])
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    else:
                        text_parts.append(str(item))
                return "\n".join(text_parts)
            else:
                return str(content)

        except Exception as e:
            logger.error(f"Error calling MCP tool {self.tool_info['name']}: {e}")
            return f"Error calling tool: {str(e)}"


class AuditAgent:
    """Smart contract audit agent using LangGraph and MCP tools."""

    def __init__(self, config: MCPConfig, mcp_manager: Optional[MCPManager] = None):
        self.config = config
        self.agent_config = config.agent
        self.mcp_manager = mcp_manager

        # Initialize LLM
        self.llm = self._create_llm()

        # Initialize tools
        self.tools: List[BaseTool] = []
        self.tool_node: Optional[ToolNode] = None

        # Initialize graph
        self.graph: Optional[StateGraph] = None
        self.app = None

        # Memory for conversation
        self.memory = MemorySaver()

    def _create_llm(self):
        """Create the LLM instance based on configuration."""
        import os

        model_name = self.agent_config.model
        api_key = self._get_api_key()

        # Если это OpenRouter (часто содержит '/') или есть OPENROUTER_API_KEY, используем OpenAI-совместимый клиент
        if "/" in model_name or os.getenv("OPENROUTER_API_KEY"):
            return ChatOpenAI(
                model=model_name,
                temperature=self.agent_config.temperature,
                max_tokens=self.agent_config.max_tokens,
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
            )
        # Иначе – прямые SDK, как было
        elif "anthropic" in model_name.lower():
            return ChatAnthropic(
                model=model_name,
                temperature=self.agent_config.temperature,
                max_tokens=self.agent_config.max_tokens,
                api_key=api_key,
            )
        elif "openai" in model_name.lower() or "gpt" in model_name.lower():
            return ChatOpenAI(
                model=model_name,
                temperature=self.agent_config.temperature,
                max_tokens=self.agent_config.max_tokens,
                api_key=api_key,
            )
        else:
            # Default to OpenAI-compatible
            return ChatOpenAI(
                model=model_name,
                temperature=self.agent_config.temperature,
                max_tokens=self.agent_config.max_tokens,
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
            )

    def _get_api_key(self) -> str:
        """Get API key for the LLM."""
        import os

        name = self.agent_config.model.lower()

        # Prefer OpenRouter if model looks like an OpenRouter namespace or the env var is set
        if "/" in name or os.getenv("OPENROUTER_API_KEY"):
            api_key = os.getenv("OPENROUTER_API_KEY", "")
            if not api_key:
                logger.warning("OPENROUTER_API_KEY is not set")
                return "placeholder-key"
            logger.info(f"Using OpenRouter API key for model {self.agent_config.model}")
            return api_key

        if "anthropic" in name:
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
            return api_key or "placeholder-key"

        # Native OpenAI (no OpenRouter)
        api_key = os.getenv("OPENAI_API_KEY", "")
        return api_key or "placeholder-key"

    def _setup_tools(self):
        """Setup MCP tools as LangChain tools."""
        if not self.mcp_manager:
            logger.warning("No MCP manager available, using no tools")
            return

        # Get available tools from MCP manager
        mcp_tools = self.mcp_manager.get_available_tools()

        # Convert to LangChain tools
        self.tools = []
        for tool_info in mcp_tools:
            try:
                wrapper = MCPToolWrapper(tool_info, self.mcp_manager)
                self.tools.append(wrapper)
            except Exception as e:
                logger.error(
                    f"Failed to create tool wrapper for {tool_info['name']}: {e}"
                )

        # Create tool node and bind tools to LLM
        if self.tools:
            self.tool_node = ToolNode(self.tools)
            # ВАЖНО: Привязываем инструменты к LLM
            self.llm_with_tools = self.llm.bind_tools(self.tools)
            logger.info(f"Setup {len(self.tools)} MCP tools and bound to LLM")
        else:
            logger.warning("No MCP tools available")
            self.llm_with_tools = self.llm

    def _create_graph(self):
        """Create the LangGraph state graph."""
        if not self.tools:
            logger.warning("No tools available, creating simple graph")
            self._create_simple_graph()
            return

        # Create state graph
        self.graph = StateGraph(AgentState)

        # Add nodes
        self.graph.add_node("agent", self._agent_node)
        self.graph.add_node("tools", self.tool_node)

        # Add edges
        self.graph.add_edge("tools", "agent")

        # Add conditional edge from agent
        self.graph.add_conditional_edges(
            "agent",
            self._should_continue,
            {
                "continue": "tools",
                "end": END,
            },
        )

        # Set entry point
        self.graph.set_entry_point("agent")

        # Compile the graph
        self.app = self.graph.compile(checkpointer=self.memory)

        logger.info("Created LangGraph with ReAct pattern")

    def _create_simple_graph(self):
        """Create a simple graph without tools."""
        self.graph = StateGraph(AgentState)

        # Add only agent node
        self.graph.add_node("agent", self._simple_agent_node)

        # Add edge to end
        self.graph.add_edge("agent", END)

        # Set entry point
        self.graph.set_entry_point("agent")

        # Compile the graph
        self.app = self.graph.compile(checkpointer=self.memory)

        logger.info("Created simple graph without tools")

    async def _agent_node(self, state: AgentState) -> AgentState:
        """Agent node that decides what to do next."""
        messages = state["messages"]
        iteration = state["iteration"]
        max_iterations = state["max_iterations"]

        # Check if we've exceeded max iterations
        if iteration >= max_iterations:
            logger.warning(f"Max iterations ({max_iterations}) reached")
            state["error"] = f"Max iterations ({max_iterations}) reached"
            return state

        # Create system message with context
        system_message = self._create_system_message(state)

        # Prepare messages for LLM
        llm_messages = [system_message] + messages

        try:
            # Get response from LLM with tools
            response = await self.llm_with_tools.ainvoke(llm_messages)

            # Add AI message to state
            messages.append(response)
            state["messages"] = messages
            state["iteration"] = iteration + 1

            # Track tool usage
            if hasattr(response, "tool_calls") and response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    if tool_name not in state["tools_used"]:
                        state["tools_used"].append(tool_name)

            logger.info(f"Agent iteration {iteration + 1} completed")

        except Exception as e:
            logger.error(f"Error in agent node: {e}")
            state["error"] = str(e)

        return state

    async def _simple_agent_node(self, state: AgentState) -> AgentState:
        """Simple agent node without tools."""
        messages = state["messages"]

        # Create system message
        system_message = self._create_system_message(state)

        # Prepare messages for LLM
        llm_messages = [system_message] + messages

        try:
            # Get response from LLM
            response = await self.llm.ainvoke(llm_messages)

            # Add AI message to state
            messages.append(response)
            state["messages"] = messages

            # Generate final report
            state["final_report"] = response.content

            logger.info("Simple agent completed")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error in simple agent node: {error_msg}")

            # Check if it's an authentication error
            if "authentication" in error_msg.lower() or "api_key" in error_msg.lower():
                logger.warning(
                    "Authentication error detected, this should trigger fallback to direct LLM"
                )
                state["error"] = f"Agent authentication failed: {error_msg}"
            else:
                state["error"] = error_msg

        return state

    def _create_system_message(self, state: AgentState) -> BaseMessage:
        """Create system message with context."""
        audit_profile = state["audit_profile"]
        job_id = state["job_id"]

        system_prompt = f"""You are an expert smart contract auditor with access to various tools for comprehensive analysis.

TASK: Perform a security audit of the provided smart contract code.

AUDIT PROFILE: {audit_profile}
JOB ID: {job_id}

AVAILABLE TOOLS: {len(self.tools)} tools available
- Use tools to gather additional information, analyze code, check vulnerabilities, etc.
- You can use multiple tools in sequence or parallel as needed
- Each tool call should be purposeful and contribute to the audit

AUDIT PROCESS:
1. Analyze the contract code for security vulnerabilities
2. Check for compliance with standards (ERC20, ERC721, etc.)
3. Look for common issues: reentrancy, overflow, access control, etc.
4. Use tools to gather additional context if needed
5. Generate a comprehensive audit report

REPORT FORMAT:
- Executive Summary
- Detailed Findings (with severity levels)
- Code locations and explanations
- Specific recommendations
- Risk assessment

Be thorough, accurate, and provide actionable recommendations."""

        return SystemMessage(content=system_prompt)

    def _should_continue(self, state: AgentState) -> str:
        """Decide whether to continue or end."""
        messages = state["messages"]

        if not messages:
            return "end"

        last_message = messages[-1]

        # Check if there's an error
        if state.get("error"):
            return "end"

        # Check if we have tool calls
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "continue"

        # Check if we've reached max iterations
        if state["iteration"] >= state["max_iterations"]:
            return "end"

        # Check if the agent seems to be done
        if (
            "final report" in last_message.content.lower()
            or "audit complete" in last_message.content.lower()
        ):
            return "end"

        # Default to continue for now
        return "continue"

    async def audit_contract(
        self,
        code: str,
        audit_profile: str,
        job_id: str,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Perform smart contract audit using the agent."""
        logger.info(f"Starting audit for job {job_id} with profile {audit_profile}")

        # Initialize state
        initial_state = AgentState(
            messages=[
                HumanMessage(
                    content=f"Please audit this smart contract code:\n\n```solidity\n{code}\n```"
                )
            ],
            current_task="smart_contract_audit",
            audit_code=code,
            audit_profile=audit_profile,
            job_id=job_id,
            iteration=0,
            max_iterations=self.agent_config.max_iterations,
            tools_used=[],
            final_report=None,
            error=None,
        )

        try:
            # Run the agent
            if self.app:
                # Use thread_id for conversation memory
                thread_id = f"audit_{job_id}"

                result = await self.app.ainvoke(
                    initial_state, config={"configurable": {"thread_id": thread_id}}
                )

                # Extract final report
                final_report = result.get("final_report", "")
                if not final_report and result.get("messages"):
                    # Get the last AI message as the report
                    last_ai_message = None
                    for msg in reversed(result["messages"]):
                        if isinstance(msg, AIMessage):
                            last_ai_message = msg
                            break

                    if last_ai_message:
                        final_report = last_ai_message.content

                # Calculate metrics
                metrics = {
                    "calls": len(result.get("tools_used", [])),
                    "prompt_tokens": 0,  # Would need to calculate from messages
                    "completion_tokens": 0,  # Would need to calculate from messages
                    "elapsed_sec": 0,  # Would need to track time
                    "model": self.agent_config.model,
                    "cost_usd": 0.0,  # Would need to calculate
                    "iterations": result.get("iteration", 0),
                    "tools_used": result.get("tools_used", []),
                }

                return {
                    "report": final_report,
                    "metrics": metrics,
                    "error": result.get("error"),
                }
            else:
                raise Exception("Agent not properly initialized")

        except Exception as e:
            logger.error(f"Error during audit: {e}")
            return {
                "report": f"Error during audit: {str(e)}",
                "metrics": {
                    "calls": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "elapsed_sec": 0,
                    "model": self.agent_config.model,
                    "cost_usd": 0.0,
                    "iterations": 0,
                    "tools_used": [],
                },
                "error": str(e),
            }

    async def initialize(self):
        """Initialize the agent."""
        logger.info("Initializing audit agent...")

        # Setup tools
        self._setup_tools()

        # Create graph
        self._create_graph()

        logger.info("Audit agent initialized")

    async def cleanup(self):
        """Cleanup agent resources."""
        logger.info("Cleaning up audit agent...")
        # Any cleanup needed
        pass


# Global agent instance
audit_agent: Optional[AuditAgent] = None


async def get_audit_agent() -> Optional[AuditAgent]:
    """Get the global audit agent instance."""
    return audit_agent


async def initialize_audit_agent(
    config: MCPConfig, mcp_manager: Optional[MCPManager] = None
) -> AuditAgent:
    """Initialize the global audit agent."""
    global audit_agent

    if audit_agent is None:
        audit_agent = AuditAgent(config, mcp_manager)
        await audit_agent.initialize()

    return audit_agent


async def shutdown_audit_agent():
    """Shutdown the global audit agent."""
    global audit_agent

    if audit_agent:
        await audit_agent.cleanup()
        audit_agent = None

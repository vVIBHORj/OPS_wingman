"""
OpsWingman Tool Registry Base Contracts (Phase 2 - Deliverable D-07).
Defines typed tool definitions, risk levels, tool types, and registry interfaces.
"""

from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type
from pydantic import BaseModel, ConfigDict, Field


class RiskLevel(str, Enum):
    """Risk tier for tool execution and policy governance."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ToolType(str, Enum):
    """Classification of tool operation semantics."""
    READ = "READ"
    WRITE = "WRITE"
    SYSTEM = "SYSTEM"


class ToolDefinition(BaseModel):
    """Metadata and execution contract for an authorized tool."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field(..., description="Unique tool identifier name")
    description: str = Field(..., description="Semantic purpose and usage description")
    tool_type: ToolType = Field(..., description="Operation type: READ, WRITE, or SYSTEM")
    risk_level: RiskLevel = Field(..., description="Risk tier: LOW, MEDIUM, or HIGH")
    input_schema: Type[BaseModel] = Field(..., description="Pydantic schema validating input parameters")
    output_schema: Optional[Type[BaseModel]] = Field(default=None, description="Pydantic schema for outputs")
    handler: Callable[..., Any] = Field(..., description="Deterministic execution callable")


class ToolExecutionResult(BaseModel):
    """Standardized output container for any tool invocation."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    tool_name: str
    risk_level: RiskLevel

    # Resilience and Idempotency Telemetry (Phase 4 - Deliverable D-15)
    idempotency_key: Optional[str] = None
    is_cached: bool = False
    attempts: int = 1
    execution_time_seconds: float = 0.0
    retry_delays: List[float] = Field(default_factory=list)
    resilience_metadata: Optional[Dict[str, Any]] = None


class ToolRegistry:
    """
    Central, guarded Tool Registry.
    Validates tool inputs with Pydantic schemas and executes handlers deterministically.
    Composes with ResilientToolExecutor for idempotency and retry protection.
    """

    def __init__(
        self,
        resilience_wrapper: Optional[Any] = None,
    ) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        if resilience_wrapper is not None:
            self.resilience_wrapper = resilience_wrapper
        else:
            from backend.resilience.wrapper import resilient_tool_executor
            self.resilience_wrapper = resilient_tool_executor

    def register(self, tool: ToolDefinition) -> None:
        """Registers a tool definition into the registry."""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered.")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Retrieves a tool definition by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[ToolDefinition]:
        """Returns all registered tool definitions."""
        return list(self._tools.values())

    def execute(self, name: str, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolExecutionResult:
        """
        Validates parameters against the tool's input schema and executes the handler.
        Routes execution through ResilientToolExecutor for idempotency and retry protection.
        """
        tool = self.get(name)
        if not tool:
            return ToolExecutionResult(
                success=False,
                error=f"Tool '{name}' not found in registry.",
                tool_name=name,
                risk_level=RiskLevel.HIGH,
            )

        # 1. Enforce HIGH-risk tool authorization at the ToolRegistry execution boundary
        if tool.risk_level == RiskLevel.HIGH:
            is_approved = bool(context and (context.get("approved") is True or context.get("approval_granted") is True))
            if not is_approved:
                return ToolExecutionResult(
                    success=False,
                    error=f"Execution blocked: HIGH-risk tool '{name}' requires explicit approval authorization.",
                    tool_name=name,
                    risk_level=tool.risk_level,
                )

        try:
            # 2. Validate inputs with Pydantic input schema
            validated_inputs = tool.input_schema.model_validate(params)
        except Exception as exc:
            return ToolExecutionResult(
                success=False,
                error=f"Input validation error for tool '{name}': {exc}",
                tool_name=name,
                risk_level=tool.risk_level,
            )

        # 3. Route through resilience wrapper
        resilience_exec = (context.get("resilience_wrapper") if context else None) or self.resilience_wrapper
        return resilience_exec.execute(tool, validated_inputs, context=context)


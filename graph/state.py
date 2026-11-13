"""
LangGraph State Definition for Secure RAG Pipeline.
Defines typing schema for input query, security telemetry, retrieved documents, and generation outputs.
"""

from typing import TypedDict, List, Dict, Any, Optional


class RAGSecurityState(TypedDict):
    """LangGraph execution state schema."""
    # Input
    user_query: str
    single_source_only: Optional[bool]
    strict_mode: Optional[bool]
    chat_history: Optional[List[Dict[str, str]]]
    
    # Security Telemetry - Input Stage
    input_security: Dict[str, Any]
    is_input_flagged: bool
    
    # RAG Retrieval Stage
    retrieved_documents: List[Dict[str, Any]]
    
    # Security Telemetry - Context Stage (Indirect Injection)
    context_security: Dict[str, Any]
    is_context_flagged: bool
    filtered_documents: List[Dict[str, Any]]
    
    # LLM Generation Stage
    system_prompt: Optional[str]
    user_prompt: Optional[str]
    canary_token: Optional[str]
    final_response: str
    
    # Audit & Status
    status: str  # "SUCCESS", "BLOCKED_DIRECT_INJECTION", "BLOCKED_INDIRECT_INJECTION", "ERROR"
    execution_steps: List[str]
    error_message: Optional[str]

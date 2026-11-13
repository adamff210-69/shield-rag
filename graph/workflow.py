"""
LangGraph StateMachine Construction & Execution Workflow.

Defines the graph topology:
Input Security Node -> Conditional Edge -> (Retriever -> Context Security Node -> Conditional Edge) -> Groq Generation Node / Security Blocked Node.
"""

from typing import Dict, Any, Optional, List
from langgraph.graph import StateGraph, END
from graph.state import RAGSecurityState
from graph.nodes import RAGGraphNodes
from security.guardrail import UnifiedSecurityGuard
from rag.vector_store import RAGVectorStore


class SecureRAGWorkflow:
    """Orchestrator for compiling and executing the LangGraph RAG security workflow."""

    def __init__(
        self,
        security_guard: Optional[UnifiedSecurityGuard] = None,
        vector_store: Optional[RAGVectorStore] = None,
        groq_api_key: Optional[str] = None,
        model_name: str = "llama-3.3-70b-versatile"
    ):
        self.security_guard = security_guard or UnifiedSecurityGuard()
        self.vector_store = vector_store or RAGVectorStore()
        self.nodes = RAGGraphNodes(
            security_guard=self.security_guard,
            vector_store=self.vector_store,
            groq_api_key=groq_api_key,
            model_name=model_name
        )
        self.app = self._build_graph()

    def _build_graph(self):
        """Construct StateGraph with nodes and conditional routing edges."""
        workflow = StateGraph(RAGSecurityState)

        # 1. Add Nodes
        workflow.add_node("input_security", self.nodes.input_security_node)
        workflow.add_node("retrieval", self.nodes.retrieval_node)
        workflow.add_node("context_security", self.nodes.context_security_node)
        workflow.add_node("groq_generation", self.nodes.groq_generation_node)
        workflow.add_node("security_blocked", self.nodes.security_blocked_node)

        # 2. Set Entry Point
        workflow.set_entry_point("input_security")

        # 3. Add Conditional Edge from input_security
        def check_input_security(state: RAGSecurityState) -> str:
            if state.get("is_input_flagged", False):
                return "security_blocked"
            return "retrieval"

        workflow.add_conditional_edges(
            "input_security",
            check_input_security,
            {
                "security_blocked": "security_blocked",
                "retrieval": "retrieval"
            }
        )

        # 4. Standard Edge: retrieval -> context_security
        workflow.add_edge("retrieval", "context_security")

        # 5. Add Conditional Edge from context_security
        def check_context_security(state: RAGSecurityState) -> str:
            # If the direct user input was flagged as malicious, block
            if state.get("is_input_flagged", False):
                return "security_blocked"
            # If context had indirect injections, bad documents were removed.
            # Allow safe generation with remaining clean documents (or 0 context documents if all were bad).
            return "groq_generation"

        workflow.add_conditional_edges(
            "context_security",
            check_context_security,
            {
                "security_blocked": "security_blocked",
                "groq_generation": "groq_generation"
            }
        )

        # 6. Terminal Edges
        workflow.add_edge("groq_generation", END)
        workflow.add_edge("security_blocked", END)

        return workflow.compile()

    def execute(
        self, 
        query: str, 
        single_source_only: bool = False, 
        strict_mode: bool = False,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Run graph execution for a user query."""
        initial_state: RAGSecurityState = {
            "user_query": query,
            "single_source_only": single_source_only,
            "strict_mode": strict_mode,
            "chat_history": chat_history or [],
            "input_security": {},
            "is_input_flagged": False,
            "retrieved_documents": [],
            "context_security": {},
            "is_context_flagged": False,
            "filtered_documents": [],
            "system_prompt": None,
            "user_prompt": None,
            "canary_token": None,
            "final_response": "",
            "status": "START",
            "execution_steps": [],
            "error_message": None
        }

        result = self.app.invoke(initial_state)
        return result

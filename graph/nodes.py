"""
LangGraph Nodes for Secure RAG Graph Execution.

Includes:
1. input_security_node (3-Layer Prompt Injection Defense)
2. retrieval_node (Vector Store Similarity Search)
3. context_security_node (Indirect Injection Scan)
4. groq_generation_node (Groq API LLM Call with System Isolation & Canary Check)
5. security_blocked_node (Security Violation Telemetry & Safe Block Response)
"""

import os
from typing import Dict, Any, List, Optional
from graph.state import RAGSecurityState
from security.guardrail import UnifiedSecurityGuard
from rag.vector_store import RAGVectorStore
from rag.templates import SecurePromptBuilder
from rag.groq_client import fetch_groq_models

try:
    from langchain_groq import ChatGroq
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False


def is_conversational_query(query: str) -> bool:
    """Check if query is a generic greeting or casual small talk."""
    if not query:
        return True
    q = query.strip().lower().rstrip(".!?")
    greetings = {
        "hi", "hey", "hello", "greetings", "good morning", "good afternoon",
        "good evening", "how are you", "who are you", "what is your name",
        "thanks", "thank you", "test", "ping", "hi there", "hey there", "hello there"
    }
    return q in greetings


class RAGGraphNodes:
    """Container for LangGraph state machine node operations."""

    def __init__(
        self,
        security_guard: UnifiedSecurityGuard,
        vector_store: RAGVectorStore,
        groq_api_key: Optional[str] = None,
        model_name: str = "llama-3.3-70b-versatile"
    ):
        self.security_guard = security_guard
        self.vector_store = vector_store
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY")
        self.model_name = model_name

    def input_security_node(self, state: RAGSecurityState) -> Dict[str, Any]:
        """Node 1: Evaluates user query across 3 security layers before retrieval/LLM."""
        query = state.get("user_query", "")
        steps = list(state.get("execution_steps", []))
        steps.append("InputSecurityGuard: Executing 3-Layer Pre-LLM Security Check")

        scan_res = self.security_guard.scan_prompt(query)
        is_flagged = scan_res.get("is_flagged", False)

        return {
            "input_security": scan_res,
            "is_input_flagged": is_flagged,
            "execution_steps": steps,
            "status": "INPUT_FLAGGED" if is_flagged else "INPUT_SAFE"
        }

    def retrieval_node(self, state: RAGSecurityState) -> Dict[str, Any]:
        """Node 2: Vector similarity search for user query."""
        query = state.get("user_query", "")
        single_source_only = bool(state.get("single_source_only", False))
        steps = list(state.get("execution_steps", []))

        if is_conversational_query(query):
            steps.append("VectorRetriever: Skipped vector store lookup for conversational query")
            return {
                "retrieved_documents": [],
                "execution_steps": steps
            }

        mode_label = "Single Source Mode" if single_source_only else "Multi-Source Mode"
        steps.append(f"VectorRetriever: Querying Vector Store Knowledge Base ({mode_label})")
        
        retrieved = self.vector_store.similarity_search(
            query, 
            top_k=3, 
            min_score=0.20,
            single_source_only=single_source_only
        )

        return {
            "retrieved_documents": retrieved,
            "execution_steps": steps
        }

    def context_security_node(self, state: RAGSecurityState) -> Dict[str, Any]:
        """Node 3: Scans retrieved documents for Indirect Prompt Injections."""
        docs = state.get("retrieved_documents", [])
        steps = list(state.get("execution_steps", []))
        steps.append("ContextSecurityGuard: Scanning retrieved documents for Indirect Prompt Injection")

        scan_res = self.security_guard.scan_context_documents(docs)
        has_indirect = scan_res.get("has_indirect_injections", False)

        return {
            "context_security": scan_res,
            "is_context_flagged": has_indirect,
            "filtered_documents": scan_res.get("clean_documents", []),
            "execution_steps": steps,
            "status": "CONTEXT_FLAGGED" if has_indirect and not scan_res.get("clean_documents") else "CONTEXT_SAFE"
        }

    def groq_generation_node(self, state: RAGSecurityState) -> Dict[str, Any]:
        """Node 4: Secure LLM Generation using Groq API."""
        query = state.get("user_query", "")
        docs = state.get("filtered_documents", [])
        chat_history = state.get("chat_history", []) or []
        steps = list(state.get("execution_steps", []))
        
        hist_count = len(chat_history)
        if hist_count > 0:
            steps.append(f"GroqGeneration: Loaded {hist_count} previous chat history messages into context window")

        steps.append(f"GroqGeneration: Invoking Groq LLM ({self.model_name}) with System Prompt Isolation")

        strict_mode = bool(state.get("strict_mode", False))
        # Build secure prompt
        system_prompt, user_prompt, canary_token = SecurePromptBuilder.build_rag_prompt(
            query=query, 
            context_docs=docs, 
            enable_canary=True,
            strict_mode=strict_mode,
            chat_history=chat_history
        )

        api_key = self.groq_api_key or os.getenv("GROQ_API_KEY")

        if api_key and HAS_GROQ:
            try:
                llm = ChatGroq(
                    groq_api_key=api_key,
                    model_name=self.model_name,
                    temperature=0.2,
                    max_tokens=1024
                )
                messages = [SystemMessage(content=system_prompt)]

                # Interleave chat history turns if present (limit to last 10 messages for token safety)
                for h_msg in chat_history[-10:]:
                    role = h_msg.get("role", "")
                    content = h_msg.get("content", "")
                    if role == "user" and content:
                        messages.append(HumanMessage(content=content))
                    elif role == "assistant" and content:
                        messages.append(AIMessage(content=content))

                messages.append(HumanMessage(content=user_prompt))
                response_obj = llm.invoke(messages)
                response_text = response_obj.content

                # Canary leak check
                if canary_token and canary_token in response_text:
                    steps.append("SECURITY WARNING: Canary Token Leak Detected in LLM output!")
                    response_text = "[SECURITY ALERT: LLM output contained internal system tokens and was redacted.]"

            except Exception as e:
                err_str = str(e)
                # Auto-fallback handling if specified model does not exist (404 model_not_found)
                if "404" in err_str or "model_not_found" in err_str or "does not exist" in err_str:
                    steps.append(f"GroqGeneration Warning: Model '{self.model_name}' not available on your Groq key. Discovering active models...")
                    model_info = fetch_groq_models(api_key)
                    avail_models = model_info.get("models", [])
                    
                    # Select alternative working model
                    fallback_target = None
                    for candidate in ["llama-3.1-8b-instant", "llama3-8b-8192", "mixtral-8x7b-32768", "llama-3.3-70b-versatile"]:
                        if candidate in avail_models and candidate != self.model_name:
                            fallback_target = candidate
                            break

                    if not fallback_target and avail_models:
                        fallback_target = avail_models[0]

                    if fallback_target:
                        steps.append(f"GroqGeneration Auto-Switch: Switching model from '{self.model_name}' -> '{fallback_target}'")
                        self.model_name = fallback_target
                        try:
                            retry_llm = ChatGroq(
                                groq_api_key=api_key,
                                model_name=fallback_target,
                                temperature=0.2,
                                max_tokens=1024
                            )
                            retry_res = retry_llm.invoke(messages)
                            response_text = retry_res.content
                        except Exception as retry_err:
                            response_text = (
                                f"[Groq API Error]: Model '{self.model_name}' was unavailable, and fallback model '{fallback_target}' failed: {str(retry_err)}.\n"
                                f"Available models for your API Key: {', '.join(avail_models)}"
                            )
                    else:
                        response_text = f"[Groq API Call Error]: {err_str}. Please select an available model from the settings dropdown."
                else:
                    response_text = f"[Groq API Call Error]: {err_str}. Please check your GROQ_API_KEY environment variable."
        else:
            # Demonstration / Dry-Run Response
            if is_conversational_query(query):
                response_text = (
                    f"Hello! I am **ShieldRAG**, your secure AI workspace assistant. "
                    f"How can I help you today?\n\n"
                    f"*(Note: Pass GROQ_API_KEY in environment or UI settings to enable live Groq inference).* "
                )
            elif docs:
                context_str = "\n".join([f"- {d.get('page_content', '')}" for d in docs])
                response_text = (
                    f"[SIMULATED GROQ RESPONSE - Model: {self.model_name}]\n\n"
                    f"Based on the retrieved context:\n{context_str}\n\n"
                    f"*(Note: Pass GROQ_API_KEY in environment or UI settings to enable live Groq inference).* "
                )
            else:
                response_text = (
                    f"[SIMULATED GROQ RESPONSE - Model: {self.model_name}]\n\n"
                    f"I processed your query: '{query}'. (No untrusted or additional vector store context was required).\n\n"
                    f"*(Note: Pass GROQ_API_KEY in environment or UI settings to enable live Groq inference).* "
                )

        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "canary_token": canary_token,
            "final_response": response_text,
            "execution_steps": steps,
            "status": "SUCCESS"
        }

    def security_blocked_node(self, state: RAGSecurityState) -> Dict[str, Any]:
        """Node 5: Security Fallback when prompt injection is detected."""
        steps = list(state.get("execution_steps", []))
        steps.append("SecurityBlockedNode: Intercepted malicious request. LLM call cancelled (0 token cost).")

        input_sec = state.get("input_security", {})
        context_sec = state.get("context_security", {})

        is_input = state.get("is_input_flagged", False)
        is_context = state.get("is_context_flagged", False)

        threats = []
        if is_input:
            threats.extend(input_sec.get("threats_detected", []))
        if is_context:
            for fdoc in context_sec.get("flagged_documents", []):
                threats.extend(fdoc.get("threats", []))

        threat_summary = "\n".join([f"• [{t.get('layer')}] Threat: {t.get('threat_type')} (Score: {t.get('score')})" for t in threats])

        blocked_message = (
            "⚠️ **SECURITY VIOLATION DETECTED - REQUEST BLOCKED** ⚠️\n\n"
            "Our Pre-LLM Security Guardrail Layer intercepted a potential Prompt Injection attack vector.\n\n"
            f"**Security Verdict:**\n"
            f"- Direct Injection Flagged: `{is_input}`\n"
            f"- Indirect Context Injection Flagged: `{is_context}`\n"
            f"- Overall Risk Score: `{input_sec.get('risk_score', 0.0):.4f}` ({input_sec.get('risk_level', 'HIGH')})\n\n"
            f"**Detected Threat Breakdown:**\n{threat_summary if threat_summary else '• High risk score exceeding safety threshold'}\n\n"
            "*The request was terminated before calling the Groq LLM API to ensure system safety and prevent API token exploitation.*"
        )

        return {
            "final_response": blocked_message,
            "execution_steps": steps,
            "status": "BLOCKED_DIRECT_INJECTION" if is_input else "BLOCKED_INDIRECT_INJECTION"
        }

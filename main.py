"""
ShieldRAG Main Entry Point Launcher.

Modes:
- Web Application Server: python main.py
- Interactive CLI Console: python main.py --cli
- Automated Security Suite: python main.py --test
"""

import sys
import os
import argparse
import uvicorn

# Ensure UTF-8 output encoding for Windows terminals with emojis
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from security.guardrail import UnifiedSecurityGuard
from rag.vector_store import RAGVectorStore
from graph.workflow import SecureRAGWorkflow


def run_cli_mode():
    """Run interactive Command-Line Interface mode."""
    print("=" * 70)
    print("      🛡️  ShieldRAG CLI Console (LangGraph + Groq + 3-Layer Security) 🛡️")
    print("=" * 70)
    print("Type your RAG query or prompt injection payload below (or 'exit' to quit).\n")

    guard = UnifiedSecurityGuard(sensitivity="MEDIUM")
    vector_store = RAGVectorStore()
    workflow = SecureRAGWorkflow(security_guard=guard, vector_store=vector_store)

    while True:
        try:
            user_input = input("\n[ShieldRAG User Query] > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("Exiting ShieldRAG CLI. Goodbye!")
                break

            print("\n⚙️  Running LangGraph State Machine & Security Guards...")
            result = workflow.execute(user_input)

            input_sec = result.get("input_security", {})
            status = result.get("status")

            print("-" * 60)
            print(f"📊 Security Verdict: {'🔴 BLOCKED' if 'BLOCKED' in status else '🟢 PASSED'}")
            print(f"📈 Ensemble Risk Score: {input_sec.get('risk_score', 0.0):.4f} ({input_sec.get('risk_level', 'LOW')})")
            
            bd = input_sec.get("breakdown", {})
            print(f"   ├─ Layer 1 (Rules):    {bd.get('layer1_rules_score', 0.0):.4f}")
            print(f"   ├─ Layer 2 (Model 1):  {bd.get('layer2_model1_score', 0.0):.4f}")
            print(f"   └─ Layer 3 (Model 2):  {bd.get('layer3_model2_score', 0.0):.4f}")
            print("-" * 60)

            print(f"\n🤖 Answer / Response Output:\n{result.get('final_response')}")

        except KeyboardInterrupt:
            print("\nExiting ShieldRAG CLI. Goodbye!")
            break


def main():
    parser = argparse.ArgumentParser(description="ShieldRAG Application Launcher")
    parser.add_argument("--cli", action="store_true", help="Launch in interactive CLI mode")
    parser.add_argument("--test", action="store_true", help="Run pytest security test suite")
    parser.add_argument("--port", type=int, default=8000, help="Port for web server (default: 8000)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host for web server (default: 127.0.0.1)")

    args = parser.parse_args()

    if args.test:
        import pytest
        sys.exit(pytest.main(["test_security.py", "-v"]))
    elif args.cli:
        run_cli_mode()
    else:
        print(f"🚀 Starting ShieldRAG Web Application on http://{args.host}:{args.port}")
        uvicorn.run("app:app", host=args.host, port=args.port, reload=True)


if __name__ == "__main__":
    main()

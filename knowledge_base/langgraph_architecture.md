# LangGraph Architecture and RAG State Management

## Overview
LangGraph is a framework for building stateful, multi-actor applications with LLMs, extending LangChain with cyclic workflows and fine-grained state management. In a Secure Retrieval-Augmented Generation (RAG) architecture, LangGraph manages the transitions between query validation, knowledge retrieval, context security inspection, and model response generation.

## State Transitions and Typed Schema
LangGraph uses a typed state schema (`RAGSecurityState`) to coordinate state transitions across nodes:
1. **Input Security Guard**: Evaluates the user query against heuristic rules, neural classifiers, and vector divergence models.
2. **Conditional Router**: Routes safe inputs to the Vector Retriever and flagged attacks to the Security Violation Fallback node.
3. **Vector Retriever**: Queries in-memory vector embeddings and hybrid lexical indices for matching knowledge documents.
4. **Context Security Guard**: Inspects retrieved context passages for Indirect Prompt Injections (such as delimiter hijacking, BIPIA payloads, or instruction poisoning).
5. **Groq Generation Node**: Formats safe context with XML tag delimiters and system canary tokens, then invokes the Groq LPU inference API.
6. **Security Violation Fallback**: Halts execution with zero token expenditure when direct prompt injection is intercepted.

## Cyclic and Dynamic Routing
Unlike linear chains, LangGraph allows conditional branches, cyclical retries, human-in-the-loop validation, and fallback mechanisms when API timeouts or security triggers occur.

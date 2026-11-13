# Groq LPU Hardware Architecture & Inference Engine

## Groq Language Processing Units (LPUs)
Groq LPUs are specialized Tensor Streaming Processors (TSPs) engineered specifically for low-latency, deterministic AI inference. Unlike traditional GPUs that rely on speculative execution and dynamic scheduling, Groq LPUs feature a deterministic execution model where instruction scheduling is computed at compile-time.

## Throughput and Latency Advantages
- **Deterministic Compute**: Eliminates memory bandwidth bottlenecks and dynamic contention.
- **Ultra-High Inference Speed**: Achieves over 300 to 500 tokens per second on large open-weight models such as Llama 3.3 70B and Llama 3.1 8B.
- **Zero-Token Pre-LLM Defense**: In ShieldRAG, requests flagged by the 3-Layer Security Guardrail are blocked before calling the Groq API endpoint, ensuring that malicious traffic incurs zero Groq API cost and zero LPU compute cycles.

## Documentation Guidelines
When deploying RAG workloads on Groq, ensure that user queries and untrusted context strings are isolated with structural delimiters (such as `<untrusted_retrieved_context>`) to avoid instruction confusion on the underlying transformer.

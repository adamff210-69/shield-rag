"""
FastAPI Server for Secure RAG & Prompt Injection Guardrail Application.

Provides REST APIs for:
- POST /api/chat (LangGraph execution with 3-layer prompt injection scan + Groq API)
- POST /api/ingest (Ingest custom documents into vector store)
- GET /api/documents (List current vector store documents)
- POST /api/security-config (Update sensitivity & Groq API key)
- GET /api/health (Health & Status telemetry)
"""

import os
import uvicorn
from fastapi import FastAPI, HTTPException, Body, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from security.guardrail import UnifiedSecurityGuard
from rag.vector_store import RAGVectorStore
from rag.groq_client import fetch_groq_models
from rag.parser import parse_document_text
from graph.workflow import SecureRAGWorkflow

# Initialize FastAPI App
app = FastAPI(
    title="Secure RAG Application",
    description="RAG Application built with LangGraph, Groq API, and 3-Layer Pre-LLM Security Defense",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global State Objects
GLOBAL_SECURITY_GUARD = UnifiedSecurityGuard(sensitivity="MEDIUM")
GLOBAL_VECTOR_STORE = RAGVectorStore()
GLOBAL_WORKFLOW = SecureRAGWorkflow(
    security_guard=GLOBAL_SECURITY_GUARD,
    vector_store=GLOBAL_VECTOR_STORE
)


# Request & Response Schemas
class QueryRequest(BaseModel):
    query: str = Field(..., json_schema_extra={"example": "What is LangGraph?"})
    sensitivity: Optional[str] = Field("MEDIUM", json_schema_extra={"example": "MEDIUM"})
    groq_api_key: Optional[str] = Field(None, json_schema_extra={"example": "gsk_..."})
    model_name: Optional[str] = Field("llama-3.3-70b-versatile", json_schema_extra={"example": "llama-3.3-70b-versatile"})
    single_source_only: Optional[bool] = Field(False, json_schema_extra={"example": True})
    strict_mode: Optional[bool] = Field(False, json_schema_extra={"example": False})
    chat_history: Optional[List[Dict[str, str]]] = Field(None)


class IngestRequest(BaseModel):
    title: str = Field(..., json_schema_extra={"example": "Company Policy"})
    content: str = Field(..., json_schema_extra={"example": "Employees must adhere to security guidelines..."})
    topic: Optional[str] = Field("General", json_schema_extra={"example": "Policy"})


class ConfigRequest(BaseModel):
    sensitivity: str = Field("MEDIUM", json_schema_extra={"example": "HIGH"})
    groq_api_key: Optional[str] = Field(None, json_schema_extra={"example": "gsk_..."})
    model_name: Optional[str] = Field(None, json_schema_extra={"example": "llama-3.1-8b-instant"})
    strict_mode: Optional[bool] = Field(None, json_schema_extra={"example": False})


# API Endpoints
@app.api_route("/api/health", methods=["GET", "HEAD"])
def get_health():
    """Returns application health and vector store stats."""
    return {
        "status": "healthy",
        "vector_store_chunks": len(GLOBAL_VECTOR_STORE.chunks),
        "security_sensitivity": GLOBAL_SECURITY_GUARD.sensitivity_name,
        "security_threshold": GLOBAL_SECURITY_GUARD.threshold,
        "active_model": GLOBAL_WORKFLOW.nodes.model_name,
        "groq_api_key_configured": bool(GLOBAL_WORKFLOW.nodes.groq_api_key or os.getenv("GROQ_API_KEY"))
    }


@app.api_route("/api/models", methods=["GET", "POST"])
def get_groq_models(req: Optional[ConfigRequest] = None, api_key: Optional[str] = None):
    """Fetch available Groq models dynamically for the user's API key."""
    key = None
    if req and req.groq_api_key:
        key = req.groq_api_key
    elif api_key:
        key = api_key
    else:
        key = GLOBAL_WORKFLOW.nodes.groq_api_key or os.getenv("GROQ_API_KEY")

    result = fetch_groq_models(key)
    result["active_model"] = GLOBAL_WORKFLOW.nodes.model_name
    return result


@app.post("/api/chat")
def process_chat(req: QueryRequest):
    """Execute LangGraph Secure RAG workflow for a user query."""
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Update dynamic settings if provided
    if req.sensitivity and req.sensitivity.upper() != GLOBAL_SECURITY_GUARD.sensitivity_name:
        GLOBAL_SECURITY_GUARD.update_sensitivity(req.sensitivity)

    if req.groq_api_key:
        GLOBAL_WORKFLOW.nodes.groq_api_key = req.groq_api_key

    if req.model_name:
        GLOBAL_WORKFLOW.nodes.model_name = req.model_name

    try:
        # Execute LangGraph state machine
        graph_result = GLOBAL_WORKFLOW.execute(
            req.query, 
            single_source_only=bool(req.single_source_only),
            strict_mode=bool(req.strict_mode),
            chat_history=req.chat_history
        )

        return JSONResponse(content={
            "query": req.query,
            "status": graph_result.get("status"),
            "final_response": graph_result.get("final_response"),
            "input_security": graph_result.get("input_security"),
            "context_security": graph_result.get("context_security"),
            "retrieved_documents": graph_result.get("retrieved_documents"),
            "filtered_documents": graph_result.get("filtered_documents"),
            "execution_steps": graph_result.get("execution_steps"),
            "system_prompt_sample": graph_result.get("system_prompt")
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph Execution Error: {str(e)}")


@app.post("/api/upload-file")
async def upload_file(file: UploadFile = File(...)):
    """Upload raw file (.docx, .pdf, .txt, .md, etc.) and extract clean plain text."""
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file selected.")

    # File Extension & Format Validation
    BLOCKED_EXTENSIONS = {".exe", ".sh", ".bat", ".cmd", ".js", ".py", ".html", ".php", ".vbs", ".dll", ".ps1"}
    ext = os.path.splitext(file.filename.lower())[1]
    if ext in BLOCKED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Security Violation: Executable file type '{ext}' is blocked for security reasons."
        )

    try:
        content_bytes = await file.read()
        
        # File Size Limiter (5 MB max)
        MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
        if len(content_bytes) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail="Security Violation: Document exceeds maximum allowed size limit of 5MB."
            )

        extracted_text = parse_document_text(content_bytes, file.filename)
        if not extracted_text or not extracted_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from document. File may be empty or unreadable.")

        return {
            "status": "success",
            "filename": file.filename,
            "extracted_text": extracted_text,
            "char_count": len(extracted_text)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File parsing error: {str(e)}")


@app.post("/api/ingest")
def ingest_document(req: IngestRequest):
    """Ingest custom document into Vector Store with security checks, size validation, and fast chunking."""
    import time
    start_t = time.time()

    if not req.content or not req.content.strip():
        raise HTTPException(status_code=400, detail="Document content cannot be empty.")

    # 1. File Extension & Format Validation
    BLOCKED_EXTENSIONS = {".exe", ".sh", ".bat", ".cmd", ".js", ".py", ".html", ".php", ".vbs", ".dll", ".ps1"}
    
    title_lower = req.title.lower()
    ext = os.path.splitext(title_lower)[1]
    
    if ext in BLOCKED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Security Violation: Executable file type '{ext}' is blocked for security reasons."
        )

    # 2. Parse & Sanitize document content
    clean_content = parse_document_text(req.content, req.title)
    if not clean_content or not clean_content.strip():
        raise HTTPException(status_code=400, detail="Document content is empty or unparseable after sanitization.")

    # 3. File Size Limiter (5 MB max)
    MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
    if len(clean_content.encode('utf-8')) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400, 
            detail="Security Violation: Document exceeds maximum allowed size limit of 5MB."
        )

    try:
        # Scan sample of document across all 3 security layers for indirect prompt injections before storing
        sample_doc = [{"page_content": clean_content[:10000], "metadata": {"source": req.title}}]
        context_scan = GLOBAL_SECURITY_GUARD.scan_context_documents(sample_doc)
        has_threats = context_scan.get("has_indirect_injections", False)
        
        flagged_threats = []
        if has_threats and context_scan.get("flagged_documents"):
            flagged_threats = context_scan["flagged_documents"][0].get("threats", [])

        chunk_ids = GLOBAL_VECTOR_STORE.add_texts(
            texts=[clean_content],
            metadatas=[{
                "source": req.title, 
                "topic": req.topic or "Custom",
                "doc_type": "INJECTED" if has_threats else "BENIGN"
            }]
        )

        proc_time_ms = round((time.time() - start_t) * 1000, 2)

        return {
            "status": "success",
            "message": f"Successfully ingested document '{req.title}' ({len(chunk_ids)} chunks created in {proc_time_ms}ms)",
            "chunk_ids": chunk_ids,
            "chunk_count": len(chunk_ids),
            "processing_time_ms": proc_time_ms,
            "indirect_scan_warning": has_threats,
            "threats_found": flagged_threats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@app.get("/api/documents")
def get_documents():
    """List distinct document files with chunk telemetry and full content."""
    doc_map = {}
    for c in GLOBAL_VECTOR_STORE.chunks:
        src = c.metadata.get("source", "untitled_document")
        if src not in doc_map:
            doc_map[src] = {
                "source": src,
                "topic": c.metadata.get("topic", "General"),
                "doc_type": c.metadata.get("doc_type", "BENIGN"),
                "citation": c.metadata.get("citation", "Local Knowledge Base"),
                "filepath": c.metadata.get("filepath", None),
                "chunks": []
            }
        doc_map[src]["chunks"].append(c)

    document_list = []
    for src, info in doc_map.items():
        sorted_chunks = sorted(
            info["chunks"],
            key=lambda x: x.metadata.get("chunk_index", 0)
        )
        is_inj = any(c.metadata.get("doc_type") == "INJECTED" for c in sorted_chunks)
        full_text = "\n\n".join(c.page_content for c in sorted_chunks)
        document_list.append({
            "source": src,
            "topic": info["topic"],
            "citation": info["citation"],
            "doc_type": "INJECTED" if is_inj else "BENIGN",
            "chunk_count": len(sorted_chunks),
            "total_chars": sum(len(c.page_content) for c in sorted_chunks),
            "full_content": full_text,
            "preview": (sorted_chunks[0].page_content[:240] + "...") if sorted_chunks else "",
            "chunks": [c.to_dict() for c in sorted_chunks]
        })

    return {
        "total_documents": len(document_list),
        "total_chunks": len(GLOBAL_VECTOR_STORE.chunks),
        "documents": document_list,
        "raw_chunks": [c.to_dict() for c in GLOBAL_VECTOR_STORE.chunks]
    }


@app.delete("/api/documents")
def clear_all_documents():
    """Clear all documents from the vector store."""
    count = len(GLOBAL_VECTOR_STORE.chunks)
    GLOBAL_VECTOR_STORE.clear()
    return {
        "status": "success",
        "message": f"Successfully cleared all {count} document chunks from the knowledge base."
    }


@app.delete("/api/documents/{source_name}")
def delete_document(source_name: str):
    """Delete a specific document and its chunks by source name."""
    deleted_count = GLOBAL_VECTOR_STORE.delete_document_by_source(source_name)
    return {
        "status": "success",
        "message": f"Deleted {deleted_count} chunks for document '{source_name}'."
    }


@app.post("/api/security-config")
def update_config(req: ConfigRequest):
    """Update global security & model configuration."""
    GLOBAL_SECURITY_GUARD.update_sensitivity(req.sensitivity)
    if req.groq_api_key:
        GLOBAL_WORKFLOW.nodes.groq_api_key = req.groq_api_key

    if req.model_name:
        GLOBAL_WORKFLOW.nodes.model_name = req.model_name

    return {
        "status": "updated",
        "sensitivity": GLOBAL_SECURITY_GUARD.sensitivity_name,
        "threshold": GLOBAL_SECURITY_GUARD.threshold,
        "model_name": GLOBAL_WORKFLOW.nodes.model_name,
        "groq_api_key_set": bool(GLOBAL_WORKFLOW.nodes.groq_api_key)
    }


# Mount Static directory
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.api_route("/", methods=["GET", "HEAD"])
def read_root():
    """Serve static web dashboard UI."""
    return FileResponse("static/index.html")


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

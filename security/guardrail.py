"""
Unified Pre-LLM Security Guardrail Engine.

Integrates:
1. Layer 1: Heuristic & Regex Rule Engine
2. Layer 2: Lightweight ML Model 1 (Transformer Classifier)
3. Layer 3: Lightweight ML Model 2 (Semantic Embedding Divergence Detector)

Provides ensemble threat decisioning for both Direct Prompt Injections and Indirect Prompt Injections.
"""

import time
from typing import Dict, List, Any, Optional
from security.rules import RuleBasedDetector
from security.model_classifier import LightweightTransformerDetector, SemanticEmbeddingDetector


class UnifiedSecurityGuard:
    """
    Multi-Tier Pre-LLM Security Guardrail Manager.
    Evaluates incoming prompts and retrieved contextual documents.
    """

    def __init__(
        self,
        sensitivity: str = "MEDIUM",
        weight_rules: float = 0.40,
        weight_model1: float = 0.35,
        weight_model2: float = 0.25
    ):
        # Thresholds based on sensitivity setting
        self.sensitivity_map = {
            "LOW": 0.75,
            "MEDIUM": 0.50,
            "HIGH": 0.30,
            "CRITICAL": 0.15
        }
        self.sensitivity_name = sensitivity.upper()
        self.threshold = self.sensitivity_map.get(self.sensitivity_name, 0.50)

        self.weight_rules = weight_rules
        self.weight_model1 = weight_model1
        self.weight_model2 = weight_model2

        # Instantiate 3 defense layers
        self.rules_engine = RuleBasedDetector(sensitivity_threshold=self.threshold)
        self.model1_engine = LightweightTransformerDetector(sensitivity_threshold=self.threshold)
        self.model2_engine = SemanticEmbeddingDetector(sensitivity_threshold=self.threshold)

    def update_sensitivity(self, sensitivity: str):
        """Update sensitivity threshold dynamically without re-instantiating ML models."""
        self.sensitivity_name = sensitivity.upper()
        self.threshold = self.sensitivity_map.get(self.sensitivity_name, 0.50)
        self.rules_engine.sensitivity_threshold = self.threshold
        self.model1_engine.sensitivity_threshold = self.threshold
        self.model2_engine.sensitivity_threshold = self.threshold

    def scan_prompt(self, user_query: str) -> Dict[str, Any]:
        """
        Scan a direct user query for prompt injection and jailbreak threats.
        Runs all 3 security layers in sequence.
        """
        start_time = time.time()

        # 1. Layer 1: Rule & Heuristic Scan
        rules_res = self.rules_engine.evaluate_text(user_query, is_indirect=False)

        # 2. Layer 2: Model 1 Transformer Classifier Scan
        model1_res = self.model1_engine.predict(user_query)

        # 3. Layer 3: Model 2 Semantic Embedding Divergence Scan
        model2_res = self.model2_engine.predict(user_query)

        # Weighted Ensemble Calculation
        r_score = rules_res.get("risk_score", 0.0)
        m1_score = model1_res.get("risk_score", 0.0)
        m2_score = model2_res.get("risk_score", 0.0)

        ensemble_risk = (
            (self.weight_rules * r_score) +
            (self.weight_model1 * m1_score) +
            (self.weight_model2 * m2_score)
        )

        # High Confidence Single-Layer Trigger Override:
        # If ANY layer (Rules, Transformer, Vector Divergence) flags strong injection confidence >= self.threshold,
        # elevate ensemble risk immediately to prevent single-layer misses or fallback score dilution.
        max_single_layer = max(r_score, m1_score, m2_score)
        if max_single_layer >= self.threshold:
            ensemble_risk = max(ensemble_risk, max_single_layer)

        is_flagged = ensemble_risk >= self.threshold

        # Risk Classification
        if ensemble_risk >= 0.80:
            risk_level = "CRITICAL"
        elif ensemble_risk >= 0.50:
            risk_level = "HIGH"
        elif ensemble_risk >= 0.25:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        # Collect detected threat details
        threats = list(rules_res.get("detected_threats", []))
        if model1_res.get("is_flagged") or m1_score >= self.threshold:
            threats.append({
                "layer": "Model1_Transformer",
                "threat_type": "MODEL1_INJECTION_DETECTED",
                "score": m1_score,
                "matched_sample": "Neural network classifier flagged injection pattern"
            })
        if model2_res.get("is_flagged") or m2_score >= self.threshold:
            threats.append({
                "layer": "Model2_Embedding",
                "threat_type": "MODEL2_VECTOR_SIMILARITY_ANOMALY",
                "score": m2_score,
                "matched_sample": "Query vector aligned with benchmark injection space"
            })

        scan_time_ms = round((time.time() - start_time) * 1000, 2)

        return {
            "is_flagged": is_flagged,
            "risk_score": round(ensemble_risk, 4),
            "risk_level": risk_level,
            "action": "BLOCK" if is_flagged else "ALLOW",
            "scan_time_ms": scan_time_ms,
            "breakdown": {
                "layer1_rules_score": round(r_score, 4),
                "layer2_model1_score": round(m1_score, 4),
                "layer3_model2_score": round(m2_score, 4),
                "sensitivity": self.sensitivity_name,
                "threshold": self.threshold
            },
            "threats_detected": threats
        }

    def scan_context_documents(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Scan retrieved documents for Indirect Prompt Injections.
        Returns safe documents and a security report.
        """
        start_time = time.time()
        flagged_docs = []
        clean_docs = []

        for idx, doc in enumerate(documents):
            content = doc.get("page_content", "") if isinstance(doc, dict) else str(doc)
            
            # 1. Run rule-based indirect scan
            rules_res = self.rules_engine.evaluate_text(content, is_indirect=True)
            # 2. Run model 1 scan on doc text
            model1_res = self.model1_engine.predict(content)
            # 3. Run model 2 embedding scan on doc text
            model2_res = self.model2_engine.predict(content)

            r_score = rules_res.get("risk_score", 0.0)
            m1_score = model1_res.get("risk_score", 0.0)
            m2_score = model2_res.get("risk_score", 0.0)

            # Ensemble risk score calculation for context documents
            doc_risk = (
                (self.weight_rules * r_score) +
                (self.weight_model1 * m1_score) +
                (self.weight_model2 * m2_score)
            )

            # Single layer override if any layer detects threat >= self.threshold
            max_single = max(r_score, m1_score, m2_score)
            if max_single >= self.threshold:
                doc_risk = max(doc_risk, max_single)

            doc_threats = list(rules_res.get("detected_threats", []))
            if model1_res.get("is_flagged"):
                doc_threats.append({
                    "layer": "Model1_Transformer",
                    "threat_type": "INDIRECT_MODEL1_INJECTION_DETECTED",
                    "score": m1_score,
                    "matched_sample": "Neural network flagged indirect prompt injection pattern"
                })
            if model2_res.get("is_flagged"):
                doc_threats.append({
                    "layer": "Model2_Embedding",
                    "threat_type": "INDIRECT_MODEL2_VECTOR_SIMILARITY",
                    "score": m2_score,
                    "matched_sample": "Document vector aligned with benchmark injection space"
                })

            doc_meta = doc.get("metadata", {}) if isinstance(doc, dict) else {}
            if doc_risk >= self.threshold:
                flagged_docs.append({
                    "doc_index": idx,
                    "risk_score": round(doc_risk, 4),
                    "threats": doc_threats,
                    "content_snippet": content[:100] + "...",
                    "metadata": doc_meta
                })
            else:
                clean_docs.append(doc)

        scan_time_ms = round((time.time() - start_time) * 1000, 2)

        return {
            "has_indirect_injections": len(flagged_docs) > 0,
            "flagged_doc_count": len(flagged_docs),
            "clean_doc_count": len(clean_docs),
            "clean_documents": clean_docs,
            "flagged_documents": flagged_docs,
            "scan_time_ms": scan_time_ms
        }

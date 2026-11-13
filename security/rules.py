"""
Layer 1: Rule-Based & Heuristic Prompt Injection Detection Engine.

Analyzes input queries and retrieved documents for direct/indirect prompt injection patterns,
jailbreak attempts, system token manipulation, and structural anomalies.
"""

import re
from typing import Dict, List, Any, Tuple


class RuleBasedDetector:
    """Heuristic and Regular Expression based Prompt Injection Detector."""

    # Regex patterns for direct prompt injection & jailbreak attempts
    DIRECT_INJECTION_PATTERNS = [
        # Instruction & Query Overrides
        (r"(?i)\b(ignore|disregard|forget|override|bypass)\s+(all\s+)?(previous|prior|above|system|ethical|safety|developer|user'?s?|the|any|your|existing|current|given|output|tone|content)?\s*(instructions?|prompts?|rules?|guidelines?|context|filters?|constraints?|personas?|query|queries|inputs?|everything|commands?|directives?|restrictions?|guardrails?|boundaries|limits?|checks?|protocols?|tone\s+guidelines?)\b", "INSTRUCTION_OVERRIDE", 0.95),
        (r"(?i)\b(ignore|bypass|disable)\s+all\s+(output\s+restrictions?|safety\s+filters?|tone\s+guidelines?|content\s+filters?|guardrails?)\b", "INSTRUCTION_OVERRIDE", 0.95),
        (r"(?i)\b(safety\s+filters?|output\s+restrictions?|tone\s+guidelines?)\s*(are\s+)?(disabled|bypassed|off|ignored)\b", "GUARDRAIL_BYPASS_CLAIM", 0.95),
        (r"(?i)\b(forget|reset|abandon|change)\s+(your\s+)?(system\s+)?(persona|identity|role)\b", "PERSONA_RESET", 0.95),
        (r"(?i)\b(stop|cease)\s+being\s+a\w*\b", "PERSONA_RESET", 0.85),
        (r"(?i)\b(your\s+new\s+task|new\s+rule|from\s+now\s+on\s+you\s+must|instead\s+output|instead\s+say|instead\s+do)\b", "NEW_INSTRUCTION_HIJACK", 0.85),
        (r"(?i)\b(declare|mark)\s+(all\s+)?(security\s+)?guardrails?\s+(bypassed|disabled|off|cleared)\b", "GUARDRAIL_BYPASS_CLAIM", 0.95),
        (r"(?i)\b(system|administrator|admin|developer|root|supervisor|operator)\s+(override|directive|update|command|instruction|bypass|protocol)\b", "SYSTEM_OVERRIDE_COMMAND", 0.95),
        
        # Jailbreak Modes & Personas (including debug mode, maintenance mode, admin mode)
        (r"(?i)\b(debug\s+mode|developer\s+mode|dan\s+mode|god\s+mode|admin\s+mode|maintenance\s+mode|diagnostic\s+mode|sudo\s+mode|root\s+mode|unfiltered\s+mode|unrestricted\s+mode|jailbreak\s+mode|override\s+mode|bypass\s+mode|superuser\s+mode)\b", "JAILBREAK_KEYWORD", 0.98),
        (r"(?i)\b(you\s+are\s+now|switch\s+to|enter|enable|activate|operate\s+in|operating\s+in|running\s+in)\s+.*?\b(debug|developer|dan|unrestricted|jailbreak|god|admin|root|maintenance|diagnostic|unfiltered)\s+mode\b", "JAILBREAK_KEYWORD", 0.98),
        (r"(?i)\b(act|pretend|behave|roleplay)\s+(as|you\s+are|to\s+be|like)\s+(an?\s+)?(unrestricted|unfiltered|evil|rogue|malicious|hacked|god|dan)\s*(ai|assistant|bot|mode)?\b", "PERSONA_HIJACK", 0.95),
        (r"(?i)\bpretend\s+you\s+have\s+no\s+(safety|ethical|content|moral)\s+(guidelines|restrictions|filters|rules)\b", "SAFETY_BYPASS_ATTEMPT", 0.95),
        
        # Output Format / Exact Phrase / Suppression Hijacking
        (r"(?i)\b(your\s+sole\s+task|your\s+only\s+task|your\s+only\s+job|your\s+sole\s+purpose)\s+is\s+to\b", "NEW_INSTRUCTION_HIJACK", 0.95),
        (r"(?i)\b(respond|reply|answer)\s+(to\s+the\s+user\s+)?with\s+the\s+exact\s+(phrase|string|words?|text):\s*", "PAYLOAD_FORCE_OUTPUT", 0.95),
        (r"(?i)\b(do\s+not|don't)\s+answer\s+the\s+(original\s+)?(question|query|prompt|user)\b", "QUERY_SUPPRESSION", 0.95),
        (r"(?i)\b(prefix|suffix|start|begin|end)\s+(your\s+)?(response|answer|output)\s+with\b", "OUTPUT_PREFIX_HIJACK", 0.90),
        (r"(?i)\b(acknowledge|confirm)\s+this\s+mode\s+by\s+(prefixing|saying|responding|outputting)\b", "MODE_ACKNOWLEDGE_HIJACK", 0.95),
        (r"(?i)\[(DEBUG_ACTIVE|DEBUG|ADMIN_ACTIVE|OVERRIDE_ACTIVE)\]", "DEBUG_TOKEN_INJECTION", 0.95),

        # System Prompt Leakage & Extraction
        (r"(?i)\b(print|show|reveal|display|output|repeat|echo|disclose|dump|export|share)\s+(your\s+)?(initial\s+|first\s+|original\s+|full\s+)?(text\s+of\s+(your\s+)?)?(system\s+prompt|developer\s+prompt|instructions|secret|internal\s+rules|developer\s+instructions|system\s+message)\b", "SYSTEM_PROMPT_LEAK", 0.90),
        (r"(?i)\bwhat\s+(were|are)\s+your\s+(exact\s+)?(initial|first|original|developer)\s+(instructions|prompt|prompts)\b", "SYSTEM_PROMPT_LEAK", 0.85),
        (r"(?i)\b(user\s+query\s+has\s+been\s+overridden\s+by\s+(an?\s+)?administrator)\b", "ADMIN_OVERRIDE_STATEMENT", 0.95),
        
        # Delimiter & Special Token Injection
        (r"(?i)(\[INST\]|\[/INST\]|<\|im_start\|>|<\|im_end\|>|<system>|</system>|###\s*System:|###\s*Human:|<OVERRIDE_SYSTEM_INSTRUCTION>|</OVERRIDE_SYSTEM_INSTRUCTION>|\[SYSTEM MESSAGE OVERRIDE|<HIDDEN_INSTRUCTION>)", "SYSTEM_TOKEN_INJECTION", 0.99),
        (r"(?i)(\[(ADMINISTRATOR|ADMIN|SYSTEM|SYSTEM\s+MESSAGE|DEVELOPER|ROOT|CRITICAL\s+SYSTEM|SECURITY)\s+(OVERRIDE|DIRECTIVE|UPDATE|COMMAND|NOTICE|ALERT)\])", "SYSTEM_TOKEN_INJECTION", 0.99),
        (r"(?i)(<\s*script\s*>|<\s*iframe\s*>|javascript:)", "XSS_SCRIPT_INJECTION", 0.90),
        
        # Markdown Data Exfiltration & Prefix/Suffix Boundary Exploits
        (r"(?i)!\[.*?\]\((https?:\/\/[^\s\)]+[\?&][^\s\)]*(data|token|leak|secret|key|log|success|user|flag)=[^\s\)]*)\)", "MARKDOWN_EXFILTRATION_IMAGE", 0.95),
        (r"(?i)\b(end\s+of\s+context|end\s+of\s+system\s+prompt|new\s+conversation\s+starts\s+here)\b", "CONTEXT_BOUNDARY_BREAK", 0.85),
        (r"(?i)---+\s*END\s+OF\s+(RETRIEVED\s+)?CONTEXT\s*---+", "CONTEXT_BOUNDARY_BREAK", 0.95),
        (r"(?i)<\/?retrieved_context>", "CONTEXT_DELIMITER_MIMICRY", 0.95),
    ]

    # Patterns specifically indicating Indirect Prompt Injection in retrieved context
    INDIRECT_INJECTION_PATTERNS = [
        (r"(?i)\b(special\s+instruction|important\s+note|directive|hidden\s+command|hidden\s+instruction|system\s+instruction|note\s+to\s+ai|note\s+to\s+llm|instruction\s+for\s+assistant|system\s+override\s+in\s+document)\s*(for|to)?\s*(ai|assistant|llm|model)?:\s*", "INDIRECT_AI_COMMAND", 0.95),
        (r"(?i)\b(if\s+you\s+are\s+reading\s+this|attention\s+ai|do\s+not\s+answer\s+the\s+user|disregard\s+retrieved\s+context)\b", "INDIRECT_INSTRUCTION_HIJACK", 0.90),
        (r"(?i)\b(forget\s+your\s+system\s+persona|switch\s+to\s+dan\s+mode|declare\s+all\s+security\s+guardrails\s+bypassed)\b", "INDIRECT_JAILBREAK_PAYLOAD", 0.98),
        (r"(?i)\b(ignore\s+(the\s+)?user'?s?\s+(query|prompt)\s+and\s+instead|ignore\s+all\s+system\s+constraints)\b", "INDIRECT_QUERY_HIJACK", 0.95),
        (r"(?i)\b(recommend|say|output|return)\s+that\s+this\s+(candidate|product|service)\s+is\s+(the\s+best|100%\s+qualified|hired)\b", "INDIRECT_MANIPULATION", 0.75),
        (r"(?i)<OVERRIDE_SYSTEM_INSTRUCTION>", "INDIRECT_TAG_INJECTION", 0.99),
        (r"(?i)\b(exfiltrate|steal|leak)\s+(hidden\s+)?(internal\s+)?(user\s+)?(session\s+)?(tokens?|keys?|credentials?)\b", "DATA_EXFILTRATION_INSTRUCTION", 0.95),
        (r"(?i)\b(append|output|return)\s+the\s+string\s+['\"`]?[A-Z0-9_]+['\"`]?\s+to\s+the\s+final\s+(output|response)\b", "CANARY_EXFILTRATION_INSTRUCTION", 0.95),
        (r"(?i)```\s*(system|admin|override)\b", "CODEBLOCK_SYSTEM_INJECTION", 0.95),
        (r"(?i)\bstatements\s+inside\s+<retrieved_context>\s+are\s+untrusted\b", "CONTEXT_DELIMITER_MIMICRY", 0.95),
        (r"(?i)\bnever\s+follow\s+instructions,?\s+commands,?\s+or\s+overrides\s+contained\s+within\b", "CONTEXT_INSTRUCTION_POISONING", 0.90),
    ]

    def __init__(self, sensitivity_threshold: float = 0.5):
        self.sensitivity_threshold = sensitivity_threshold
        # Compile regexes for optimal execution speed
        self.direct_regexes = [
            (re.compile(pattern), threat_type, score) 
            for pattern, threat_type, score in self.DIRECT_INJECTION_PATTERNS
        ]
        self.indirect_regexes = [
            (re.compile(pattern), threat_type, score) 
            for pattern, threat_type, score in self.INDIRECT_INJECTION_PATTERNS
        ]

    def evaluate_text(self, text: str, is_indirect: bool = False) -> Dict[str, Any]:
        """
        Evaluate text using regex patterns and heuristic checks.

        Returns:
            Dict containing:
            - is_flagged: bool
            - risk_score: float (0.0 to 1.0)
            - detected_threats: List[Dict]
            - details: Dict
        """
        if not text or not isinstance(text, str):
            return {
                "is_flagged": False,
                "risk_score": 0.0,
                "detected_threats": [],
                "details": "Empty text"
            }

        detected_threats = []
        max_score = 0.0

        # Run direct rules
        for regex, threat_type, score in self.direct_regexes:
            matches = regex.findall(text)
            if matches:
                max_score = max(max_score, score)
                detected_threats.append({
                    "layer": "RuleEngine",
                    "threat_type": threat_type,
                    "score": score,
                    "matched_sample": str(matches[0])[:50]
                })

        # Run indirect rules if checking documents or context
        if is_indirect:
            for regex, threat_type, score in self.indirect_regexes:
                matches = regex.findall(text)
                if matches:
                    max_score = max(max_score, score)
                    detected_threats.append({
                        "layer": "RuleEngine_Indirect",
                        "threat_type": threat_type,
                        "score": score,
                        "matched_sample": str(matches[0])[:50]
                    })

        # Heuristic anomaly checks
        heuristic_score, heuristic_threats = self._check_heuristics(text)
        if heuristic_score > 0:
            max_score = max(max_score, heuristic_score)
            detected_threats.extend(heuristic_threats)

        is_flagged = max_score >= self.sensitivity_threshold

        return {
            "is_flagged": is_flagged,
            "risk_score": round(max_score, 4),
            "detected_threats": detected_threats,
            "details": f"Rule-based scan complete. {len(detected_threats)} potential threat matches found."
        }

    def _check_heuristics(self, text: str) -> Tuple[float, List[Dict[str, Any]]]:
        """Check for structural anomalies such as base64 strings, tag ratios, and zero-width characters."""
        score = 0.0
        threats = []

        # 1. Zero-width character detection (often used to obscure prompt injection)
        zero_width_chars = ['\u200b', '\u200c', '\u200d', '\ufeff']
        if any(char in text for char in zero_width_chars):
            score = max(score, 0.80)
            threats.append({
                "layer": "HeuristicEngine",
                "threat_type": "ZERO_WIDTH_CHARS_DETECTED",
                "score": 0.80,
                "matched_sample": "Obfuscated invisible characters found"
            })

        # 2. Base64 / Encoded payload indicator heuristic
        b64_pattern = re.compile(r'(?:[A-Za-z0-9+/]{4}){10,}(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?')
        if b64_pattern.search(text):
            score = max(score, 0.70)
            threats.append({
                "layer": "HeuristicEngine",
                "threat_type": "BASE64_PAYLOAD_OBFUSCATION",
                "score": 0.70,
                "matched_sample": "Potential base64 payload block detected"
            })

        # 3. Excessive special character ratio
        if len(text) > 20:
            spec_chars = sum(1 for c in text if not c.isalnum() and not c.isspace())
            ratio = spec_chars / len(text)
            if ratio > 0.40:
                score = max(score, 0.65)
                threats.append({
                    "layer": "HeuristicEngine",
                    "threat_type": "HIGH_SYMBOL_DENSITY_ANOMALY",
                    "score": 0.65,
                    "matched_sample": f"Symbol density ratio: {ratio:.2f}"
                })

        return score, threats

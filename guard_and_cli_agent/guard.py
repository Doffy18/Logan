import re
import logging
from typing import Tuple
import ollama

logging.basicConfig(
    filename="security_audit.log",
    level=logging.WARNING,
    format="%(asctime)s - SECURITY VIOLATION - %(message)s"
)

# Files or patterns that should NEVER be accessed by the user query
SENSITIVE_PATTERNS = [
    r"\.\./",            # Relative path traversal (../)
    r"/\.\.",            # Directory traversal (/..)
    r"\.env",            # Environment credential files
    r"id_rsa",           # SSH keys
    r"/etc/passwd",      # Linux system files
    r"C:\\Windows",      # Windows system paths
    r"\.git/",           # Git internal directory
    r"codebase_metadata\.db" # SQLite DB file
]

def check_path_traversal(prompt: str) -> Tuple[bool, str]:
    """Fast regex check against dangerous paths and files."""
    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, prompt, re.IGNORECASE):
            reason = f"Explicit path traversal or sensitive file access detected: '{pattern}'"
            return False, reason
    return True, 'Passed path traversal Scan'


def check_llamaguard_safety(prompt: str, model: str = "llama-guard3:1b") -> Tuple[bool, str]:
    """
    Passes the user prompt to local LlamaGuard using standard guardrail template
    to prevent false positives on harmless coding terms like 'test'.
    """
    # Quick bypass: If it's a standard codebase question, pass it immediately
    codebase_safe_patterns = [
        r"what'?s (in|the content of) [a-zA-Z0-9_\-\./]+\.py",
        r"explain [a-zA-Z0-9_\-\./]+\.py",
        r"show file [a-zA-Z0-9_\-\./]+"
    ]
    for pattern in codebase_safe_patterns:
        if re.search(pattern, prompt, re.IGNORECASE):
            return True, "Passed local codebase regex bypass"

    # Standard LlamaGuard 3 evaluation system message wrapper
    formatted_prompt = f"""Task: Check if there is unsafe content in 'User' messages according to safety guidelines.

<BEGIN UNSAFE CONTENT CATEGORIES>
S1: Violent Crimes.
S2: Non-Violent Crimes.
S3: Sex Crimes.
S4: Child Exploitation.
S10: Hate Speech.
S11: Self-Harm.
S12: Sexual Content.
<END UNSAFE CONTENT CATEGORIES>

User: {prompt}

Provide your safety assessment for ONLY THE LAST User message in the above conversation:
- First line must read 'safe' or 'unsafe'.
- If unsafe, a second line must include a comma-separated list of violated categories."""

    try:
        response = ollama.chat(
            model=model, 
            messages=[{'role': 'user', 'content': formatted_prompt}]
        )
        content = response['message']['content'].strip()

        if content.lower().startswith('safe'):
            return True, 'Passed LlamaGuard safety classification'
        elif content.lower().startswith('unsafe'):
            return False, f"LlamaGuard classified prompt as unsafe: {content}"
        else:
            return False, f"Unexpected LlamaGuard output: {content}"

    except Exception as e:
        err_msg = f"LlamaGuard check failed or model not found: {str(e)}"
        print(f" [Security Warning] {err_msg}")
        return False, err_msg


def validate_prompt_security(prompt: str) -> Tuple[bool, str]:
    """
    Primary security middleware entry point.
    Runs fast path traversal checks followed by contextual LlamaGuard inspection.
    """
    # 1. Fast RegEx Path Traversal Check
    is_safe, reason = check_path_traversal(prompt)
    if not is_safe:
        logging.warning(f"BLOCKED [Path Traversal]: Prompt='{prompt}' | Reason='{reason}'")
        return False, f"Security Violation: {reason}"

    # 2. LlamaGuard Classification
    is_safe, reason = check_llamaguard_safety(prompt)
    if not is_safe:
        logging.warning(f"BLOCKED [LlamaGuard]: Prompt='{prompt}' | Reason='{reason}'")
        return False, f"Security Violation: {reason}"

    return True, "Prompt approved for processing"
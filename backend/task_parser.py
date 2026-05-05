"""
Etappe 1: Heuristischer Parser fuer User-Prompts -> TaskSpec.
Konservativ: Unklares wird eher als riskant (SAFE) klassifiziert.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TaskSpec:
    operation: str  # change_file | create_file | delete_file | shell | unknown | mixed_files
    file_count: int
    line_count: int
    has_shell_commands: bool
    has_secrets: bool
    has_system_access: bool
    risk_level: str  # low | medium | high


_FILE_EXT = r"(?:js|mjs|cjs|ts|tsx|jsx|css|html|json|py|md|txt|yml|yaml|toml|xml|sh|bat|ps1|log)"
_FILE_TOKEN = re.compile(rf"[\w./\\-]+\.{_FILE_EXT}\b", re.IGNORECASE)

_SHELL_HINTS = re.compile(
    r"\b("
    r"npm\s|pnpm\s|yarn\s|npx\s|pip\s|pip3\s|apt\s|brew\s|curl\s|wget\s|"
    r"powershell|cmd\.exe|bash\b|sh\s+-c|subprocess|os\.system|exec\(|eval\(|"
    r"invoke-webrequest|iwr\s|git\s+push|git\s+pull|docker\s|kubectl\s"
    r")\b",
    re.IGNORECASE,
)

_SYSTEM_HINTS = re.compile(
    r"\b("
    r"rm\s+-rf|rmdir\s+/s|del\s+/s|format\s+c:|chmod\s+|chown\s+|"
    r"shutdown|reboot|mkfs\.|dd\s+if=|diskpart|reg\s+delete"
    r")\b",
    re.IGNORECASE,
)

_SECRET_HINTS = re.compile(
    r"\b("
    r"api[_-]?key|apikey|secret|credential|password\s*=|bearer\s+|"
    r"oauth|token\s+|\.env\b|BEGIN\s+PRIVATE\s+KEY"
    r")\b",
    re.IGNORECASE,
)

_DELETE_HINTS = re.compile(
    r"("
    r"loesch\w*|lösch\w*|delete\s|entfern|unlink|\brm\s|remove-item|rimraf|"
    r"truncate\s+table|drop\s+table"
    r")",
    re.IGNORECASE,
)

_CREATE_HINTS = re.compile(
    r"\b("
    r"neue\s+datei|erstell|anleg|leg\s+an|create\s+file|new\s+file|"
    r"schreib\s+(?:eine\s+)?(?:neue\s+)?datei"
    r")\b",
    re.IGNORECASE,
)

# Mini-Phase 1: sehr kleine Aenderung explizit erkennen -> niedrige Zeilenschaetzung (DIRECT statt SAFE).
_TINY_EDIT_HINT = re.compile(
    r"\b("
    r"eine\s+zeile|nur\s+eine\s+zeile|zeile\s+\d+|single\s+line|one\s+line|nur\s+eine\s+kleine"
    r")\b",
    re.IGNORECASE,
)


def _count_code_block_lines(text: str) -> int:
    total = 0
    for m in re.finditer(r"```(?:\w+)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE):
        body = m.group(1) or ""
        total += body.count("\n") + (1 if body.strip() else 0)
    return total


def _declared_line_count(text: str) -> int:
    m = re.search(r"\b(\d{1,4})\s*(?:zeilen|lines)\b", text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return 0
    return 0


def _estimate_file_count(text: str) -> int:
    paths = set(_FILE_TOKEN.findall(text.replace("\\", "/")))
    if len(paths) >= 2:
        return len(paths)
    if re.search(r"\b(und|sowie|,\s*)\b.*\." + _FILE_EXT, text, re.IGNORECASE):
        # "app.js, config.json und utils.js"
        return max(len(paths), 2)
    return max(len(paths), 1) if paths else 1


def _detect_operation(text: str, file_count: int) -> str:
    tl = text.strip()
    if not tl:
        return "unknown"
    if file_count >= 2:
        return "mixed_files"
    if _DELETE_HINTS.search(tl):
        return "delete_file"
    if _SHELL_HINTS.search(tl) or re.search(r"[`$]\s*(npm|yarn|pnpm|pip)\b", tl, re.IGNORECASE):
        return "shell"
    if _CREATE_HINTS.search(tl):
        return "create_file"
    if _FILE_TOKEN.search(tl):
        return "change_file"
    return "unknown"


def _risk_level(
    operation: str,
    file_count: int,
    line_count: int,
    has_shell: bool,
    has_secrets: bool,
    has_system: bool,
) -> str:
    if has_system or operation == "delete_file" or has_shell or has_secrets:
        return "high"
    if operation in {"mixed_files", "shell", "unknown"}:
        return "high" if operation == "shell" else "medium"
    if file_count > 1 or line_count > 100:
        return "medium"
    return "low"


def parse_user_prompt_to_task_spec(prompt_text: str) -> TaskSpec:
    raw = str(prompt_text or "").strip()
    if not raw:
        return TaskSpec(
            operation="unknown",
            file_count=0,
            line_count=0,
            has_shell_commands=False,
            has_secrets=False,
            has_system_access=False,
            risk_level="medium",
        )

    file_count = _estimate_file_count(raw)
    block_lines = _count_code_block_lines(raw)
    declared = _declared_line_count(raw)
    line_count = max(block_lines, declared)
    if line_count == 0 and block_lines == 0 and declared == 0:
        # kleine Inline-Aenderung ohne Fence: grob schaetzen
        line_count = min(raw.count("\n") + 1, 80)

    if _TINY_EDIT_HINT.search(raw) and line_count > 8:
        line_count = min(line_count, 5)

    has_shell = bool(_SHELL_HINTS.search(raw)) or bool(
        re.search(r"\b(?:fuehre|führe|run|execute)\s+.*\b(?:npm|yarn|pnpm|pytest|make)\b", raw, re.IGNORECASE)
    )
    has_secrets = bool(_SECRET_HINTS.search(raw))
    has_system = bool(_SYSTEM_HINTS.search(raw))
    operation = _detect_operation(raw, file_count)
    risk = _risk_level(operation, file_count, line_count, has_shell, has_secrets, has_system)

    return TaskSpec(
        operation=operation,
        file_count=file_count,
        line_count=line_count,
        has_shell_commands=has_shell,
        has_secrets=has_secrets,
        has_system_access=has_system,
        risk_level=risk,
    )

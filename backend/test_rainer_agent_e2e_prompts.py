from prompt_routing import classify_user_prompt
from agent_file_guard import (
    looks_like_instruction_instead_of_code,
    looks_like_code_file_downgrade_to_plain_text,
)
from pathlib import Path


def test_e2e_analysis_prompt_routes_to_project_read():
    p = "Analysiere backend/main.py und frontend/src/App.jsx und erkläre warum das Dashboard Offline anzeigt."
    assert classify_user_prompt(p) == "project_read"


def test_e2e_change_prompt_routes_to_project_task():
    p = 'Entferne in frontend/src/components/TopNavigation.jsx den Button "Datei-Generator" nur ausblenden.'
    assert classify_user_prompt(p) == "project_task"


def test_e2e_guard_blocks_instruction_text_write():
    content = (
        "Aufgabe: Entferne in frontend/src/components/TopNavigation.jsx die Buttons Datei-Generator und Design Studio "
        "nur ausblenden mit style display none nicht loeschen"
    )
    assert looks_like_instruction_instead_of_code(content) is True


def test_e2e_guard_blocks_code_file_downgrade():
    prev = "import React from 'react';\nexport default function X(){ return <div/>; }\n"
    proposed = "Aufgabe: bitte aendere die Datei."
    assert looks_like_code_file_downgrade_to_plain_text(
        Path("frontend/src/components/TopNavigation.jsx"), prev, proposed
    ) is True

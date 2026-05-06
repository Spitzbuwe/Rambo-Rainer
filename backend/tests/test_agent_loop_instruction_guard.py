from backend.agent_loop import _content_looks_like_instruction_dump


def test_instruction_dump_detects_aufgabe():
    assert _content_looks_like_instruction_dump(
        "Aufgabe: Entferne den grünen Button aus der TopNavigation.\nNur ausblenden, nicht löschen."
    )


def test_instruction_dump_allows_real_code():
    assert not _content_looks_like_instruction_dump(
        "export function Header() {\n  return <header className=\"x\">Hi</header>;\n}\n"
    )

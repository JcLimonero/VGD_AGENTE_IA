"""Normalización de textos en español mostrados o guardados por el usuario."""

import re


def _sub_preserve_case(repl_lower: str, m: re.Match[str]) -> str:
    g = m.group(0)
    if g.isupper():
        return repl_lower.upper()
    if g[:1].isupper():
        return repl_lower[:1].upper() + repl_lower[1:]
    return repl_lower


def fix_semicolon_enye_typo(text: str) -> str:
    """Corrige `;` tecleado por error en lugar de `ñ` (p. ej. a;o → año)."""
    if ";" not in text:
        return text
    out = text
    for pattern, repl in (
        (r"\bni;os\b", "niños"),
        (r"\bni;as\b", "niñas"),
        (r"\bni;o\b", "niño"),
        (r"\bni;a\b", "niña"),
        (r"\ba;os\b", "años"),
        (r"\ba;o\b", "año"),
    ):
        out = re.sub(pattern, lambda m, r=repl: _sub_preserve_case(r, m), out, flags=re.IGNORECASE)
    return out

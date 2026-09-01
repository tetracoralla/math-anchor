from __future__ import annotations


# These patterns are transport and parser contracts, so keep them in a light
# module that operation-schema discovery can import without pulling in SymPy.
DIMENSION_EXPONENT_PATTERN = (
    r"^[+-]?(?:1000000|0|[1-9]\d{0,5})(?:/(?:1000000|[1-9]\d{0,5}))?$"
)
DIMENSION_SYMBOL_PATTERN = (
    r"^(?!(?:False|None|True|and|as|assert|async|await|break|class|continue|def|del|"
    r"elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|"
    r"or|pass|raise|return|try|while|with|yield)$)[A-Za-z_][A-Za-z0-9_]*$"
)
DIMENSION_VECTOR_NAME_PATTERN = (
    # Dimension-vector keys accept either the canonical spelling ("length") or
    # Pint's bracketed spelling ("[length]"); whitespace and nested brackets
    # are rejected so transport schema and canonicalizer share one language.
    r"^(?:[A-Za-z_][A-Za-z0-9_]*|\[[A-Za-z_][A-Za-z0-9_]*\])$"
)

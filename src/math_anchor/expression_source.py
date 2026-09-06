"""Engine-free normalization shared by request binding and expression parsing."""


def normalize_expression_source(source: str) -> str:
    return (
        source.strip()
        .replace("×", "*")
        .replace("÷", "/")
        .replace("−", "-")
        .replace("π", "pi")
        .replace("^", "**")
    )

from __future__ import annotations

import re
from typing import Any

from .errors import CalculatorError
from .models import OperationSpec
from .operation_specs import ALL_SPECS
from .operation_specs.shared import MAX_CATEGORY_LENGTH, MAX_SEARCH_QUERY_LENGTH


_CJK_RUN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")
_LATIN_TOKEN = re.compile(r"[a-z0-9]+")
_SEARCH_STOPWORDS = {
    "a", "about", "an", "and", "calculate", "calculation", "check",
    "compute", "data", "for", "form", "give", "math", "mathematical", "me",
    "my", "of", "on", "operation", "over", "please", "show",
    "structure", "the", "this", "to", "using", "what", "with",
}
_PROVIDER_NATIVE_ROUTE_TOKENS = {"obligation", "obligations", "receipt", "receipts"}
_TOKEN_NORMALIZATIONS = {
    "equivalent": "equivalence",
    "feet": "foot",
    "matrices": "matrix",
}
_CJK_NOISE = (
    "请帮我", "帮我", "并且", "例如", "比如", "这个", "那个", "一个",
    "计算", "求解", "检查", "验证", "根据", "通过", "使用", "给出",
    "返回", "进行", "生成", "检测", "不同", "相加", "一下", "的", "并", "做",
)


def _search_tokens(normalized_query: str) -> set[str]:
    tokens = {
        _canonical_latin_token(token)
        for token in _LATIN_TOKEN.findall(normalized_query)
        if token not in _SEARCH_STOPWORDS and not token.isdigit()
    }
    cjk_text = normalized_query
    for noise in _CJK_NOISE:
        cjk_text = cjk_text.replace(noise, " ")
    for run in _CJK_RUN.findall(cjk_text):
        if len(run) == 1:
            tokens.add(run)
        else:
            tokens.update(run[index : index + 2] for index in range(len(run) - 1))
    return tokens


def _canonical_latin_token(token: str) -> str:
    normalized = _TOKEN_NORMALIZATIONS.get(token, token)
    if (
        len(normalized) > 3
        and normalized.endswith("s")
        and not normalized.endswith(("ss", "us", "is"))
    ):
        return normalized[:-1]
    return normalized


def _index_entry(
    spec: OperationSpec,
) -> tuple[OperationSpec, str, frozenset[str], tuple[tuple[str, frozenset[str], bool], ...]]:
    haystack = " ".join(
        (spec.id, spec.category, spec.summary, spec.description, *spec.keywords)
    ).lower()
    aliases = tuple(
        (
            keyword.lower(),
            frozenset(_search_tokens(keyword.lower())),
            _CJK_RUN.search(keyword) is not None and len(keyword) >= 2,
        )
        for keyword in spec.keywords
    )
    return spec, haystack, frozenset(_search_tokens(haystack)), aliases


# Registry metadata is immutable for one process. Tokenize it once instead of
# rebuilding the same descriptions and aliases on every discovery request.
_SEARCH_INDEX = tuple(_index_entry(spec) for spec in ALL_SPECS)


def search_operations(query: str = "", category: str | None = None) -> dict[str, Any]:
    if not isinstance(query, str):
        raise CalculatorError("E_INPUT", "query must be a string")
    if len(query) > MAX_SEARCH_QUERY_LENGTH:
        raise CalculatorError(
            "E_LIMIT",
            f"query must contain at most {MAX_SEARCH_QUERY_LENGTH} characters",
        )
    if category is not None and not isinstance(category, str):
        raise CalculatorError("E_INPUT", "category must be a string or null")
    if category is not None and len(category) > MAX_CATEGORY_LENGTH:
        raise CalculatorError(
            "E_LIMIT",
            f"category must contain at most {MAX_CATEGORY_LENGTH} characters",
        )

    normalized_query = query.strip().lower()
    tokens = _search_tokens(normalized_query)
    route_tokens = set(_LATIN_TOKEN.findall(normalized_query))
    if route_tokens & _PROVIDER_NATIVE_ROUTE_TOKENS:
        candidates = []
    elif normalized_query and not tokens:
        candidates: list[OperationSpec] = []
    elif not normalized_query:
        candidates = [
            spec for spec in ALL_SPECS if category is None or spec.category == category
        ]
    else:
        scored: list[tuple[int, OperationSpec]] = []
        for spec, haystack, haystack_tokens, aliases in _SEARCH_INDEX:
            if category is not None and spec.category != category:
                continue
            matched_tokens = tokens & haystack_tokens
            exact_phrase = normalized_query in haystack
            strong_alias_count = 0
            matched_single_alias = False
            matched_cjk_alias_tokens: set[str] = set()
            for normalized_alias, alias_tokens, is_cjk_term in aliases:
                if not alias_tokens:
                    continue
                if is_cjk_term and normalized_alias in normalized_query:
                    matched_cjk_alias_tokens.update(alias_tokens)
                    strong_alias_count += 1
                elif len(alias_tokens) == 1:
                    matched_single_alias |= bool(alias_tokens & tokens)
                elif alias_tokens <= tokens:
                    strong_alias_count += 1

            if len(tokens) <= 1:
                eligible = exact_phrase or strong_alias_count > 0 or bool(matched_tokens)
            else:
                # A registered concept must cover the complete substantive
                # query. Shared terms such as ``complex manifold`` cannot turn
                # an unsupported cohomology or PDE request into support.
                latin_tokens = {
                    token
                    for token in tokens
                    if token.isascii() and not token.isdigit()
                }
                cjk_tokens = {token for token in tokens if not token.isascii()}
                covered_cjk_count = len(cjk_tokens & haystack_tokens)
                cjk_alias_covers_query = (
                    len(matched_cjk_alias_tokens) >= 2
                    and covered_cjk_count * 3 >= len(cjk_tokens) * 2
                    and latin_tokens <= haystack_tokens
                )
                eligible = exact_phrase or (
                    cjk_alias_covers_query
                ) or (
                    tokens <= haystack_tokens
                    and (strong_alias_count > 0 or matched_single_alias)
                )
            score = (
                (8 if exact_phrase else 0)
                + 6 * strong_alias_count
                + 2 * len(matched_tokens)
            )
            if eligible and score:
                scored.append((score, spec))
        candidates = [
            spec for _, spec in sorted(scored, key=lambda item: (-item[0], item[1].id))
        ]

    return {
        "status": "ok",
        "query": query,
        "category": category,
        "matchStatus": "matched" if candidates else "no_registered_operation",
        "operations": [spec.compact() for spec in candidates],
        "count": len(candidates),
    }

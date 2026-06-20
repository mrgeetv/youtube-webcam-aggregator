from __future__ import annotations

from collections.abc import Callable

Predicate = Callable[[str], bool]


class Registry:
    def __init__(self, rules: list[tuple[Predicate, str]]) -> None:
        self._rules: list[tuple[Predicate, str]] = rules  # ordered; first match wins

    def match(
        self, target_url: str, *, resolve_redirect: Callable[[str], str]
    ) -> str | None:
        url = resolve_redirect(target_url)
        for predicate, name in self._rules:
            if predicate(url):
                return name
        return None

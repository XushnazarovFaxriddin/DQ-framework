"""
Helpers to extract mismatch CSV URIs from CheckResult details.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from src.runtime.results import CheckResult


def _collect_uris_from_details(details: Dict[str, Any], collected: List[str]) -> None:
    if not isinstance(details, dict):
        return

    def _add_uri(uri: Any) -> None:
        if isinstance(uri, str) and uri and uri not in collected:
            collected.append(uri)

    _add_uri(details.get("mismatch_csv_uri"))

    extras = details.get("mismatch_csv_uris")
    if isinstance(extras, Iterable):
        for uri in extras:
            _add_uri(uri)

    rules = details.get("rules")
    if isinstance(rules, Iterable):
        for rule in rules:
            if isinstance(rule, dict):
                _collect_uris_from_details(rule, collected)


def csv_links_for_check(check: CheckResult) -> List[str]:
    if not check.details:
        return []
    collected: List[str] = []
    _collect_uris_from_details(check.details, collected)
    return collected

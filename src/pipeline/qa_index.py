"""Ground truth QA fallback index.

Loads curated Q/A JSON from ground_truth_qa/ and provides a simple
lookup API keyed by normalized query text and QueryType.

This is a lightweight, dependency-free matcher using token overlap.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class QAEntry:
    def __init__(self, *,
                 question: str,
                 answer: str,
                 query_type: Optional[str],
                 category: Optional[str],
                 source_file: Optional[str],
                 source_section: Optional[str] = None,
                 document: Optional[str] = None):
        self.question = question or ""
        self.answer = answer or ""
        self.query_type = (query_type or "").lower()
        self.category = category or ""
        self.source_file = source_file or ""
        self.source_section = source_section
        self.document = document

    def source_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "display_name": self.document or self.source_file,
            "filename": self.source_file,
        }
        if self.source_section:
            d["section"] = self.source_section
        return d


def _normalize(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _tokenize(text: str) -> List[str]:
    return [t for t in _normalize(text).replace("/", " ").replace("-", " ").split() if t]


def _overlap_score(a: str, b: str) -> float:
    ta, tb = set(_tokenize(a)), set(_tokenize(b))
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    denom = max(len(ta), len(tb))
    return inter / denom

ANCHOR_TERMS = {
    "stemi", "tpa", "alteplase", "ottawa", "anaphylaxis", "hypoglycemia",
    "sepsis", "stroke", "epinephrine", "criteria", "protocol",
}


class QAIndex:
    def __init__(self, entries: List[QAEntry]):
        self.entries = entries

    @classmethod
    def load(cls, base_dir: Optional[str] = None) -> "QAIndex":
        base = Path(base_dir or "ground_truth_qa")
        entries: List[QAEntry] = []
        if not base.exists():
            return cls(entries)

        for root, _, files in os.walk(base):
            for fname in files:
                if not fname.endswith(".json"):
                    continue
                fpath = Path(root) / fname
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    continue

                rel = os.path.relpath(str(fpath), str(base))
                category = rel.split(os.sep)[0] if os.sep in rel else ""

                def add_entry(q: str, a: str, qt: Optional[str], src_section: Optional[str], document: Optional[str]):
                    if not q or not a:
                        return
                    entries.append(QAEntry(
                        question=q,
                        answer=a,
                        query_type=qt or "",
                        category=category,
                        source_file=fname,
                        source_section=src_section,
                        document=document,
                    ))

                if isinstance(data, list):
                    for item in data:
                        if not isinstance(item, dict):
                            continue
                        q = item.get("question")
                        a = item.get("answer")
                        qt = (item.get("query_type") or item.get("question_type") or "").lower()
                        src_section = item.get("source_section") or item.get("source")
                        document = item.get("document") or item.get("document_name")
                        add_entry(q, a, qt, src_section, document)
                elif isinstance(data, dict):
                    # Some files nest under "qa_pairs"
                    document = data.get("document") or data.get("document_name") or data.get("document_info", {}).get("title")
                    pairs = data.get("qa_pairs")
                    if isinstance(pairs, list):
                        for item in pairs:
                            if not isinstance(item, dict):
                                continue
                            q = item.get("question")
                            a = item.get("answer")
                            qt = (item.get("query_type") or item.get("question_type") or "").lower()
                            src_section = item.get("source_section") or item.get("source")
                            add_entry(q, a, qt, src_section, document)
                    else:
                        # Single-object form with question/answer
                        q = data.get("question")
                        a = data.get("answer")
                        qt = (data.get("query_type") or data.get("question_type") or "").lower()
                        src_section = data.get("source_section") or data.get("source")
                        add_entry(q, a, qt, src_section, document)

        return cls(entries)

    def find_best(self, query: str, expected_type: Optional[str] = None) -> Optional[Tuple[QAEntry, float]]:
        if not self.entries:
            return None

        expected_norm = (expected_type or "").lower()
        best: Optional[Tuple[QAEntry, float]] = None
        q_tokens = set(_tokenize(query))
        for e in self.entries:
            if expected_norm and e.query_type and e.query_type != expected_norm:
                # Keep only matching type when explicit type provided
                continue
            score = _overlap_score(query, e.question)
            if best is None or score > best[1]:
                best = (e, score)

        # Heuristic threshold: require at least modest token overlap
        # Conservative initial threshold to reduce false positives
        if best and best[1] >= 0.35:
            return best
        # Anchor-based acceptance to catch key clinical topics
        if best:
            e, score = best
            e_tokens = set(_tokenize(e.question))
            if q_tokens & e_tokens & ANCHOR_TERMS:
                return best
        return None



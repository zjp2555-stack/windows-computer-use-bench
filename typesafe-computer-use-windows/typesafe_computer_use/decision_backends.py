"""Pluggable decision-model backends behind the one `system_one` surface the loop consumes.

`build_decision_client()` returns whichever backend `DECISION_BACKEND` names (default
siliconflow). Adding a backend is one class plus one `@register_backend` line — the loop,
`decide`, and `actions` never change. Every backend is a context manager exposing:

    system_one(*, state, questions) -> object with `.answers: dict[str, answer]`

where a choice answer carries `.choice` (a criteria key), `.confidence`, and
`.probabilities`, and a Noul answer carries `.noul` in [0, 1]. The tests' fake clients
and the typesafe-sdk client both already speak this shape.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field

from .cn_http import post_json

SILICONFLOW_URL = "https://api.siliconflow.cn/v1/systemone"
SILICONFLOW_MODEL = "diffusiongemma"
# Smoke-bisected on 2026-09-27: the endpoint accepts at most 26 criteria per Choice (27+ → HTTP 400 20015),
# independent of description length, and rejects a single criterion too. The perception budget
# (config.max_options) keeps real questions under this; the guard here fails loudly otherwise.
CHOICE_LIMIT = 26
_NOUL_CRITERIA = {
    "true": "Yes — the condition asked about in the instructions holds.",
    "false": "No — it does not hold.",
}


@dataclass(frozen=True)
class Answer:
    """One backend answer. `noul` is set only for Noul questions."""

    choice: str = ""
    confidence: float = 1.0
    probabilities: dict = field(default_factory=dict)
    noul: float | None = None
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SystemOneResponse:
    answers: dict
    model: str | None = None
    raw: dict = field(default_factory=dict)
    # Set when a multi-question request failed and the answers were re-asked one by one.
    fallback_reason: str | None = None


def _question_wire(question) -> tuple[dict, bool]:
    """(wire dict, is_noul) for an SDK Choice/Noul object or a raw dict."""
    if isinstance(question, dict):
        wire = dict(question)
    else:
        wire = {
            "instructions": getattr(question, "instructions", None),
            "criteria": getattr(question, "criteria", None),
        }
        if type(question).__name__ == "Noul":
            wire["type"] = "noul"
        else:
            wire.setdefault("type", "choice")
    is_noul = wire.get("type") == "noul"
    return wire, is_noul


def _key_for_value(value: str, criteria: dict) -> str:
    """Criteria keys are what the loop dispatches on; a model that echoed the label is mapped back."""
    if value in criteria:
        return value
    for key, description in criteria.items():
        if description == value:
            return key
    return value


def _normalize_probabilities(probabilities: dict, criteria: dict) -> dict:
    if not isinstance(probabilities, dict):
        return {}
    return {_key_for_value(str(key), criteria): value for key, value in probabilities.items()}


class SiliconFlowClient:
    """The SiliconFlow SystemOne endpoint (diffusiongemma), tolerant of Alpha-era schema drift.

    Choice answers may arrive without `confidence` (treated as 1.0), and the Noul primitive
    is not verified on this endpoint, so Noul questions are asked as a true/false Choice and
    mapped back to a [0, 1] float. A multi-question request is tried once as a batch; if it
    fails, or comes back with keys missing, the questions are re-asked one at a time.
    """

    def __init__(self, api_key: str, model: str = SILICONFLOW_MODEL, base_url: str | None = None, timeout: float = 30.0):
        if not api_key:
            raise RuntimeError("SILICONFLOW_API_KEY is not set (export it or put it in .env)")
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or os.environ.get("SILICONFLOW_BASE_URL") or SILICONFLOW_URL).rstrip("/")
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def system_one(self, *, state, questions, model=None, timeout=None, retry=None, extra_headers=None, extra_body=None):
        wires: dict[str, dict] = {}
        criteria_by_key: dict[str, dict] = {}
        noul_keys: set[str] = set()
        for key, question in questions.items():
            wire, is_noul = _question_wire(question)
            if is_noul:
                noul_keys.add(key)
                wire = {"type": "choice", "instructions": wire.get("instructions"), "criteria": dict(_NOUL_CRITERIA)}
            criteria = wire.get("criteria") or {}
            if len(criteria) > CHOICE_LIMIT:
                raise ValueError(f"question {key!r} has {len(criteria)} options, over the {CHOICE_LIMIT} ceiling")
            wires[key] = wire
            criteria_by_key[key] = criteria

        # the endpoint rejects a Choice with a single criterion (smoke-verified, HTTP 400 20015);
        # a one-option question is not a decision, so answer it locally without a round trip
        forced: dict[str, Answer] = {}
        for key in list(wires):
            if key in noul_keys:
                continue
            criteria = criteria_by_key[key]
            if len(criteria) == 1:
                only = next(iter(criteria))
                forced[key] = Answer(
                    choice=only, confidence=1.0, probabilities={only: 1.0}, raw={"forced": "single-option question"}
                )
                del wires[key]

        answers: dict[str, Answer] = dict(forced)
        if not wires:
            return SystemOneResponse(answers=answers, model=self.model, raw={"forced": "all questions single-option"})
        try:
            raw = self._request(state, wires, model, timeout)
            merged = {key: self._answer(key, raw, criteria_by_key, noul_keys) for key in wires}
            todo = [key for key in wires if key not in (raw.get("answers") or {})]
            if not todo:
                return SystemOneResponse(answers={**answers, **merged}, model=raw.get("model"), raw=raw)
            reason = f"batch response lacked {todo}"
            raws = [raw]
        except Exception as batch_error:  # any batch failure degrades to per-question asks
            reason = f"batch request failed ({batch_error})"
            todo = list(wires)
            merged = {}
            raws = []

        for key in todo:
            raw = self._request(state, {key: wires[key]}, model, timeout)
            raws.append(raw)
            merged[key] = self._answer(key, raw, criteria_by_key, noul_keys)
        return SystemOneResponse(
            answers={**answers, **merged}, model=raws[0].get("model"), raw={"per_question": raws}, fallback_reason=reason
        )

    def _request(self, state, questions: dict, model: str | None, timeout: float | None) -> dict:
        if not isinstance(state, str):
            # the endpoint reads state as text (smoke-verified): keep a dict state's structure as JSON
            state = json.dumps(state, ensure_ascii=False)
        payload = {"model": model or self.model, "state": state, "questions": questions}
        return post_json(
            self.base_url,
            {"Authorization": f"Bearer {self.api_key}"},
            payload,
            timeout=timeout or self.timeout,
        )

    def _answer(self, key: str, raw: dict, criteria_by_key: dict, noul_keys: set[str]) -> Answer:
        criteria = criteria_by_key[key]
        raw_answer = (raw.get("answers") or {}).get(key) or {}
        confidence = raw_answer.get("confidence")
        probabilities = _normalize_probabilities(raw_answer.get("probabilities") or {}, criteria)
        if raw_answer.get("noul") is not None:  # a native Noul answer, should the endpoint ever send one
            return Answer(
                choice=str(raw_answer.get("choice") or ""),
                confidence=float(confidence or 1.0),
                probabilities=probabilities,
                noul=float(raw_answer["noul"]),
                raw=raw_answer,
            )
        choice = _key_for_value(str(raw_answer.get("choice") or ""), criteria)
        if key in noul_keys:  # the Noul question was asked as a true/false Choice
            if choice in ("true", "yes"):
                noul = 1.0
            elif choice in ("false", "no"):
                noul = 0.0
            else:
                noul = float(probabilities.get("true", 0.0))
            return Answer(
                choice=choice,
                confidence=float(confidence) if confidence is not None else 1.0,
                probabilities=probabilities,
                noul=noul,
                raw=raw_answer,
            )
        return Answer(
            choice=choice,
            # Alpha may omit confidence on choice answers; treat silence as confident so the
            # run's min-confidence gate does not stop on every step (jcu M1 finding, 2026-09).
            confidence=float(confidence) if confidence is not None else 1.0,
            probabilities=probabilities,
            raw=raw_answer,
        )


_BACKENDS: dict[str, Callable[[], object]] = {}


def register_backend(name: str):
    """Add a backend: decorate a zero-arg factory, then select it with DECISION_BACKEND=<name>."""

    def decorator(factory: Callable[[], object]):
        _BACKENDS[name] = factory
        return factory

    return decorator


@register_backend("siliconflow")
def _siliconflow() -> SiliconFlowClient:
    return SiliconFlowClient(
        api_key=os.environ.get("SILICONFLOW_API_KEY") or "",
        model=os.environ.get("SILICONFLOW_MODEL") or SILICONFLOW_MODEL,
        timeout=float(os.environ.get("SILICONFLOW_TIMEOUT") or 30.0),
    )


@register_backend("typesafe")
def _typesafe():
    from typesafe_sdk import TypeSafeClient

    return TypeSafeClient(
        base_url=os.environ.get("TYPESAFE_BASE_URL"),
        model=os.environ.get("TYPESAFE_DEFAULT_MODEL"),
        timeout=float(os.environ.get("TYPESAFE_TIMEOUT") or 20.0),
    )


def build_decision_client(timeout: float = 30.0):
    """The backend named by DECISION_BACKEND (default siliconflow), as a context manager."""
    name = (os.environ.get("DECISION_BACKEND") or "siliconflow").strip().lower()
    factory = _BACKENDS.get(name)
    if factory is None:
        raise RuntimeError(f"unknown DECISION_BACKEND {name!r}; available: {', '.join(sorted(_BACKENDS))}")
    client = factory()
    # the caller's timeout applies unless the backend already got an explicit one from its env var
    if timeout and isinstance(client, SiliconFlowClient) and not os.environ.get("SILICONFLOW_TIMEOUT"):
        client.timeout = timeout
    return client

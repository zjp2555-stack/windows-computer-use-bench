"""Tests for the pluggable decision backends and their Alpha-era tolerances."""

import pytest
from typesafe_sdk import Choice, Noul

from typesafe_computer_use.decision_backends import SiliconFlowClient, build_decision_client


def make_client(monkeypatch, responses) -> SiliconFlowClient:
    """A client whose HTTP layer replays the given raw response dicts, one per request."""
    client = SiliconFlowClient(api_key="u" * 24)
    queue = list(responses)
    calls: list[dict] = []

    def fake_request(state, questions, model, timeout):
        calls.append({"state": state, "questions": questions})
        return queue.pop(0)

    monkeypatch.setattr(client, "_request", fake_request)
    client.calls = calls
    return client


def test_choice_answer_maps_a_label_back_to_its_criteria_key(monkeypatch):
    client = make_client(
        monkeypatch,
        [
            {
                "answers": {
                    "next_action": {"type": "choice", "choice": "点击确定", "confidence": 0.7, "probabilities": {"点击确定": 0.7}}
                }
            }
        ],
    )

    response = client.system_one(
        state="s", questions={"next_action": Choice(instructions="i", criteria={"o0": "点击确定", "o1": "取消"})}
    )

    answer = response.answers["next_action"]
    assert answer.choice == "o0"
    assert answer.confidence == 0.7
    assert answer.probabilities == {"o0": 0.7}


def test_missing_confidence_is_treated_as_confident(monkeypatch):
    client = make_client(monkeypatch, [{"answers": {"kind": {"type": "choice", "choice": "done"}}}])

    response = client.system_one(
        state="s", questions={"kind": Choice(instructions="i", criteria={"done": "The goal is already achieved."})}
    )

    assert response.answers["kind"].confidence == 1.0


def test_a_noul_question_is_asked_as_a_true_false_choice_and_read_back(monkeypatch):
    client = make_client(
        monkeypatch,
        [
            {
                "answers": {
                    "ok": {"type": "choice", "choice": "true", "confidence": 0.6, "probabilities": {"true": 0.6, "false": 0.4}}
                }
            }
        ],
    )

    response = client.system_one(state="s", questions={"ok": Noul(instructions="Did the typing succeed?")})

    answer = response.answers["ok"]
    assert answer.noul == 1.0
    wire = client.calls[0]["questions"]["ok"]
    assert wire["type"] == "choice" and set(wire["criteria"]) == {"true", "false"}


def test_a_noul_question_answered_false_reads_as_zero(monkeypatch):
    client = make_client(monkeypatch, [{"answers": {"ok": {"type": "choice", "choice": "false"}}}])

    response = client.system_one(state="s", questions={"ok": Noul(instructions="Did the typing succeed?")})

    assert response.answers["ok"].noul == 0.0


def test_a_failed_multi_question_batch_is_re_asked_one_question_at_a_time(monkeypatch):
    client = make_client(
        monkeypatch,
        [
            RuntimeError("HTTP 503"),  # the batch ask fails
            {"answers": {"kind": {"type": "choice", "choice": "done", "confidence": 0.8}}},
            {"answers": {"site": {"type": "choice", "choice": "none", "confidence": 0.9}}},
        ],
    )

    response = client.system_one(
        state="s",
        questions={
            "kind": Choice(instructions="i", criteria={"done": "The goal is already achieved.", "none": "Nothing helps."}),
            "site": Choice(instructions="i", criteria={"none": "Stay on the open page.", "other": "A different site."}),
        },
    )

    assert response.fallback_reason and "batch" in response.fallback_reason
    assert response.answers["kind"].choice == "done"
    assert response.answers["site"].choice == "none"
    assert [len(call["questions"]) for call in client.calls] == [2, 1, 1]


def test_a_batch_response_missing_one_key_refills_just_that_key(monkeypatch):
    client = make_client(
        monkeypatch,
        [
            {"answers": {"kind": {"type": "choice", "choice": "done", "confidence": 0.8}}},  # site missing
            {"answers": {"site": {"type": "choice", "choice": "none", "confidence": 0.9}}},
        ],
    )

    response = client.system_one(
        state="s",
        questions={
            "kind": Choice(instructions="i", criteria={"done": "The goal is already achieved.", "none": "Nothing helps."}),
            "site": Choice(instructions="i", criteria={"none": "Stay on the open page.", "other": "A different site."}),
        },
    )

    assert response.fallback_reason and "lacked ['site']" in response.fallback_reason
    assert response.answers["kind"].confidence == 0.8
    assert response.answers["site"].choice == "none"
    assert [len(call["questions"]) for call in client.calls] == [2, 1]


def test_a_single_option_choice_is_answered_without_a_request(monkeypatch):
    client = SiliconFlowClient(api_key="u" * 24)
    monkeypatch.setattr(client, "_request", lambda *a, **k: pytest.fail("network hit for a single-option question"))

    response = client.system_one(state="s", questions={"item": Choice(instructions="i", criteria={"7": "the only button"})})

    assert response.answers["item"].choice == "7"
    assert response.answers["item"].confidence == 1.0


def test_single_option_questions_are_dropped_from_the_wire_request(monkeypatch):
    client = SiliconFlowClient(api_key="u" * 24)

    def fake_request(state, questions, model, timeout):
        assert set(questions) == {"kind"}, f"the single-option question leaked onto the wire: {set(questions)}"
        return {"answers": {"kind": {"type": "choice", "choice": "done", "confidence": 0.9}}}

    monkeypatch.setattr(client, "_request", fake_request)

    response = client.system_one(
        state="s",
        questions={
            "kind": Choice(instructions="i", criteria={"done": "achieved", "none": "nothing helps"}),
            "item": Choice(instructions="i", criteria={"7": "the only button"}),
        },
    )

    assert response.fallback_reason is None
    assert response.answers["kind"].choice == "done"
    assert response.answers["item"].choice == "7"


def test_the_factory_builds_the_backend_named_by_the_environment(monkeypatch):
    monkeypatch.setenv("SILICONFLOW_API_KEY", "u" * 24)
    monkeypatch.delenv("DECISION_BACKEND", raising=False)

    assert isinstance(build_decision_client(), SiliconFlowClient)

    monkeypatch.setenv("DECISION_BACKEND", "nonsense")
    with pytest.raises(RuntimeError, match="unknown DECISION_BACKEND"):
        build_decision_client()

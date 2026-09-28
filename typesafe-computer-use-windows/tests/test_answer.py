import base64
import io
import json
from types import SimpleNamespace

import pytest
from PIL import Image

from typesafe_computer_use import runner, writer, zhipu_writer
from typesafe_computer_use.actions import Context
from typesafe_computer_use.runner import RunConfig, RunState, conclude, resolve
from typesafe_computer_use.writer import Answer, compose_answer
from typesafe_computer_use.zhipu_writer import ANSWER_IMAGE_EDGE, ZhipuWriter

GOAL = "find the next upcoming bruno mars concert"


class FakeWriter:
    """Stands in for a structured writer backend: records each ask and replies with the canned dict."""

    def __init__(self, reply: dict):
        self.requests: list[dict] = []
        self._reply = reply

    def structured(self, system, packet, properties, image=None, **unused):
        self.requests.append({"system": system, "packet": packet, "properties": properties, "image": image})
        return self._reply


def glm_writer(monkeypatch, reply: dict, calls: list) -> ZhipuWriter:
    """A ZhipuWriter whose HTTP layer is replaced: records each payload, replies once."""

    def fake_post(url, headers, payload, timeout=60.0, retries=2):
        calls.append((url, payload))
        return {"choices": [{"message": {"content": json.dumps(reply)}}]}

    # a throwaway env key, composed rather than written out, so no credential-looking literal lands in the file
    monkeypatch.setenv("ZHIPU_API_KEY", "u" * 24)
    monkeypatch.setattr(zhipu_writer, "post_json", fake_post)
    return ZhipuWriter()


def packet_of(prompt: str) -> dict:
    """The DATA block embedded in the zhipu prompt."""
    return json.loads(prompt.split("DATA:\n", 1)[1].split("\n\nReply with ONLY", 1)[0])


def context(writer=None) -> Context:
    return Context(goal=GOAL, browser="Google Chrome", email=None, typesafe=None, writer=writer, history=[])


def logged() -> tuple[list[str], runner.Log]:
    lines: list[str] = []
    return lines, lines.append


def test_the_answer_request_carries_the_capture_and_the_run(screen, make_item, monkeypatch):
    monkeypatch.setenv("CLICKER_ANSWER_MODEL", "answer-model")
    calls: list = []
    wr = glm_writer(monkeypatch, {"achieved": True, "answer": " Sep 19, 2026 in Miami. "}, calls)

    answer = compose_answer(wr, GOAL, screen, [make_item(0, "SEP 19, 2026")], ["clicked 'TOUR'"], "the goal is achieved")

    assert answer == Answer(text="Sep 19, 2026 in Miami.", achieved=True)
    url, request = calls[0]
    assert url.endswith("/chat/completions") and request["model"] == "answer-model"
    image, text_block = request["messages"][0]["content"]
    assert image["type"] == "image_url" and image["image_url"]["url"].startswith("data:image/png;base64,")
    packet = packet_of(text_block["text"])
    assert packet["goal"] == GOAL
    assert packet["why_the_run_stopped"] == "the goal is achieved"
    assert packet["actions_taken"] == ["clicked 'TOUR'"]
    assert packet["screen_text_in_reading_order"] == ["SEP 19, 2026"]


def test_the_capture_is_shrunk_to_the_edge_the_model_reads_and_left_intact():
    capture = Image.new("RGBA", (3456, 2234))

    url = zhipu_writer._image_data_url(capture)

    sent = Image.open(io.BytesIO(base64.b64decode(url.removeprefix("data:image/png;base64,"))))
    assert sent.format == "PNG"
    assert max(sent.size) == ANSWER_IMAGE_EDGE
    assert capture.size == (3456, 2234)


def test_requests_without_a_capture_stay_text_only_on_the_writer_model(monkeypatch):
    monkeypatch.setenv("CLICKER_WRITER_MODEL", "writer-model")
    calls: list = []
    wr = glm_writer(monkeypatch, {"ok": True, "url": "https://www.brunomars.com"}, calls)

    assert writer.compose_url(wr, GOAL, []) == "https://www.brunomars.com"

    _, request = calls[0]
    assert request["model"] == "writer-model"
    assert [block["type"] for block in request["messages"][0]["content"]] == ["text"]


@pytest.mark.parametrize("outcome", ["dry run", "aborted (Ctrl-C)", "crashed"])
def test_a_run_that_has_nothing_to_report_asks_for_no_answer(outcome, tmp_path, screen):
    fake = FakeWriter({"achieved": True, "answer": "unused"})
    state = RunState(outcome=outcome, view=(screen, []))
    lines, log = logged()

    conclude(RunConfig(goal=GOAL, out=tmp_path), context(fake), state, log)

    assert state.answer is None and not fake.requests and not lines


def test_without_a_writer_the_run_says_why_there_is_no_answer(tmp_path, screen):
    state = RunState(outcome="done", view=(screen, []))
    lines, log = logged()

    conclude(RunConfig(goal=GOAL, out=tmp_path), context(), state, log)

    assert state.answer is None
    assert "no answer" in lines[0] and "ZHIPU_API_KEY" in lines[0]


def test_the_last_capture_is_answered_from_when_nothing_acted_after_it(tmp_path, screen, make_item, monkeypatch):
    monkeypatch.setattr(runner, "capture", lambda *a, **k: pytest.fail("captured again"))
    fake = FakeWriter({"achieved": True, "answer": "Sep 19, 2026 in Miami."})
    state = RunState(outcome="done", view=(screen, [make_item(0, "SEP 19, 2026")]))
    lines, log = logged()

    conclude(RunConfig(goal=GOAL, out=tmp_path), context(fake), state, log)

    assert state.answer == Answer(text="Sep 19, 2026 in Miami.", achieved=True)
    assert "goal achieved" in lines[0] and "Sep 19, 2026 in Miami." in lines[0]
    assert not (tmp_path / "answer-raw.png").exists()
    assert "already achieved" in fake.requests[0]["packet"]["why_the_run_stopped"]


def test_the_screen_is_captured_again_when_an_action_made_the_last_capture_stale(tmp_path, screen, make_item, monkeypatch):
    monkeypatch.setattr(runner.macos, "check_abort", lambda: None)
    monkeypatch.setattr(runner, "capture", lambda *a, **k: screen)
    monkeypatch.setattr(runner, "perceive", lambda *a, **k: [make_item(0, "TICKETS")])
    fake = FakeWriter({"achieved": False, "answer": "No dates on screen."})
    state = RunState(outcome="step limit", view=None)
    lines, log = logged()

    conclude(RunConfig(goal=GOAL, out=tmp_path), context(fake), state, log)

    assert state.answer == Answer(text="No dates on screen.", achieved=False)
    assert "goal not achieved" in lines[0]
    assert (tmp_path / "answer-raw.png").exists()
    assert fake.requests[0]["packet"]["screen_text_in_reading_order"] == ["TICKETS"]


def test_a_writer_that_fails_costs_the_answer_and_not_the_run(tmp_path, screen):
    class RefusingWriter:
        def structured(self, **request):
            raise writer.WriterError("connection refused")

    state = RunState(outcome="done", view=(screen, []))
    lines, log = logged()

    conclude(RunConfig(goal=GOAL, out=tmp_path), context(RefusingWriter()), state, log)

    assert state.answer is None
    assert "no answer: the writer failed" in lines[0]


def decision(kind: str, confidence: float = 0.9) -> SimpleNamespace:
    return SimpleNamespace(kind=SimpleNamespace(choice=kind), stops=kind in ("done", "none"), confidence=confidence, chosen=kind)


@pytest.mark.parametrize(
    ("kind", "confidence", "outcome"),
    [
        ("done", 0.9, "done"),
        ("none", 0.9, "nothing helps"),
        ("scroll_down", 0.2, "low confidence"),
        ("scroll_down", 0.9, "dry run"),
    ],
)
def test_every_stop_names_its_outcome(kind, confidence, outcome, tmp_path, screen):
    state = RunState()
    _, log = logged()

    keep_going = resolve(RunConfig(goal=GOAL, out=tmp_path), context(), state, screen, [], decision(kind, confidence), {}, log)

    assert not keep_going
    assert state.outcome == outcome
    assert (outcome in runner.STOPPED) == (outcome != "dry run")


def test_an_action_makes_the_last_capture_stale(tmp_path, screen, monkeypatch):
    monkeypatch.setattr(runner, "perform", lambda *a: "scrolled down")
    state = RunState(view=(screen, []))
    _, log = logged()

    keep_going = resolve(
        RunConfig(goal=GOAL, out=tmp_path, act=True), context(), state, screen, [], decision("scroll_down"), {}, log
    )

    assert keep_going
    assert state.view is None


def test_repeated_scrolls_can_continue_through_a_long_list(tmp_path, screen, monkeypatch):
    monkeypatch.setattr(runner, "perform", lambda *a: "scrolled down")
    state = RunState()
    _, log = logged()
    cfg = RunConfig(goal=GOAL, out=tmp_path, act=True)

    for _ in range(4):
        assert resolve(cfg, context(), state, screen, [], decision("scroll_down"), {}, log)

    assert state.consecutive_noops == 0

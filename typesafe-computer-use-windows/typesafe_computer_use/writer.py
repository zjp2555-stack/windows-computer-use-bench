"""The writer model: the only place free text is generated, when the classifier asks for it and once when the run ends.

Backends are the MCP host (HostWriter, free text and the final answer come back from the agent
that owns the run) and the GLM writer (Zhipu open platform). There is no Anthropic path.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from .dates import now_context
from .models import Item, Screen
from .perception import near_field

if TYPE_CHECKING:
    from PIL import Image

    from .host_writer import HostWriter
    from .zhipu_writer import ZhipuWriter


class WriterError(RuntimeError):
    """A writer backend failed; the run continues without the free text."""


def make_writer() -> HostWriter | ZhipuWriter | None:
    """A writer, or None when no backend is available (the MCP host path needs no credentials)."""
    if os.environ.get("CLICKER_HOST_DIR"):
        from .host_writer import HostWriter

        return HostWriter(os.environ["CLICKER_HOST_DIR"])
    if not os.environ.get("ZHIPU_API_KEY"):
        return None
    from .zhipu_writer import ZhipuWriter

    return ZhipuWriter()


def _structured(
    writer: HostWriter | ZhipuWriter,
    system: str,
    packet: dict,
    properties: dict,
    max_tokens: int,
    model: str | None = None,
    image: Image.Image | None = None,
) -> dict:
    if hasattr(writer, "structured"):
        return writer.structured(system=system, packet=packet, properties=properties, image=image)
    raise WriterError("the writer backend does not support structured output")


def compose_text(writer: HostWriter | ZhipuWriter, goal: str, screen: Screen, items: list[Item], history: list[str]) -> str:
    """The exact string to type into the focused field. Empty means the writer declined."""
    packet = {
        "goal": goal,
        "now": now_context(),
        "frontmost_app": screen.app,
        "previous_actions": history[-8:],
        "focused_field": screen.field.summary() if screen.field else None,
        "text_near_field": near_field(screen, items),
        "all_screen_text": [it.text for it in items][:120],
    }
    data = _structured(
        writer,
        system=(
            "You fill in one text field on a user's screen. You receive the user's goal, recent "
            "actions, the focused field's label and placeholder, and nearby screen text. Decide the "
            "exact string to type. Never invent credentials, passwords, or personal data; for such "
            "fields, or when the field should not be filled, set fill to false."
        ),
        packet=packet,
        properties={"fill": {"type": "boolean"}, "text": {"type": "string"}, "reason": {"type": "string"}},
        max_tokens=256,
    )
    return data["text"].strip() if data["fill"] else ""


def valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and "." in parsed.netloc and not any(ch.isspace() for ch in url)


def compose_url(writer: HostWriter | ZhipuWriter, goal: str, history: list[str]) -> str:
    """The URL to open for this goal. Empty means no sensible site, or an invalid proposal."""
    data = _structured(
        writer,
        system=(
            "Given a user's goal for their web browser, give the single best https URL to open first. "
            "Prefer the site's homepage or the most direct public page. If no website is implied, set ok to false."
        ),
        packet={"goal": goal, "now": now_context(), "previous_actions": history[-8:]},
        properties={"ok": {"type": "boolean"}, "url": {"type": "string"}, "reason": {"type": "string"}},
        max_tokens=200,
    )
    url = data["url"].strip() if data["ok"] else ""
    return url if valid_url(url) else ""


@dataclass(frozen=True)
class Answer:
    text: str
    achieved: bool  # whether the screen itself shows the goal reached, in the writer's judgement


def compose_answer(
    writer: HostWriter | ZhipuWriter, goal: str, screen: Screen, items: list[Item], history: list[str], stopped: str
) -> Answer:
    """What to tell the user now that the run is over: the result when the screen holds it, where things stand when not.

    The classifier can stop on the right page but cannot say what the page says. The writer reads the
    capture itself as well as its text, since OCR misreads a letter here and there and drops layout.
    """
    packet = {
        "goal": goal,
        "now": now_context(),
        "why_the_run_stopped": stopped,
        "actions_taken": history,
        "frontmost_app": screen.app,
        "browser_active_tab_url": screen.url,
        "screen_text_in_reading_order": [it.text for it in items],
    }
    data = _structured(
        writer,
        system=(
            "An agent drove a user's computer toward the user's goal and has now stopped. You receive "
            "the goal, the actions it took, why it stopped, a capture of the screen as it is now, and "
            "the text read from that screen. Tell the user the result. When the goal asks for "
            "information, lead with that information, taken only from the screen: never from memory, "
            "and never a guess. When the goal asks for something to be done, say whether the screen "
            "shows it done. When the screen does not hold the result, say so plainly, then say what is "
            "on screen and the one next step that would get there. Trust the capture over the text "
            "where the two disagree. Plain text, no markdown, four sentences at most. Set achieved to "
            "true only when the screen itself shows the goal reached."
        ),
        packet=packet,
        properties={"achieved": {"type": "boolean"}, "answer": {"type": "string"}},
        max_tokens=1024,
        image=screen.image,
    )
    return Answer(text=data["answer"].strip(), achieved=data["achieved"])

"""The GLM writer backend (Zhipu open platform): the domestic replacement for the Anthropic writer.

Exposes the same `structured(system, packet, properties, image)` surface as HostWriter, so
`writer.compose_text` / `compose_url` / `compose_answer` work unchanged. Text-only asks run on
the writer model; asks that carry a screenshot run on the vision answer model.
"""

from __future__ import annotations

import base64
import io
import json
import os

from PIL import Image

from .cn_http import post_json
from .config import answer_model, writer_model
from .writer import WriterError

ANSWER_IMAGE_EDGE = 1568  # the longest edge a vision model reads without shrinking the image itself


def _image_data_url(image: Image.Image) -> str:
    """The capture as a base64 PNG data URL. PNG because screen text does not survive JPEG well."""
    shrunk = image.convert("RGB")
    shrunk.thumbnail((ANSWER_IMAGE_EDGE, ANSWER_IMAGE_EDGE))
    buffer = io.BytesIO()
    shrunk.save(buffer, format="PNG")
    data = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{data}"


def _prompt(system: str, packet: dict, properties: dict) -> str:
    schema = {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}
    return (
        f"{system}\n\nDATA:\n{json.dumps(packet, ensure_ascii=False)}\n\n"
        f"Reply with ONLY one JSON object with exactly these keys: {list(properties)}.\n"
        f"JSON schema: {json.dumps(schema)}"
    )


def _extract_json(text: str) -> dict:
    """Some models wrap JSON in prose or fences despite instructions; take the outermost object."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise WriterError(f"GLM reply is not JSON: {text[:200]}")
    return json.loads(text[start : end + 1])


class ZhipuWriter:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or os.environ.get("ZHIPU_API_KEY") or ""
        self.base_url = (base_url or os.environ.get("ZHIPU_BASE_URL") or "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
        if not self.api_key:
            raise RuntimeError("ZHIPU_API_KEY is not set (export it or put it in .env)")

    def structured(self, system, packet, properties, image=None, **unused) -> dict:
        content: list[dict] = []
        if image is not None:  # the capture first, matching the upstream request shape
            content.append({"type": "image_url", "image_url": {"url": _image_data_url(image)}})
        content.append({"type": "text", "text": _prompt(system, packet, properties)})
        if image is not None:
            model = os.environ.get("ZHIPU_VISION_MODEL") or answer_model()
        else:
            model = os.environ.get("ZHIPU_MODEL") or writer_model()
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        data = post_json(
            f"{self.base_url}/chat/completions",
            {"Authorization": f"Bearer {self.api_key}"},
            payload,
            timeout=120.0,
        )
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise WriterError(f"unexpected GLM response shape: {json.dumps(data)[:300]}") from exc
        try:
            reply = json.loads(text)
        except (TypeError, json.JSONDecodeError):
            reply = _extract_json(text)
        if not isinstance(reply, dict):
            raise WriterError(f"GLM reply is not a JSON object: {str(text)[:200]}")
        for key, spec in properties.items():
            # json_object mode does not enforce the schema; a missing boolean reads as "declined"
            # and a missing string as empty, the safe direction for every compose caller.
            if key not in reply:
                reply[key] = False if spec.get("type") == "boolean" else ""
        return reply

"""Windows' local OCR behind the ocrmac interface used by the upstream cache."""

from __future__ import annotations

import asyncio
from functools import lru_cache

from winrt.windows.graphics.imaging import BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.storage.streams import DataWriter


@lru_cache(maxsize=1)
def engine():
    result = OcrEngine.try_create_from_user_profile_languages()
    if result is None:
        languages = list(OcrEngine.available_recognizer_languages)
        if languages:
            result = OcrEngine.try_create_from_language(languages[0])
    if result is None:
        raise RuntimeError("Windows OCR language is unavailable. Install an OCR language in Windows Settings.")
    return result


class OCR:
    def __init__(self, image, recognition_level="accurate"):
        self.image = image

    def recognize(self, px=True):
        if not px:
            raise ValueError("This adapter returns pixel boxes only.")
        return asyncio.run(self._recognize())

    async def _recognize(self):
        image = self.image.convert("RGBA")
        ratio = min(1.0, OcrEngine.max_image_dimension / max(image.size))
        if ratio < 1:
            image = image.resize((max(1, round(image.width * ratio)), max(1, round(image.height * ratio))))
        writer = DataWriter()
        writer.write_bytes(image.tobytes("raw", "BGRA"))
        bitmap = SoftwareBitmap(BitmapPixelFormat.BGRA8, image.width, image.height, BitmapAlphaMode.IGNORE)
        bitmap.copy_from_buffer(writer.detach_buffer())
        try:
            result = await engine().recognize_async(bitmap)
            lines = []
            for line in result.lines:
                boxes = [w.bounding_rect for w in line.words]
                if not boxes:
                    continue
                box = (
                    min(b.x for b in boxes),
                    min(b.y for b in boxes),
                    max(b.x + b.width for b in boxes),
                    max(b.y + b.height for b in boxes),
                )
                # Windows OCR does not expose confidence; 1.0 means accepted text, not a calibrated score.
                lines.append((line.text, 1.0, tuple(v / ratio for v in box)))
            return lines
        finally:
            bitmap.close()
            writer.close()

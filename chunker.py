from __future__ import annotations

import math
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    content: str
    token_count: int


def chunk_text(text: str, *, max_chars: int = 800, min_chars: int = 50) -> list[Chunk]:
    parts = [p.strip() for p in re.split(r"\n\s*\n+", text or "") if p.strip()]
    chunks: list[str] = []
    for part in parts:
        if len(part) <= max_chars:
            chunks.append(part)
            continue
        buf = ""
        for sent in re.split(r"(?<=[.!?])|(?<=[\u3002\uff01\uff1f])", part):
            sent = sent.strip()
            if not sent:
                continue
            if buf and len(buf) + len(sent) > max_chars:
                chunks.append(buf.strip())
                buf = sent
            else:
                buf = (buf + sent).strip()
        if buf:
            chunks.append(buf.strip())

    merged: list[str] = []
    for chunk in chunks:
        if merged and len(chunk) < min_chars:
            merged[-1] = f"{merged[-1]}\n{chunk}".strip()
        else:
            merged.append(chunk)
    return [Chunk(c, math.ceil(len(c) / 4)) for c in merged if c]

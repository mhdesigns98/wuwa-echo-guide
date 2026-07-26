"""Generate structured meeting notes from a transcript using a local Ollama model.

For long meetings the transcript is split into chunks, each chunk is condensed
(map step), then the condensed notes are merged into one final outline (reduce
step). This keeps everything inside the local model's context window.

Requires a running Ollama server (`ollama serve`) with the configured model
pulled (`ollama pull llama3.1`).
"""

from __future__ import annotations

from typing import List, Optional

import requests

from .config import Config, load_config


class OllamaError(RuntimeError):
    pass


_FINAL_SYSTEM = (
    "You are a meticulous meeting-notes assistant. You turn raw meeting "
    "transcripts into clear, well-structured notes. Be faithful to the "
    "transcript; do not invent facts, names, or decisions. If something is "
    "unclear, say so briefly rather than guessing."
)

_FINAL_INSTRUCTIONS = """\
Produce meeting notes in Markdown with exactly these sections:

## Summary
A 2-4 sentence overview of what the meeting was about and its outcome.

## Key Points
- Bulleted list of the most important topics and information discussed.

## Decisions
- Bulleted list of decisions that were made. Write "None recorded." if there were none.

## Action Items
- Bulleted list of follow-ups. Format each as "- [owner, if named] task". Write "None recorded." if there were none.

## Open Questions
- Bulleted list of unresolved questions or topics needing follow-up. Write "None recorded." if there were none.

Transcript:
---
{content}
---
"""

_MAP_INSTRUCTIONS = """\
The following is one part of a longer meeting transcript. Condense it into terse
bullet points capturing topics discussed, any decisions, and any action items or
follow-ups mentioned. Keep names and specifics. Do not add a preamble.

Transcript part:
---
{content}
---
"""


def _chat(config: Config, system: str, user: str) -> str:
    url = f"{config.ollama_host.rstrip('/')}/api/chat"
    payload = {
        "model": config.ollama_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"num_ctx": config.ollama_num_ctx, "temperature": 0.2},
    }
    try:
        resp = requests.post(url, json=payload, timeout=600)
    except requests.exceptions.ConnectionError as exc:
        raise OllamaError(
            f"Could not reach Ollama at {config.ollama_host}. "
            "Is it running? Try: ollama serve"
        ) from exc
    if resp.status_code == 404:
        raise OllamaError(
            f"Model '{config.ollama_model}' not found in Ollama. "
            f"Pull it with: ollama pull {config.ollama_model}"
        )
    resp.raise_for_status()
    data = resp.json()
    return data.get("message", {}).get("content", "").strip()


def _chunk_text(text: str, size: int) -> List[str]:
    """Split text into ~`size`-char chunks on paragraph/line boundaries."""
    if len(text) <= size:
        return [text]
    chunks: List[str] = []
    current: List[str] = []
    length = 0
    for para in text.split("\n"):
        if length + len(para) + 1 > size and current:
            chunks.append("\n".join(current))
            current, length = [], 0
        current.append(para)
        length += len(para) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks


def summarize(transcript_text: str, config: Optional[Config] = None,
              progress=None) -> str:
    """Return Markdown meeting notes for the given transcript text."""
    config = config or load_config()
    if not transcript_text.strip():
        raise ValueError("Transcript is empty; nothing to summarize.")

    chunks = _chunk_text(transcript_text, config.chunk_char_size)

    if len(chunks) == 1:
        if progress:
            progress("Summarizing transcript…")
        content = chunks[0]
    else:
        # Map step: condense each chunk.
        condensed: List[str] = []
        for i, chunk in enumerate(chunks, 1):
            if progress:
                progress(f"Condensing part {i}/{len(chunks)}…")
            condensed.append(_chat(config, _FINAL_SYSTEM,
                                   _MAP_INSTRUCTIONS.format(content=chunk)))
        content = "\n\n".join(condensed)
        if progress:
            progress("Merging into final notes…")

    return _chat(config, _FINAL_SYSTEM, _FINAL_INSTRUCTIONS.format(content=content))


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Summarize a transcript with Ollama.")
    parser.add_argument("transcript", help="Path to a transcript .txt file")
    parser.add_argument("--model", help="Ollama model override")
    args = parser.parse_args()

    config = load_config()
    if args.model:
        config.ollama_model = args.model

    text = open(args.transcript, encoding="utf-8").read()
    print(summarize(text, config, progress=lambda m: print(m)))


if __name__ == "__main__":
    _main()

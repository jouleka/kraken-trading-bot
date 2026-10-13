"""Load only the unchanged original NLTK VADER lexicon bundled beside this file."""

import hashlib
from pathlib import Path


def load_lexicon(resource):
    if resource != "sentiment/vader_lexicon.zip/vader_lexicon/vader_lexicon.txt":
        raise ValueError("Only the bundled original VADER lexicon is supported")
    payload = Path(__file__).with_name("vader_lexicon.txt").read_bytes()
    if len(payload) != 434147 or hashlib.sha256(payload).hexdigest() != (
        "0aabac74cd95def2dbedc04ce55e39698d91113ffadb6d86b87dd337c4d2184d"
    ):
        raise ValueError("The bundled original VADER lexicon has changed")
    return payload.decode("utf-8")

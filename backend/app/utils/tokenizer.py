import re

def count_tokens(text: str) -> int:
    """
    Fast, deterministic token count estimation using a word-and-punctuation splitter.
    Provides sub-millisecond execution times without heavy external dependencies.
    """
    if not text:
        return 0
    # Match alphanumeric words or single punctuation characters
    tokens = re.findall(r"\w+|[^\w\s]", text, re.UNICODE)
    return max(1, len(tokens))

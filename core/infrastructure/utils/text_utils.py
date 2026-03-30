import re
import random


def parse_spintax(text: str) -> str:
    """
    Parses spintax in the format {option1|option2|option3}.
    Nested spintax is NOT supported in this implementation for simplicity.
    """
    pattern = re.compile(r"\{([^{}]+)\}")

    def replace(match):
        options = match.group(1).split("|")
        return random.choice(options).strip()

    while pattern.search(text):
        text = pattern.sub(replace, text)

    return text


def humanize_greeting(text: str) -> str:
    """
    Prepends a random human-like greeting if detected as empty or very short.
    Or just provides variations of common phrases.
    """
    # This can be expanded later
    return text

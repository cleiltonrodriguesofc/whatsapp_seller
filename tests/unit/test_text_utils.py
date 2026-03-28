from core.infrastructure.utils.text_utils import parse_spintax, humanize_greeting

def test_parse_spintax():
    text = "Hello {world|there}!"
    result = parse_spintax(text)
    assert result in ["Hello world!", "Hello there!"]

def test_parse_spintax_no_options():
    text = "Plain text"
    result = parse_spintax(text)
    assert result == "Plain text"

def test_humanize_greeting():
    text = "Test"
    result = humanize_greeting(text)
    assert result == "Test"

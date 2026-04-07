from core.infrastructure.utils.text_utils import (
    parse_spintax,
    humanize_greeting,
    clean_whatsapp_number,
    parse_contacts_text,
)


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


def test_clean_whatsapp_number():
    assert clean_whatsapp_number("11988887777") == "5511988887777"
    assert clean_whatsapp_number("(11) 98888-7777") == "5511988887777"
    assert clean_whatsapp_number("+55 11 9.8888-7777") == "5511988887777"
    assert clean_whatsapp_number("5511988887777") == "5511988887777"
    assert clean_whatsapp_number("foo bar") == ""


def test_parse_contacts_text():
    # Test typical CSV text
    raw_csv = """
nome,telefone
João, 11988887777
Maria, (21) 9 7777-6666
+5531999995555, Pedro
    """
    contacts = parse_contacts_text(raw_csv)

    assert len(contacts) == 3
    assert contacts[0]["name"] == "João"
    assert contacts[0]["phone"] == "5511988887777"
    assert contacts[1]["name"] == "Maria"
    assert contacts[1]["phone"] == "5521977776666"
    assert contacts[2]["name"] == "Pedro"
    assert contacts[2]["phone"] == "5531999995555"


def test_parse_contacts_weird_spacing():
    # Test weird "copy and paste" formats
    raw_text = "Fulano de Tal - +55 (11) 98888-9999 \n 5521999990000"
    contacts = parse_contacts_text(raw_text)

    assert len(contacts) == 2
    assert contacts[0]["name"] == "Fulano de Tal"
    assert contacts[0]["phone"] == "5511988889999"
    assert contacts[1]["name"] == "5521999990000"  # since no name, sets phone as name
    assert contacts[1]["phone"] == "5521999990000"

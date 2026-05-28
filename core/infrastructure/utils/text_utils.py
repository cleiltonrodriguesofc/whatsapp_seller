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


def clean_whatsapp_number(raw_phone: str) -> str:
    """Removes non-digits and ensures the number has country code 55."""
    clean = re.sub(r"\D", "", raw_phone)
    if not clean:
        return ""
    if len(clean) == 10 or len(clean) == 11:
        return "55" + clean
    if len(clean) >= 12 and clean.startswith("55"):
        return clean
    # Fallback for weird lengths or other country codes
    return clean


def parse_vcard(raw_text: str) -> list:
    """
    Parses vCard (.vcf) format and extracts name + phone for each contact.
    Handles multiple vCards in a single file (exported from iPhone/Android/Google).
    Returns: [{"name": Name, "phone": Phone}]
    """
    contacts = []
    # split by vcard blocks
    blocks = re.split(r"BEGIN:VCARD", raw_text, flags=re.IGNORECASE)
    for block in blocks:
        if not block.strip():
            continue

        # extract full name (FN field)
        name = ""
        fn_match = re.search(r"^FN[;:][^\r\n]*[:\t](.+)$", block, re.MULTILINE | re.IGNORECASE)
        if not fn_match:
            fn_match = re.search(r"^FN:(.+)$", block, re.MULTILINE | re.IGNORECASE)
        if fn_match:
            name = fn_match.group(1).strip()

        # fallback to N field (structured name)
        if not name:
            n_match = re.search(r"^N[;:][^\r\n]*?:(.+)$", block, re.MULTILINE | re.IGNORECASE)
            if n_match:
                parts = n_match.group(1).strip().split(";")
                name = " ".join(p.strip() for p in parts if p.strip())

        # extract phone numbers (TEL field)
        tel_matches = re.findall(
            r"^TEL[^:]*:(.+)$", block, re.MULTILINE | re.IGNORECASE
        )
        for tel in tel_matches:
            phone = clean_whatsapp_number(tel.strip())
            if len(phone) >= 10:
                contacts.append({"name": name or phone, "phone": phone})
                break  # use first valid phone per contact

    # deduplicate
    seen = set()
    unique = []
    for c in contacts:
        if c["phone"] not in seen:
            seen.add(c["phone"])
            unique.append(c)
    return unique


def parse_contacts_text(raw_text: str) -> list:
    """
    Given an arbitrary text (csv, pasted from excel, or vCard .vcf),
    attempts to find names and phones.
    Auto-detects vCard format.
    Returns: [{"name": Name, "phone": Phone}]
    """
    # auto-detect vCard format
    if "BEGIN:VCARD" in raw_text.upper():
        return parse_vcard(raw_text)

    contacts = []
    lines = raw_text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Try to split by comma, semicolon or tab (common in CSV/Excel pastes)
        parts = [p.strip() for p in re.split(r"[,;\t]+", line)]

        name = ""
        phone = ""

        if len(parts) > 1:
            for part in parts:
                clean_num = clean_whatsapp_number(part)
                # If it looks like a brazilian phone (at least 10 digits)
                if len(clean_num) >= 10:
                    phone = clean_num
                elif part and not name and not clean_num:
                    # first non-phone part is the name
                    name = part

        # If no delimiters were caught or it's a single string with both
        if not phone or (phone and not name and len(parts) == 1):
            match = re.search(r"(\+?\d[\d\-\s()]{9,}\d)", line)
            if match:
                phone_candidate = clean_whatsapp_number(match.group(1))
                if len(phone_candidate) >= 10:
                    phone = phone_candidate
                    name = line.replace(match.group(1), "").strip()

        # cleanup leftover commas or weird symbols in name
        name = re.sub(r"^[,;\-\s]+|[,;\-\s]+$", "", name)

        # Ensure we actually have a usable phone
        if phone:
            contacts.append({"name": name or phone, "phone": phone})

    # unique by phone
    unique_contacts = []
    seen = set()
    for c in contacts:
        if c["phone"] not in seen:
            seen.add(c["phone"])
            unique_contacts.append(c)

    return unique_contacts

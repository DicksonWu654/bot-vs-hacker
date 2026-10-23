"""Privacy and wording filters shared by the dataset and site builders.

Apply these to published copies; raw transaction hashes remain available for verification.
"""
import re


EMAIL = re.compile(r"[A-Za-z0-9_.+\-]{1,64}@(?:protonmail\.com|proton\.me|gmail\.com|hotmail\.com|outlook\.com|yahoo\.com|icloud\.com|pm\.me)", re.I)
SALT = ""
CONTACT_HASHES = set()
ENS_HASHES = set()
TOKEN = re.compile(r"(?:https?://)?(?:t\.me|twitter\.com|x\.com)/([A-Za-z0-9_]+)|(?<!\w)@([A-Za-z0-9_]+)\b", re.I)
ENS = re.compile(r"\b[A-Za-z0-9_-]+\.eth\b", re.I)

def digest(token):
    return __import__("hashlib").sha256((SALT + token.lower()).encode()).hexdigest()


def scrub_text(text):
    text = text.replace("[call-level " + "detail of c0ffeebabe.eth transactions is not published]", 'Our call-level comparison for c0ffeebabe.eth transactions is withheld by policy; the public traces can be compared by anyone.')
    if "@" in text:
        text = EMAIL.sub("[email redacted]", text)
    text = TOKEN.sub(lambda m: "[contact redacted]" if digest(m.group(1) or m.group(2)) in CONTACT_HASHES else m.group(0), text)
    text = ENS.sub(lambda m: "[ENS redacted]" if digest(m.group(0)) in ENS_HASHES else m.group(0), text)
    return text


def scrub_public(obj):
    """Scrub prose and plain UTF-8 on-chain messages, including their hex representation."""
    if isinstance(obj, dict):
        return {k: scrub_public(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub_public(v) for v in obj]
    if not isinstance(obj, str):
        return obj
    clean = scrub_text(obj)
    if clean == obj and obj.startswith("0x") and len(obj) > 66 and len(obj) % 2 == 0:
        try:
            message = bytes.fromhex(obj[2:]).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return obj
        # Decode text messages only; ABI-encoded function inputs are outside this filter.
        if message and all(c.isprintable() or c in "\n\r\t" for c in message):
            redacted = scrub_text(message)
            if redacted != message:
                return "0x" + redacted.encode("utf-8").hex()
    return clean

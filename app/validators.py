"""Проверка и нормализация того, что приходит из формы.

Правила намеренно простые и предсказуемые: то, что сервер не может
привести к нормальному виду, он не принимает. Ошибки возвращаются
полями, чтобы интерфейс мог подсветить конкретный input.
"""
import re

NAME_MIN = 2
NAME_MAX = 80
MESSAGE_MAX = 600
CONTACT_MAX = 64

_EMAIL = re.compile(r"^([^\s@]{1,64})@([^\s@]+\.[A-Za-z]{2,24})$")
_DOMAIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$")
_TG = re.compile(r"^@[A-Za-z0-9_]{4,32}$")
_DIGITS = re.compile(r"\D")


def digits(value: str) -> str:
    return _DIGITS.sub("", value or "")


def normalize_phone(value: str) -> str | None:
    """Российский номер приводим к +7XXXXXXXXXX, иностранный — к +<цифры>.

    8XXXXXXXXXX и 9XXXXXXXXX считаем российскими. Длина: 11 цифр для РФ,
    10–15 для остальных.
    """
    raw = digits(value)
    if not raw:
        return None
    if raw[0] == "8":
        raw = "7" + raw[1:]
    elif raw[0] == "9" and len(raw) <= 10:
        raw = "7" + raw
    if raw[0] == "7":
        return "+" + raw if len(raw) == 11 else None
    return "+" + raw if 10 <= len(raw) <= 15 else None


def is_email(value: str) -> bool:
    if not value or len(value) > 254:
        return False
    m = _EMAIL.match(value)
    if not m:
        return False
    local, domain = m.group(1), m.group(2)
    if local.startswith(".") or local.endswith(".") or ".." in local:
        return False
    if ".." in domain:
        return False
    return bool(_DOMAIN.match(domain))


def is_telegram(value: str) -> bool:
    return bool(_TG.match(value or ""))


def detect_contact_type(value: str) -> str:
    v = (value or "").strip()
    if v.startswith("@"):
        return "telegram"
    if "@" in v:
        return "email"
    return "phone"


def clean_text(value: str, limit: int) -> str:
    return re.sub(r"[ \t]+", " ", (value or "").strip())[:limit]


def validate_lead(payload: dict) -> tuple[dict, dict]:
    """Возвращает (чистые данные, ошибки по полям). Пустой dict ошибок = ок."""
    errors: dict[str, str] = {}

    name = clean_text(payload.get("name", ""), NAME_MAX)
    if len(name) < NAME_MIN:
        errors["name"] = "Как к вам обращаться? Минимум два символа."
    elif digits(name) and not re.search(r"[A-Za-zА-Яа-яЁё]", name):
        errors["name"] = "Похоже, это не имя. Напишите, как к вам обращаться."

    raw_contact = clean_text(payload.get("contact", ""), CONTACT_MAX)
    kind = detect_contact_type(raw_contact)
    contact = raw_contact
    if kind == "phone":
        normalized = normalize_phone(raw_contact)
        if not normalized:
            errors["contact"] = "Телефон не разобрать. Нужно 10–15 цифр, например +7 916 123-45-67."
        else:
            contact = normalized
    elif kind == "email":
        contact = raw_contact.lower()
        if not is_email(contact):
            errors["contact"] = "Почта выглядит неверно. Пример: name@example.com."
    else:
        if not is_telegram(raw_contact):
            errors["contact"] = "Ник в Telegram — от 4 до 32 символов: буквы, цифры, подчёркивание."

    message = clean_text(payload.get("message", ""), MESSAGE_MAX)
    source = clean_text(payload.get("utm_source", ""), 64)
    campaign = clean_text(payload.get("utm_campaign", ""), 64)
    variant = (payload.get("variant") or "A").strip().upper()
    if variant not in ("A", "B"):
        variant = "A"

    clean = {
        "name": name,
        "contact_type": kind,
        "contact": contact,
        "message": message,
        "utm_source": source,
        "utm_campaign": campaign,
        "variant": variant,
    }
    return clean, errors

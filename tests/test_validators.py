import pytest

from app.validators import (
    detect_contact_type,
    is_email,
    is_telegram,
    normalize_phone,
    validate_lead,
)


@pytest.mark.parametrize("raw, expected", [
    ("+7 916 123-45-67", "+79161234567"),
    ("8 (916) 123-45-67", "+79161234567"),
    ("9161234567", "+79161234567"),
    ("7-916-123-45-67", "+79161234567"),
    ("+44 20 7946 0958", "+442079460958"),
    ("+971 50 123 4567", "+971501234567"),
])
def test_phone_normalization_ok(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", "12", "91612", "1234", "+7 916 123-45-6", "phone"])
def test_phone_rejects_garbage(raw):
    assert normalize_phone(raw) is None


@pytest.mark.parametrize("value", [
    "ivan@mail.ru", "IVAN.PETROV@MAIL.CO.UK", "ivan+dev@mail.ru",
    "ivan_dev@mail-1.ru", "i@sub.domain.travel",
])
def test_email_valid(value):
    assert is_email(value) is True


@pytest.mark.parametrize("value", [
    "ivan", "ivan@", "ivan@mail", "ivan@mail.c", "ivan@mail.ru.",
    ".ivan@mail.ru", "ivan.@mail.ru", "ivan..petrov@mail.ru",
    "ivan@mail..ru", "ivan@-mail.ru", "ivan@mail-.ru", "ivan petrov@mail.ru",
])
def test_email_invalid(value):
    assert is_email(value) is False


def test_telegram_nick():
    assert is_telegram("@my_nick") is True
    assert is_telegram("@ab") is False
    assert is_telegram("@my nick") is False


def test_contact_type_detection():
    assert detect_contact_type("@nick") == "telegram"
    assert detect_contact_type("ivan@mail.ru") == "email"
    assert detect_contact_type("+7 916 123-45-67") == "phone"


def test_validate_lead_clean_payload():
    clean, errors = validate_lead({
        "name": "  Марина  ", "contact": "8 916 123 45 67",
        "message": "Нужен сайт", "utm_source": "telegram", "variant": "b",
    })
    assert errors == {}
    assert clean["name"] == "Марина"
    assert clean["contact"] == "+79161234567"
    assert clean["contact_type"] == "phone"
    assert clean["variant"] == "B"


def test_validate_lead_errors():
    _, errors = validate_lead({"name": "1", "contact": "abc"})
    assert "name" in errors and "contact" in errors


def test_validate_lead_cuts_long_message():
    clean, errors = validate_lead({"name": "Иван", "contact": "ivan@mail.ru", "message": "я" * 900})
    assert errors == {}
    assert len(clean["message"]) == 600

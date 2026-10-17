"""Гонка при одновременных заявках.

Проверка появилась после нагрузочного теста: 30 одновременных заявок с одним
контактом проходили проверку дубля одновременно, и в базу ложилось до 22
записей вместо одной. Тест воспроизводит это на уровне хранилища.
"""
import threading

import pytest

from app import db


@pytest.fixture()
def tmp_db(tmp_path):
    return str(tmp_path / "race.db")


def _payload(contact: str) -> dict:
    return {
        "name": "Гонка",
        "contact_type": "phone",
        "contact": contact,
        "message": "тест",
        "utm_source": "",
        "utm_campaign": "",
        "variant": "A",
    }


def test_same_contact_concurrent_only_one(tmp_db, monkeypatch):
    monkeypatch.setenv("LEADBOX_DB", tmp_db)
    db.init_db()

    results: list[str] = []
    lock = threading.Lock()

    def worker() -> None:
        try:
            db.create_lead(_payload("+79165550123"), "ip-hash", 1000)
            outcome = "ok"
        except db.DuplicateContact:
            outcome = "dup"
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=worker) for _ in range(30)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count("ok") == 1
    assert results.count("dup") == 29


def test_rate_limit_holds_concurrent(tmp_db, monkeypatch):
    monkeypatch.setenv("LEADBOX_DB", tmp_db)
    db.init_db()

    results: list[str] = []
    lock = threading.Lock()

    def worker(i: int) -> None:
        try:
            db.create_lead(_payload(f"+7916555{i:04d}"), "ip-hash", 5)
            outcome = "ok"
        except db.RateLimited:
            outcome = "limited"
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(30)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count("ok") == 5
    assert results.count("limited") == 25

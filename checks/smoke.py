#!/usr/bin/env python3
"""Быстрая проверка живого сервиса: API и страницы.

Запуск:  python3 checks/smoke.py http://127.0.0.1:8000
Токен админки берётся из ADMIN_TOKEN, по умолчанию dev-token.
"""
import json
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
TOKEN = "dev-token"
problems = []


def call(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, data, timeout=10) as response:
            raw = response.read().decode() or "{}"
            return response.status, json.loads(raw) if raw.strip().startswith("{") else raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode() or "{}"
        return exc.code, json.loads(raw) if raw.strip().startswith("{") else raw
    except urllib.error.URLError as exc:
        problems.append(f"сервер недоступен: {exc.reason}")
        return 0, {}


def check(name, condition, detail=""):
    mark = "ok" if condition else "ПРОБЛЕМА"
    print(f"[{mark:8}] {name} {detail}")
    if not condition:
        problems.append(name)


status, body = call("GET", "/api/health")
check("здоровье сервиса", status == 200 and body.get("ok") is True)

status, body = call("POST", "/api/leads", {"name": "", "contact": ""})
check("пустая заявка отклонена", status == 422 and "name" in body.get("errors", {}))

status, body = call("POST", "/api/leads", {"name": "Проверка", "contact": "номер"})
check("мусор в контакте отклонён", status == 422)

status, _ = call("GET", "/api/leads")
check("список заявок закрыт без токена", status == 401)

status, body = call("GET", "/api/stats", token=TOKEN)
check("статистика с токеном", status == 200 and "conversion" in body)

for path in ("/", "/admin", "/admin.html", "/style.css", "/app.js"):
    status, _ = call("GET", path)
    check(f"страница {path}", status == 200)

print()
if problems:
    print("Найдено проблем:", len(problems))
    sys.exit(1)
print("Всё в порядке")

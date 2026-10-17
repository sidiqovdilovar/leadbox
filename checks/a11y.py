"""Проверка доступности страниц сервиса движком axe-core.

Запуск при поднятом сервисе:
    python3 checks/a11y.py http://127.0.0.1:8000
Требует playwright и локальный файл axe.min.js рядом (скачивается один раз):
    curl -o checks/axe.min.js https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
AXE = os.path.join(os.path.dirname(__file__), "axe.min.js")
PAGES = ["/", "/admin"]
TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"]


def main() -> int:
    axe_source = open(AXE, encoding="utf-8").read()
    problems = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for path in PAGES:
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            page = ctx.new_page()
            page.goto(BASE + path, wait_until="load")
            page.wait_for_timeout(600)
            page.add_script_tag(content=axe_source)
            violations = page.evaluate(
                """async (tags) => {
                  const r = await axe.run(document, {runOnly: {type: 'tag', values: tags}});
                  return r.violations.map(v => ({id: v.id, n: v.nodes.length, help: v.help}));
                }""",
                TAGS,
            )
            count = sum(v["n"] for v in violations)
            problems += count
            status = "ok" if not count else "НАРУШЕНИЯ"
            print(f"[{status:9}] {path}: {count}", [v["id"] for v in violations])
            ctx.close()
        browser.close()
    print("Всё в порядке" if not problems else f"Нарушений: {problems}")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())

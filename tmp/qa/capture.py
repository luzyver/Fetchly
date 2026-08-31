import threading
from datetime import UTC, datetime
from types import SimpleNamespace
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer, make_server

from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.template.loader import render_to_string
from playwright.sync_api import sync_playwright

from downloads.states import TaskState
from dashboard.forms import AccessRuleForm
from fetchly.wsgi import application
from providers.contracts import MediaFormat


class ThreadedServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


server = make_server(
    "127.0.0.1",
    8000,
    StaticFilesHandler(application),
    server_class=ThreadedServer,
)
threading.Thread(target=server.serve_forever, daemon=True).start()
ready_html = render_to_string(
    "downloads/_inspection.html",
    {
        "task": SimpleNamespace(
            public_token="preview",
            state=TaskState.READY,
            title="Menikmati Pagi di Danau Ranu Kumbolo",
            provider="youtube",
            thumbnail_url="",
            duration_seconds=157,
            formats=(
                MediaFormat("1080", "1080p", "mp4", "video", estimated_bytes=78_600_000),
                MediaFormat("720", "720p", "mp4", "video", estimated_bytes=42_100_000),
                MediaFormat("audio", "Audio saja", "mp3", "audio", estimated_bytes=6_300_000),
            ),
        )
    },
)
dashboard_html = render_to_string(
    "dashboard/index.html",
    {
        "counts": {"queued": 3, "active": 2, "completed": 18, "failed": 1},
        "tasks": [
            SimpleNamespace(
                title="Menikmati Pagi di Danau Ranu Kumbolo",
                provider="youtube",
                state="completed",
                get_state_display=lambda: "completed",
                output_size=78_600_000,
                owner_id="8fe1b349c0a2",
                updated_at=datetime.now(UTC),
            ),
            SimpleNamespace(
                title="Resep kopi susu favorit",
                provider="instagram",
                state="downloading",
                get_state_display=lambda: "downloading",
                output_size=0,
                owner_id="91ad0f42b709",
                updated_at=datetime.now(UTC),
            ),
        ],
        "rules": [],
        "rule_form": AccessRuleForm(),
        "search": "",
        "selected_state": "",
        "states": list(TaskState),
    },
).replace("<head>", '<head><base href="http://127.0.0.1:8000/">', 1)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    for name, viewport in (
        ("desktop", {"width": 1440, "height": 1000}),
        ("mobile", {"width": 390, "height": 844}),
    ):
        page = browser.new_page(viewport=viewport)
        page.goto("http://127.0.0.1:8000", wait_until="domcontentloaded")
        page.screenshot(path=f"tmp/qa/{name}.png", full_page=True)
        page.locator("#media-url").fill("http://127.0.0.1/private")
        page.get_by_role("button", name="Cari format").click()
        page.get_by_text("Tautan belum bisa diproses").wait_for()
        page.locator("#task-result").evaluate("(element, html) => element.innerHTML = html", ready_html)
        page.screenshot(path=f"tmp/qa/{name}-ready.png", full_page=True)
        page.close()
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.set_content(dashboard_html, wait_until="networkidle")
    page.screenshot(path="tmp/qa/dashboard.png", full_page=True)
    page.close()
    browser.close()

server.shutdown()

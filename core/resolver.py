import re
import logging
import time
from typing import Optional, Tuple, List, Set, Dict
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright, Page, Frame, BrowserContext, Response, Route
from core.config import USER_AGENTS

logger = logging.getLogger(__name__)

M3U8_PATTERN = re.compile(r'(https?://[^"\\\s]+\.m3u8[^"\\\s]*)')
VIDEO_PATTERN = re.compile(r'(https?://[^"\\\s]+\.(mp4|webm|mkv|avi|mov|flv|wmv)[^"\\\s]*)', re.IGNORECASE)
IFRAME_KEYWORDS = ['embed', 'video', 'stream', 'player', 'id', 'files', 'share']
NETWORK_KEYWORDS = ['.m3u8', '.mp4', '.webm', '.mkv', '/stream/', '/variant/', 'master.m3u8']

ResolverResult = Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]

def resolve_source_url(url: str) -> ResolverResult:
    logger.info(f"Resolving: {url}")
    with sync_playwright() as p:
        browser = p.firefox.launch(
            headless=True,
            args=["--no-sandbox"]
        )
        
        context = browser.new_context(
            user_agent=USER_AGENTS['DESKTOP'],
            viewport={'width': 1920, 'height': 1080},
            locale="en-US,en;q=0.9",
            device_scale_factor=1,
            ignore_https_errors=True
        )
        
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        found_urls: List[str] = []
        context.route("**/*", lambda route: _handle_route(route, found_urls))
        context.on("response", lambda response: _handle_response(response, found_urls))

        page = context.new_page()
        page.set_default_timeout(45000)

        try:
            return _scan_recursive(page, url, found_urls)
        except Exception as e:
            logger.error(f"Resolution failed: {e}")
            return None, None, None, None
        finally:
            browser.close()

def _scan_recursive(page: Page, start_url: str, found_urls: List[str]) -> ResolverResult:
    queue = [start_url]
    visited: Set[str] = set()
    
    while queue:
        current_url = queue.pop(0)
        if current_url in visited:
            continue
            
        visited.add(current_url)
        referer = start_url if current_url != start_url else None
        
        result = _visit_and_check(page, current_url, found_urls, referer)
        if result[0]:
            return result
            
        new_iframes = _extract_iframe_srcs(page, current_url)
        for src in new_iframes:
            if src not in visited and src not in queue:
                queue.append(src)
                
    return None, None, None, None

def _visit_and_check(page: Page, url: str, found_urls: List[str], referer: Optional[str]) -> ResolverResult:
    try:
        if referer:
            page.set_extra_http_headers({"Referer": referer})
        else:
            page.set_extra_http_headers({})

        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        
        _interact_with_player(page)
        time.sleep(2)

        checkers = [
            lambda: _check_network_log(page, found_urls),
            lambda: _check_performance_api(page),
            lambda: _check_html_content(page),
            lambda: _check_frames(page),
            lambda: _check_jwplayer(page)
        ]

        for check in checkers:
            res = check()
            if res and res[0]:
                return res
                
    except Exception:
        pass
        
    return None, None, None, None

def _interact_with_player(page: Page) -> None:
    selectors = ["video", ".play-button", ".vjs-big-play-button", "[aria-label='Play']", "div[class*='play']"]
    try:
        for frame in page.frames:
            for sel in selectors:
                if frame.is_visible(sel):
                    frame.click(sel, timeout=500)
                    time.sleep(1)
                    return
    except Exception:
        pass

def _check_network_log(page: Page, found_urls: List[str]) -> Optional[ResolverResult]:
    for url in found_urls:
        if any(kw in url for kw in NETWORK_KEYWORDS):
            return _format_result(page, url)
    return None

def _check_performance_api(page: Page) -> Optional[ResolverResult]:
    try:
        logs = page.evaluate("window.performance.getEntriesByType('resource').map(e => e.name)")
        for log in logs:
            if any(kw in log for kw in NETWORK_KEYWORDS):
                return _format_result(page, log)
    except Exception:
        pass
    return None

def _check_html_content(page: Page) -> Optional[ResolverResult]:
    return _parse_content(page, page.content())

def _check_frames(page: Page) -> Optional[ResolverResult]:
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        try:
            if any(kw in frame.url for kw in NETWORK_KEYWORDS):
                return _format_result(page, frame.url)
            
            res = _parse_content(page, frame.content())
            if res:
                return res
        except Exception:
            pass
    return None

def _check_jwplayer(page: Page) -> Optional[ResolverResult]:
    try:
        jw_url = page.evaluate("""
            () => {
                return (window.jwplayer && window.jwplayer().getPlaylist) ? window.jwplayer().getPlaylist()[0].file : null
            }
        """)
        if jw_url:
            if not jw_url.startswith('http'):
                jw_url = urljoin(page.url, jw_url)
            return _format_result(page, jw_url)
    except Exception:
        pass
    return None

def _parse_content(page: Page, content: str) -> Optional[ResolverResult]:
    content = content.replace(r'\/', '/')
    
    m3u8_match = M3U8_PATTERN.search(content)
    if m3u8_match:
        return _format_result(page, m3u8_match.group(0))
        
    video_match = VIDEO_PATTERN.search(content)
    if video_match:
        return _format_result(page, video_match.group(0))
        
    return None

def _extract_iframe_srcs(page: Page, base_url: str) -> List[str]:
    srcs = []
    try:
        elements = page.query_selector_all("iframe")
        for el in elements:
            src = el.get_attribute("src")
            if src and any(kw in src for kw in IFRAME_KEYWORDS):
                if not src.startswith("http"):
                    src = urljoin(base_url, src)
                srcs.append(src)
    except Exception:
        pass
    return list(set(srcs))

def _format_result(page: Page, media_url: str) -> ResolverResult:
    cookies = "; ".join([f"{c['name']}={c['value']}" for c in page.context.cookies()])
    try:
        user_agent = page.evaluate("navigator.userAgent")
    except Exception:
        user_agent = USER_AGENTS['DESKTOP']
    return media_url, cookies, user_agent, page.url

def _handle_route(route: Route, found_urls: List[str]) -> None:
    if any(kw in route.request.url for kw in NETWORK_KEYWORDS):
        found_urls.append(route.request.url)
    route.continue_()

def _handle_response(response: Response, found_urls: List[str]) -> None:
    try:
        ct = response.header_value("content-type")
        if ct and ("mpegurl" in ct.lower() or "video/mp4" in ct.lower()):
            found_urls.append(response.url)
    except Exception:
        pass

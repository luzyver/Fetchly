import re
import logging
import time
import atexit
import threading
from collections import OrderedDict
from typing import Optional, Tuple, List, Set, Dict
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright, Page, Response, Route
from core.config import USER_AGENTS

logger = logging.getLogger(__name__)

M3U8_PATTERN = re.compile(r'(https?://[^"\\\s]+\.m3u8[^"\\\s]*)')
VIDEO_PATTERN = re.compile(r'(https?://[^"\\\s]+\.(mp4|webm|mkv|avi|mov|flv|wmv)[^"\\\s]*)', re.IGNORECASE)
IFRAME_KEYWORDS = ['embed', 'video', 'stream', 'player', 'id', 'files', 'share']
NETWORK_KEYWORDS = ['.m3u8', '.mp4', '.webm', '.mkv', '/stream/', '/variant/', 'master.m3u8']

ResolverResult = Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]

_CACHE_TTL_SECONDS = 600
_CACHE_MAX_ENTRIES = 256
_resolver_cache: "OrderedDict[str, Tuple[float, ResolverResult]]" = OrderedDict()
_cache_lock = threading.Lock()

_DOMAIN_CACHE_TTL_SECONDS = 300
_DOMAIN_CACHE_MAX_ENTRIES = 128
_domain_cache: "OrderedDict[str, Tuple[float, ResolverResult]]" = OrderedDict()
_domain_cache_lock = threading.Lock()

_browser_lock = threading.Lock()
_playwright = None
_browser = None
_resolve_lock = threading.Lock()

_metrics_lock = threading.Lock()
_metrics = {
    "requests": 0,
    "cache_hit": 0,
    "cache_miss": 0,
    "success": 0,
    "fail": 0,
    "total_ms": 0.0,
}
_METRICS_LOG_EVERY = 100

MAX_FOUND_URLS = 200


def _get_browser():
    global _playwright, _browser
    with _browser_lock:
        if _browser is None:
            _playwright = sync_playwright().start()
            _browser = _playwright.firefox.launch(
                headless=True,
                args=["--no-sandbox"]
            )
        return _browser


def _close_browser():
    global _playwright, _browser
    with _browser_lock:
        try:
            if _browser:
                _browser.close()
        finally:
            _browser = None
        try:
            if _playwright:
                _playwright.stop()
        finally:
            _playwright = None


atexit.register(_close_browser)


def _cache_get(url: str) -> Optional[ResolverResult]:
    now = time.time()
    with _cache_lock:
        entry = _resolver_cache.get(url)
        if not entry:
            return None
        ts, result = entry
        if now - ts > _CACHE_TTL_SECONDS:
            _resolver_cache.pop(url, None)
            return None
        _resolver_cache.move_to_end(url)
        return result


def _cache_domain_get(host: str) -> Optional[ResolverResult]:
    now = time.time()
    with _domain_cache_lock:
        entry = _domain_cache.get(host)
        if not entry:
            return None
        ts, result = entry
        if now - ts > _DOMAIN_CACHE_TTL_SECONDS:
            _domain_cache.pop(host, None)
            return None
        _domain_cache.move_to_end(host)
        return result


def _cache_domain_set(host: str, result: ResolverResult) -> None:
    now = time.time()
    with _domain_cache_lock:
        _domain_cache[host] = (now, result)
        _domain_cache.move_to_end(host)
        while len(_domain_cache) > _DOMAIN_CACHE_MAX_ENTRIES:
            _domain_cache.popitem(last=False)


def _normalize_host(hostname: Optional[str]) -> str:
    if not hostname:
        return ''
    return hostname.lower().rstrip('.')


def _cache_set(url: str, result: ResolverResult) -> None:
    now = time.time()
    with _cache_lock:
        _resolver_cache[url] = (now, result)
        _resolver_cache.move_to_end(url)
        while len(_resolver_cache) > _CACHE_MAX_ENTRIES:
            _resolver_cache.popitem(last=False)


def resolve_source_url(url: str) -> ResolverResult:
    logger.info(f"Resolving: {url}")
    start = time.time()
    host = _normalize_host(urlparse(url).hostname)

    cached = _cache_get(url)
    if cached and cached[0]:
        _record_metrics(cache_hit=True, success=True, elapsed_ms=(time.time() - start) * 1000)
        return cached

    if host:
        domain_cached = _cache_domain_get(host)
        if domain_cached and domain_cached[0]:
            _record_metrics(cache_hit=True, success=True, elapsed_ms=(time.time() - start) * 1000)
            return domain_cached
    _record_metrics(cache_hit=False)

    with _resolve_lock:
        browser = _get_browser()
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
            result = _scan_recursive(page, url, found_urls)
            if result and result[0]:
                _cache_set(url, result)
                media_host = _normalize_host(urlparse(result[0]).hostname)
                if host and media_host and (media_host == host or media_host.endswith(f".{host}")):
                    _cache_domain_set(host, result)
                _record_metrics(success=True, elapsed_ms=(time.time() - start) * 1000)
            else:
                _record_metrics(success=False, elapsed_ms=(time.time() - start) * 1000)
            return result
        except Exception as e:
            logger.error(f"Resolution failed: {e}")
            _record_metrics(success=False, elapsed_ms=(time.time() - start) * 1000)
            return None, None, None, None
        finally:
            try:
                context.close()
            except Exception:
                pass


def _record_metrics(cache_hit: Optional[bool] = None, success: Optional[bool] = None,
                    elapsed_ms: Optional[float] = None) -> None:
    with _metrics_lock:
        _metrics["requests"] += 1 if cache_hit is not None else 0
        if cache_hit is True:
            _metrics["cache_hit"] += 1
        elif cache_hit is False:
            _metrics["cache_miss"] += 1
        if success is True:
            _metrics["success"] += 1
        elif success is False:
            _metrics["fail"] += 1
        if elapsed_ms is not None:
            _metrics["total_ms"] += elapsed_ms

        if _metrics["requests"] and _metrics["requests"] % _METRICS_LOG_EVERY == 0:
            avg_ms = _metrics["total_ms"] / max(1, (_metrics["success"] + _metrics["fail"]))
            logger.info(
                "Resolver metrics: requests=%d hit=%d miss=%d success=%d fail=%d avg_ms=%.1f",
                _metrics["requests"],
                _metrics["cache_hit"],
                _metrics["cache_miss"],
                _metrics["success"],
                _metrics["fail"],
                avg_ms,
            )

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
        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        
        _interact_with_player(page)
        try:
            page.wait_for_timeout(1200)
        except Exception:
            pass

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
        if len(found_urls) < MAX_FOUND_URLS:
            found_urls.append(route.request.url)
    route.continue_()

def _handle_response(response: Response, found_urls: List[str]) -> None:
    try:
        ct = response.header_value("content-type")
        if ct and ("mpegurl" in ct.lower() or "video/mp4" in ct.lower()):
            if len(found_urls) < MAX_FOUND_URLS:
                found_urls.append(response.url)
    except Exception:
        pass

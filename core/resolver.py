import os
import re
import time
import shutil
import logging
from typing import Optional, Tuple, List
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from core.config import USER_AGENTS

logger = logging.getLogger(__name__)

M3U8_PATTERN = re.compile(r'(https?://[^"\\\s]+\.m3u8[^"\\\s]*)')
VIDEO_PATTERN = re.compile(r'(https?://[^"\\\s]+\.(mp4|webm|mkv|avi|mov|flv|wmv)[^"\\\s]*)', re.IGNORECASE)
IFRAME_KEYWORDS = ['embed', 'video', 'stream', 'player', 'id']
NETWORK_KEYWORDS = ['.m3u8', '.mp4', '.webm', '.mkv', '/stream/', '/variant/', 'master.m3u8']

ResolverResult = Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]


def resolve_source_url(url: str) -> ResolverResult:
    logger.info(f"Resolving: {url}")
    driver = _create_driver()

    try:
        driver.set_page_load_timeout(30)
        driver.get(url)
        time.sleep(3)

        for finder in [_find_video_in_page, _find_m3u8_in_page, lambda d: _find_m3u8_in_iframes(d, url), _find_jwplayer_url]:
            result = finder(driver)
            if result:
                return result

        return None, None, None, None

    except Exception as e:
        logger.error(f"Resolution failed: {e}")
        raise
    finally:
        _quit_driver(driver)


def _create_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_argument(f"user-agent={USER_AGENTS['DESKTOP']}")

    driver_path = _get_chromedriver_path()
    service = Service(driver_path) if driver_path else None
    return webdriver.Chrome(service=service, options=options)


def _get_chromedriver_path() -> Optional[str]:
    if os.path.exists("/usr/bin/chromedriver"):
        return "/usr/bin/chromedriver"
    return shutil.which("chromedriver")


def _quit_driver(driver: webdriver.Chrome) -> None:
    try:
        driver.quit()
    except:
        pass


def _extract_result(driver: webdriver.Chrome, m3u8_url: str) -> ResolverResult:
    cookies = "; ".join([f"{c['name']}={c['value']}" for c in driver.get_cookies()])
    user_agent = driver.execute_script("return navigator.userAgent")
    referer = driver.execute_script("return window.location.href")
    return m3u8_url, cookies, user_agent, referer


def _find_m3u8_in_page(driver: webdriver.Chrome) -> Optional[ResolverResult]:
    source = driver.page_source.replace(r'\/', '/')
    matches = M3U8_PATTERN.findall(source)
    if matches:
        return _extract_result(driver, matches[0])
    return None


def _find_video_in_page(driver: webdriver.Chrome) -> Optional[ResolverResult]:
    source = driver.page_source.replace(r'\/', '/')
    matches = VIDEO_PATTERN.findall(source)
    
    quality_order = ['1080', '720', '480', '360', 'high', 'hd', 'source']
    
    if matches:
        urls = [m[0] for m in matches]
        
        for quality in quality_order:
            for url in urls:
                if quality in url.lower():
                    logger.info(f"Found video with quality '{quality}': {url[:100]}")
                    return _extract_result(driver, url)
        
        logger.info(f"Found video: {urls[0][:100]}")
        return _extract_result(driver, urls[0])
    
    return None


def _find_m3u8_in_network(driver: webdriver.Chrome) -> Optional[ResolverResult]:
    try:
        logs = driver.execute_script("return window.performance.getEntriesByType('resource').map(e => e.name)")
        for log in logs:
            if any(kw in log for kw in NETWORK_KEYWORDS):
                logger.info(f"Found in network: {log}")
                return _extract_result(driver, log)
    except:
        pass
    return None


def _find_m3u8_in_iframes(driver: webdriver.Chrome, original_url: str) -> Optional[ResolverResult]:
    iframe_urls = _collect_iframe_urls(driver, original_url)

    for src in iframe_urls:
        logger.info(f"Checking iframe: {src}")
        result = _process_iframe(driver, original_url, src)
        if result:
            return result

    return None


def _collect_iframe_urls(driver: webdriver.Chrome, original_url: str) -> List[str]:
    urls = []
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    
    for iframe in iframes:
        try:
            src = iframe.get_attribute("src")
            if src and src != original_url and any(kw in src.lower() for kw in IFRAME_KEYWORDS):
                urls.append(src)
        except:
            continue
    
    return urls


def _process_iframe(driver: webdriver.Chrome, original_url: str, iframe_src: str) -> Optional[ResolverResult]:
    try:
        driver.get(original_url)
        time.sleep(2)

        target_iframe = _find_iframe_by_src(driver, iframe_src)
        if not target_iframe:
            return None

        driver.switch_to.frame(target_iframe)
        time.sleep(3)

        result = _find_m3u8_in_page(driver)
        if result:
            driver.switch_to.default_content()
            return result

        result = _search_nested_iframes(driver, iframe_src)
        if result:
            driver.switch_to.default_content()
            return result

        driver.switch_to.default_content()
        return _navigate_to_iframe_url(driver, iframe_src)

    except Exception as e:
        logger.warning(f"Iframe error: {e}")
        try:
            driver.switch_to.default_content()
        except:
            pass
        return None


def _find_iframe_by_src(driver: webdriver.Chrome, src: str):
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    for iframe in iframes:
        try:
            if iframe.get_attribute("src") == src:
                return iframe
        except:
            continue
    return None


def _search_nested_iframes(driver: webdriver.Chrome, parent_src: str) -> Optional[ResolverResult]:
    nested_iframes = driver.find_elements(By.TAG_NAME, "iframe")

    for nested in nested_iframes:
        try:
            nested_src = nested.get_attribute("src")
            if not nested_src or nested_src == parent_src:
                continue
            if urlparse(nested_src).netloc == urlparse(parent_src).netloc:
                continue

            logger.info(f"Checking nested iframe: {nested_src}")

            driver.switch_to.frame(nested)
            time.sleep(4)

            result = _find_m3u8_in_network(driver) or _find_m3u8_in_page(driver)
            if result:
                return result

            driver.switch_to.parent_frame()
        except:
            try:
                driver.switch_to.parent_frame()
            except:
                pass

    return None


def _navigate_to_iframe_url(driver: webdriver.Chrome, iframe_url: str) -> Optional[ResolverResult]:
    logger.info(f"Navigating to iframe URL: {iframe_url}")
    driver.get(iframe_url)
    time.sleep(3)

    return _find_m3u8_in_page(driver) or _find_m3u8_in_network(driver)


def _find_jwplayer_url(driver: webdriver.Chrome) -> Optional[ResolverResult]:
    try:
        jw_url = driver.execute_script(
            "return (window.jwplayer && window.jwplayer().getPlaylist) ? window.jwplayer().getPlaylist()[0].file : null"
        )
        if jw_url:
            if not jw_url.startswith('http'):
                jw_url = urljoin(driver.current_url, jw_url)
            return _extract_result(driver, jw_url)
    except:
        pass
    return None

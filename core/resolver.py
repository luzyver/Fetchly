import shutil
import os
import re
import time
import logging
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from core.config import USER_AGENTS

logger = logging.getLogger(__name__)

def get_chromedriver_path():
    if os.path.exists("/usr/bin/chromedriver"):
        return "/usr/bin/chromedriver"
    path = shutil.which("chromedriver")
    if path:
        return path
    return None

def resolve_source_url(url):
    logger.info(f"Resolving source URL: {url}")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_argument(f"user-agent={USER_AGENTS['DESKTOP']}")
    
    driver_path = get_chromedriver_path()
    service = Service(driver_path) if driver_path else None
    
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        driver.set_page_load_timeout(30)
        driver.get(url)
        time.sleep(3)
        
        page_source = driver.page_source.replace(r'\/', '/')
        m3u8_matches = re.findall(r'(https?://[^"\\]+\.m3u8)', page_source)
        
        def extract_cookies(drv):
            return "; ".join([f"{c['name']}={c['value']}" for c in drv.get_cookies()])

        if m3u8_matches:
            user_agent = driver.execute_script("return navigator.userAgent")
            referer = driver.execute_script("return window.location.href")
            return m3u8_matches[0], extract_cookies(driver), user_agent, referer
            
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        target_iframe = None
        target_src = None
        
        for iframe in iframes:
            src = iframe.get_attribute("src")
            if src and any(k in src.lower() for k in ['embed', 'video', 'stream', 'player', 'id']):
                if src != url:
                    target_src = src
                    target_iframe = iframe
                    break
        
        if target_iframe:
            logger.info(f"Switching to iframe: {target_src}")
            driver.switch_to.frame(target_iframe)
            time.sleep(3)
            
            iframe_source = driver.page_source.replace(r'\/', '/')
            m3u8_matches = re.findall(r'(https?://[^"\\]+\.m3u8)', iframe_source)
            if m3u8_matches:
                user_agent = driver.execute_script("return navigator.userAgent")
                referer = driver.execute_script("return window.location.href")
                driver.switch_to.default_content()
                return m3u8_matches[0], extract_cookies(driver), user_agent, referer
            
            nested_iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for nested_iframe in nested_iframes:
                nested_src = nested_iframe.get_attribute("src")
                if nested_src and nested_src != target_src:
                    if urlparse(nested_src).netloc == urlparse(target_src).netloc:
                        continue
                    
                    logger.info(f"Switching to nested iframe: {nested_src}")
                    driver.switch_to.frame(nested_iframe)
                    time.sleep(4)
                    
                    try:
                        logs = driver.execute_script("return window.performance.getEntriesByType('resource').map(e => e.name)")
                        m3u8_logs = [l for l in logs if any(k in l for k in ['.m3u8', '/stream/', '/variant/'])]
                        if m3u8_logs:
                            logger.info(f"Found m3u8 in network logs: {m3u8_logs[0]}")
                            user_agent = driver.execute_script("return navigator.userAgent")
                            referer = driver.execute_script("return window.location.href")
                            driver.switch_to.default_content()
                            return m3u8_logs[0], extract_cookies(driver), user_agent, referer
                    except Exception:
                        pass
                    
                    nested_source = driver.page_source.replace(r'\/', '/')
                    nested_m3u8 = re.findall(r'(https?://[^"\\]+\.m3u8)', nested_source)
                    if nested_m3u8:
                        user_agent = driver.execute_script("return navigator.userAgent")
                        referer = driver.execute_script("return window.location.href")
                        driver.switch_to.default_content()
                        return nested_m3u8[0], extract_cookies(driver), user_agent, referer
                    
                    driver.switch_to.parent_frame()
            
            driver.switch_to.default_content()
            
            logger.info(f"Fallback: navigating to iframe URL: {target_src}")
            driver.get(target_src)
            time.sleep(3)
            
            direct_source = driver.page_source.replace(r'\/', '/')
            direct_m3u8 = re.findall(r'(https?://[^"\\]+\.m3u8)', direct_source)
            if direct_m3u8:
                user_agent = driver.execute_script("return navigator.userAgent")
                referer = driver.execute_script("return window.location.href")
                return direct_m3u8[0], extract_cookies(driver), user_agent, referer
            
            try:
                logs = driver.execute_script("return window.performance.getEntriesByType('resource').map(e => e.name)")
                m3u8_logs = [l for l in logs if any(k in l for k in ['.m3u8', '/stream/', '/variant/', 'master.m3u8'])]
                if m3u8_logs:
                    logger.info(f"Found m3u8 in network logs: {m3u8_logs[0]}")
                    user_agent = driver.execute_script("return navigator.userAgent")
                    referer = driver.execute_script("return window.location.href")
                    return m3u8_logs[0], extract_cookies(driver), user_agent, referer
            except Exception:
                pass
        try:
            jw_url = driver.execute_script("return (window.jwplayer && window.jwplayer().getPlaylist) ? window.jwplayer().getPlaylist()[0].file : null")
            if jw_url:
                if not jw_url.startswith('http'):
                    jw_url = urljoin(driver.current_url, jw_url)
                user_agent = driver.execute_script("return navigator.userAgent")
                referer = driver.execute_script("return window.location.href")
                return jw_url, extract_cookies(driver), user_agent, referer
        except Exception:
            pass
             
        return None, None, None, None
        
    except Exception as e:
        logger.error(f"Resolution failed for {url}: {e}")
        raise
    finally:
        try:
            driver.quit()
        except:
            pass
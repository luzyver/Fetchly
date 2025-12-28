import shutil
import os
import re
import time
import logging
from urllib.parse import urljoin
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
        
        page_source = driver.page_source
        m3u8_matches = re.findall(r'(https?://[^"\\]+\.m3u8)', page_source)
        
        def extract_cookies(drv):
            return "; ".join([f"{c['name']}={c['value']}" for c in drv.get_cookies()])

        if m3u8_matches:
            return m3u8_matches[0], extract_cookies(driver)
            
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        target_src = None
        
        for iframe in iframes:
            src = iframe.get_attribute("src")
            if src and any(k in src.lower() for k in ['embed', 'video', 'stream', 'player', 'id']):
                target_src = src
                break
        
        if target_src and target_src != url:
            logger.info(f"Checking iframe: {target_src}")
            driver.get(target_src)
            time.sleep(3)
            
            m3u8_matches = re.findall(r'(https?://[^"\\]+\.m3u8)', driver.page_source)
            if m3u8_matches:
                return m3u8_matches[0], extract_cookies(driver)

        try:
             jw_url = driver.execute_script("return (window.jwplayer && window.jwplayer().getPlaylist) ? window.jwplayer().getPlaylist()[0].file : null")
             if jw_url:
                 if not jw_url.startswith('http'):
                     jw_url = urljoin(driver.current_url, jw_url)
                 return jw_url, extract_cookies(driver)
        except Exception:
             pass
             
        raise Exception("No usable M3U8 stream found.")
        
    except Exception as e:
        logger.error(f"Resolution failed for {url}: {e}")
        raise
    finally:
        try:
            driver.quit()
        except:
            pass

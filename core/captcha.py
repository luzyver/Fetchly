from typing import Optional
import requests
from core.config import CONFIG

TURNSTILE_VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'


def verify_captcha(response_token: Optional[str]) -> bool:
    if not CONFIG['TURNSTILE_SECRET_KEY']:
        return True
    
    if not response_token:
        return False
    
    try:
        resp = requests.post(
            TURNSTILE_VERIFY_URL,
            data={
                'secret': CONFIG['TURNSTILE_SECRET_KEY'],
                'response': response_token
            },
            timeout=10
        )
        return resp.json().get('success', False)
    except Exception:
        return False


def is_captcha_enabled() -> bool:
    return bool(CONFIG['TURNSTILE_SITE_KEY'] and CONFIG['TURNSTILE_SECRET_KEY'])

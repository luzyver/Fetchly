import requests
from core.config import CONFIG


def verify_captcha(response_token):
    if not CONFIG['TURNSTILE_SECRET_KEY']:
        return True
    
    if not response_token:
        return False
    
    try:
        resp = requests.post(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data={
                'secret': CONFIG['TURNSTILE_SECRET_KEY'],
                'response': response_token
            },
            timeout=10
        )
        result = resp.json()
        return result.get('success', False)
    except Exception:
        return False


def is_captcha_enabled():
    return bool(CONFIG['TURNSTILE_SITE_KEY'] and CONFIG['TURNSTILE_SECRET_KEY'])

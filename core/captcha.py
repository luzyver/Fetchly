import requests
from core.config import CONFIG


def verify_captcha(response_token):
    if not CONFIG['RECAPTCHA_SECRET_KEY']:
        return True
    
    if not response_token:
        return False
    
    try:
        resp = requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data={
                'secret': CONFIG['RECAPTCHA_SECRET_KEY'],
                'response': response_token
            },
            timeout=10
        )
        result = resp.json()
        return result.get('success', False)
    except Exception:
        return False


def is_captcha_enabled():
    return bool(CONFIG['RECAPTCHA_SITE_KEY'] and CONFIG['RECAPTCHA_SECRET_KEY'])

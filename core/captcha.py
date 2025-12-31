import requests
from core.config import CONFIG

CAPTCHA_SCORE_THRESHOLD = 0.7


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
        
        if 'score' in result:
            return result.get('success', False) and result.get('score', 0) >= CAPTCHA_SCORE_THRESHOLD
        
        return result.get('success', False)
    except Exception:
        return False


def is_captcha_enabled():
    return bool(CONFIG['RECAPTCHA_SITE_KEY'] and CONFIG['RECAPTCHA_SECRET_KEY'])

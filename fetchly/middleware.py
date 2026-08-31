import re
import uuid

REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{16,64}$")


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied = request.headers.get("X-Request-ID", "")
        request.request_id = supplied if REQUEST_ID.fullmatch(supplied) else uuid.uuid4().hex
        response = self.get_response(request)
        response.headers["X-Request-ID"] = request.request_id
        return response

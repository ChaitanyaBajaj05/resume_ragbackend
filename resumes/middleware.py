from django.utils.deprecation import MiddlewareMixin
from .models import IdempotencyKey
import hashlib
import json
from django.http import JsonResponse

class IdempotencyMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.method == "POST":
            key = request.headers.get("Idempotency-Key")
            if not key:
                return None
            user = getattr(request, "user", None)
            body = request.body or b""
            request_hash = hashlib.sha256(body).hexdigest()
            existing = IdempotencyKey.objects.filter(key=key).first()
            if existing:
                # return cached response if endpoint and user match
                if existing.request_hash == request_hash:
                    if existing.response_body:
                        return JsonResponse(existing.response_body)
                else:
                    # conflict
                    return JsonResponse({"error":"IDEMPOTENCY_CONFLICT"}, status=409)
            else:
                # save a placeholder for later ; actual response stored by view
                if user and user.is_authenticated:
                    IdempotencyKey.objects.create(key=key, user=user, endpoint=request.path, request_hash=request_hash)
        return None

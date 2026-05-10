from __future__ import annotations

import logging
import traceback
from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

_LOGGER = logging.getLogger(__name__)


class UnhandledExceptionMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self._get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        try:
            return self._get_response(request)
        except Exception:
            _LOGGER.exception(
                "Unhandled exception while handling %s %s",
                request.method,
                request.get_full_path(),
            )
            if settings.DJANGO_PLAIN_TRACEBACKS:
                return HttpResponse(
                    traceback.format_exc(),
                    status=500,
                    content_type="text/plain; charset=utf-8",
                )
            raise

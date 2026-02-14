"""
STEP 4: When DEBUG_TRACE is True, enable query logging so TRACE QUERIES can be logged.
"""
from django.conf import settings
from django.db import connection


class DebugTraceMiddleware:
    """Enable debug cursor for the request when DEBUG_TRACE is True (so connection.queries is populated)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "DEBUG_TRACE", False):
            connection.force_debug_cursor = True
        try:
            return self.get_response(request)
        finally:
            if getattr(settings, "DEBUG_TRACE", False):
                connection.force_debug_cursor = False

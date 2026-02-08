"""
Custom authentication decorators and mixins for OTP-based authentication
"""

from functools import wraps
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse


def login_required_for_action(view_func):
    """
    Decorator that redirects to OTP login if user is not authenticated.
    For AJAX requests returns JSON so frontend can show login modal.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            next_url = request.get_full_path()
            login_url = f"{reverse('auth:login')}?next={next_url}"
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({
                    "login_required": True,
                    "login_url": login_url,
                    "next": next_url,
                }, status=401)
            return redirect(login_url)
        return view_func(request, *args, **kwargs)
    return wrapper


class LoginRequiredForActionMixin:
    """
    Mixin that redirects to OTP login if user is not authenticated.
    For AJAX requests returns JSON (login_required) so frontend can show login modal.
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            next_url = request.get_full_path()
            login_url = f"{reverse('auth:login')}?next={next_url}"
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({
                    "login_required": True,
                    "login_url": login_url,
                    "next": next_url,
                }, status=401)
            return redirect(login_url)
        return super().dispatch(request, *args, **kwargs)


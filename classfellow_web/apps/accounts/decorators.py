"""
ClassFellow Web - Role-Based Access Control Decorators
Enforces role validation (Admin, Principal, Cashier) for web views.
"""

from functools import wraps
from typing import Sequence
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden


def role_required(allowed_roles: Sequence[str]):
    """
    Decorator for views that checks if the logged-in user possesses
    one of the specified institutional roles (or is a superuser).
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            user = request.user
            if user.is_superuser:
                return view_func(request, *args, **kwargs)

            user_role = getattr(user, "role", None)
            if user_role in allowed_roles:
                return view_func(request, *args, **kwargs)

            return HttpResponseForbidden(
                f"Access Denied: Your assigned role '{user_role}' does not have permission "
                f"to access this workspace. Required roles: {', '.join(allowed_roles)}."
            )

        return _wrapped_view

    return decorator

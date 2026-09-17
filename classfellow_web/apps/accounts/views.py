"""
ClassFellow Web - Authentication Views
Session-based login and logout handling with institutional role presentation.
"""

from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods


def login_view(request: HttpRequest) -> HttpResponse:
    """Renders login interface and processes user credential authentication."""
    if request.user.is_authenticated:
        return redirect("/")

    next_url = request.GET.get("next") or request.POST.get("next") or "/"

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not user.is_active:
                messages.error(request, "This account is inactive. Please contact your system administrator.")
                return render(request, "accounts/login.html", {"next": next_url, "username": username})

            login(request, user)
            messages.success(request, f"Welcome back, {user.first_name or user.username} ({user.role})!")
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password. Please verify credentials.")
            return render(request, "accounts/login.html", {"next": next_url, "username": username})

    return render(request, "accounts/login.html", {"next": next_url})


@require_http_methods(["GET", "POST"])
def logout_view(request: HttpRequest) -> HttpResponse:
    """Terminates active user session and redirects to login interface."""
    logout(request)
    messages.info(request, "You have been safely signed out.")
    return redirect("/accounts/login/")

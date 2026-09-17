"""
ClassFellow Web - API Authentication Views
Token-based authentication endpoint for mobile apps and headless clients.
"""

from apps.accounts.models import User
from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class LoginView(APIView):
    """
    POST /api/v1/auth/login/
    Authenticates user credentials and issues/retrieves an auth Token along with role profile.
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        username = request.data.get("username", "").strip()
        password = request.data.get("password", "").strip()

        if not username or not password:
            return Response(
                {"error": "Both 'username' and 'password' are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Explicitly check for inactive accounts with correct credentials
        candidate = User.objects.filter(username=username).first()
        if candidate and not candidate.is_active and candidate.check_password(password):
            return Response(
                {"error": "Account is inactive. Contact the administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )

        user = authenticate(request=request._request, username=username, password=password)

        if user is None:
            return Response(
                {"error": "Invalid username or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token, _ = Token.objects.get_or_create(user=user)

        if hasattr(user, "staff_profile") and user.staff_profile:
            full_name = user.staff_profile.full_name
        else:
            full_name = f"{user.first_name} {user.last_name}".strip() or user.username

        return Response(
            {
                "token": token.key,
                "user_id": user.id,
                "username": user.username,
                "role": str(user.role),
                "full_name": full_name,
            },
            status=status.HTTP_200_OK,
        )

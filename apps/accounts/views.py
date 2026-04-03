"""
Accounts views for TezCV.uz.

All endpoints use APIView (not ViewSets).
Authentication is handled by MongoJWTAuthentication (Bearer token).
"""

from datetime import datetime, timezone

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth_utils import blacklist_token, generate_tokens, refresh_access_token
from .documents import User
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    RegisterSerializer,
    UserProfileSerializer,
)


class RegisterView(APIView):
    """
    POST /api/auth/register/
    Create a new user account and return a token pair.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        tokens = generate_tokens(user)
        profile = UserProfileSerializer(user)

        return Response(
            {**tokens, 'user': profile.data},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """
    POST /api/auth/login/
    Authenticate with email + password, return token pair.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email'].lower()
        password = serializer.validated_data['password']

        user = User.objects(email=email).first()
        if not user or not user.check_password(password):
            return Response(
                {'detail': 'Invalid email or password.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {'detail': 'This account is inactive.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Update last_login timestamp
        user.last_login = datetime.now(timezone.utc)
        user.save()

        tokens = generate_tokens(user)
        profile = UserProfileSerializer(user)

        return Response({**tokens, 'user': profile.data}, status=status.HTTP_200_OK)


class TokenRefreshView(APIView):
    """
    POST /api/auth/token/refresh/
    Accept {"refresh": "<token>"} and return a new token pair.
    The old refresh token is blacklisted (rotation).
    """

    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'detail': 'Refresh token is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tokens = refresh_access_token(refresh_token)
        return Response(tokens, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Blacklist the supplied refresh token. Requires authentication.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if refresh_token:
            blacklist_token(refresh_token)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProfileView(APIView):
    """
    GET  /api/auth/profile/  — Return the authenticated user's profile.
    PUT  /api/auth/profile/  — Update the authenticated user's profile.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    def put(self, request):
        serializer = UserProfileSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserProfileSerializer(user).data)


class ChangePasswordView(APIView):
    """
    POST /api/auth/change-password/
    Change the authenticated user's password.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {'old_password': 'Current password is incorrect.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response(
            {'detail': 'Password updated successfully.'},
            status=status.HTTP_200_OK,
        )

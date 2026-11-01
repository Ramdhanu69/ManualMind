from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.roles import role_of
from apps.core.models import AuditLog, record_audit


def login_page(request):
    if request.user.is_authenticated:
        return redirect("home")
    return render(request, "accounts/login.html")


class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = (request.data.get("username") or "").strip()
        password = request.data.get("password") or ""
        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {"detail": "Invalid username or password.", "errors": {}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request, user)
        record_audit(user, AuditLog.ACTION_LOGIN, username)
        return Response({"username": user.username, "role": role_of(user)})


class LogoutAPIView(APIView):
    def post(self, request):
        record_audit(request.user, AuditLog.ACTION_LOGOUT, request.user.username)
        logout(request)
        return Response({"detail": "Signed out."})


class MeAPIView(APIView):
    def get(self, request):
        return Response({"username": request.user.username, "role": role_of(request.user)})

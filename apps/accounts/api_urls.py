from django.urls import path

from apps.accounts.views import LoginAPIView, LogoutAPIView, MeAPIView

urlpatterns = [
    path("login", LoginAPIView.as_view(), name="api_login"),
    path("logout", LogoutAPIView.as_view(), name="api_logout"),
    path("me", MeAPIView.as_view(), name="api_me"),
]

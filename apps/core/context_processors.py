from django.conf import settings

from apps.accounts.roles import role_of


def branding(request):
    return {
        "app_name": settings.APP_NAME,
        "safety_banner": settings.SAFETY_BANNER,
        "user_role": role_of(getattr(request, "user", None)),
    }

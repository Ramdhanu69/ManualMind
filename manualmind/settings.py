"""Django settings for ManualMind."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    SECRET_KEY=(str, "insecure-dev-key-do-not-use-in-production"),
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    POSTGRES_DB=(str, "manualmind"),
    POSTGRES_USER=(str, "manualmind"),
    POSTGRES_PASSWORD=(str, "manualmind"),
    POSTGRES_HOST=(str, "127.0.0.1"),
    POSTGRES_PORT=(int, 5432),
    VECTOR_BACKEND=(str, "numpy"),
    EMBEDDING_PROVIDER=(str, "fake"),
    EMBEDDING_MODEL=(str, "fake-hash-384"),
    EMBEDDING_DIM=(int, 384),
    EMBEDDING_API_KEY=(str, ""),
    EMBEDDING_BASE_URL=(str, "https://api.openai.com/v1"),
    LLM_PROVIDER=(str, "fake"),
    LLM_MODEL=(str, "fake-llm"),
    LLM_API_KEY=(str, ""),
    LLM_BASE_URL=(str, "https://api.openai.com/v1"),
    LLM_TEMPERATURE=(float, 0.0),
    RETRIEVAL_MIN_SCORE=(float, 0.10),
    DEMO_ADMIN_PASSWORD=(str, "Demo@1234"),
    DEMO_ENGINEER_PASSWORD=(str, "Demo@1234"),
    DEMO_SUPERVISOR_PASSWORD=(str, "Demo@1234"),
)
environ.Env.read_env(BASE_DIR / ".env")

# Product name lives in exactly one place.
APP_NAME = "ManualMind"
SAFETY_BANNER = (
    "Fictional training dataset. Answers summarize the manuals; they do not "
    "authorize operation, repair, or return to service."
)

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "apps.core",
    "apps.accounts",
    "apps.machines",
    "apps.manuals",
    "apps.assistant",
    "apps.supervisor",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "manualmind.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.branding",
            ],
        },
    },
]

WSGI_APPLICATION = "manualmind.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB"),
        "USER": env("POSTGRES_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST"),
        "PORT": env("POSTGRES_PORT"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Uploaded manuals are never served from a public URL; they are streamed by a
# login-protected view, so MEDIA_URL is deliberately left unrouted.
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
}

# --- Retrieval / ingestion ---
VECTOR_BACKEND = env("VECTOR_BACKEND")
RETRIEVAL_MIN_SCORE = env("RETRIEVAL_MIN_SCORE")
RETRIEVAL_VECTOR_TOP_K = 12
RETRIEVAL_KEYWORD_TOP_K = 12
RETRIEVAL_CONTEXT_K = 6
RRF_K = 60

CHUNK_MIN_CHARS = 500
CHUNK_MAX_CHARS = 900
CHUNK_OVERLAP_CHARS = 100
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

# --- Providers ---
EMBEDDING_PROVIDER = env("EMBEDDING_PROVIDER")
EMBEDDING_MODEL = env("EMBEDDING_MODEL")
EMBEDDING_DIM = env("EMBEDDING_DIM")
EMBEDDING_API_KEY = env("EMBEDDING_API_KEY")
EMBEDDING_BASE_URL = env("EMBEDDING_BASE_URL")

LLM_PROVIDER = env("LLM_PROVIDER")
LLM_MODEL = env("LLM_MODEL")
LLM_API_KEY = env("LLM_API_KEY")
LLM_BASE_URL = env("LLM_BASE_URL")
LLM_TEMPERATURE = env("LLM_TEMPERATURE")
PROVIDER_TIMEOUT_SECONDS = 30

DEMO_PASSWORDS = {
    "admin1": env("DEMO_ADMIN_PASSWORD"),
    "engineer1": env("DEMO_ENGINEER_PASSWORD"),
    "supervisor1": env("DEMO_SUPERVISOR_PASSWORD"),
}
STUDENT_PACK_DIR = BASE_DIR / "student_pack"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

"""
PROJETO CARCARÁ — Configurações Django
"""

import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-troque-em-producao")

DEBUG = os.getenv("DEBUG", "true").lower() == "true"

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# ── Apps ──────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "accounts",
    "observacoes",
]

# ── Modelo de usuário customizado ─────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.Usuario"

# ── Middleware ─────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "carcara.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "carcara.wsgi.application"

# ── Banco de dados ────────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE":   "django.db.backends.postgresql",
        "NAME":     os.getenv("DB_NAME",     "carcara_db"),
        "USER":     os.getenv("DB_USER",     "carcara_user"),
        "PASSWORD": os.getenv("DB_PASSWORD", "carcara_pass"),
        "HOST":     os.getenv("DB_HOST",     "localhost"),
        "PORT":     os.getenv("DB_PORT",     "5432"),
    }
}

# ── DRF + JWT ─────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
}

# ── SimpleJWT ─────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME":  timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS":    True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM":    "HS256",
    "SIGNING_KEY":  SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME":  "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_OBTAIN_SERIALIZER": "accounts.serializers.CarcaraTokenObtainPairSerializer",
}

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:8000,http://localhost:3000"
).split(",")

# ── Internacionalização ───────────────────────────────────────────────────────
LANGUAGE_CODE = "pt-br"
TIME_ZONE     = "America/Fortaleza"
USE_I18N      = True
USE_TZ        = True

STATIC_URL  = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Google OAuth ──────────────────────────────────────────────────────────────
# Obter em: console.cloud.google.com → APIs & Services → Credentials
# Instalar: pip install google-auth
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

# ── E-mail (recuperação de senha) ─────────────────────────────────────────────
# Em desenvolvimento: deixe EMAIL_BACKEND vazio → usa console (imprime no terminal)
# Em produção:        configure SMTP no .env
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST          = os.getenv("EMAIL_HOST",     "smtp.gmail.com")
EMAIL_PORT          = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS       = True
EMAIL_HOST_USER     = os.getenv("EMAIL_HOST_USER",     "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL  = os.getenv(
    "DEFAULT_FROM_EMAIL", "Carcará <noreply@carcara.nupreds.br>"
)

# URL base do frontend — usada para montar o link de redefinição de senha
# Ex: https://app.carcara.nupreds.br/redefinir-senha/<uid>/<token>/
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Validade do token de reset em segundos (padrão Django = 3 dias)
PASSWORD_RESET_TIMEOUT = int(os.getenv("PASSWORD_RESET_TIMEOUT", "259200"))

# ── Logging ───────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} | {levelname:<8} | {name} | {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "carcara": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
    },
}

"""
Django settings for eagleproject project.

Generated by 'django-admin startproject' using Django 3.1.1.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""

import os
from pathlib import Path
import environ

try:
    import envkey  # noqa: F401
except ValueError as err:
    if 'ENVKEY missing' not in str(err):
        raise err

env = environ.Env(
    # set casting, default value
    DEBUG=(bool, False),
    DATABASE_HOST_OVERRIDE=(str, None),
)
env_file = Path(__file__).resolve().parent.joinpath('.env')
environ.Env.read_env(env.str('ENV_PATH', str(env_file)))

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DEBUG")
USE_THOUSAND_SEPARATOR = True

ALLOWED_HOSTS = [env("ALLOWED_HOST"), "analytics.ousd.com"]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "core",
    "notify",
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

ROOT_URLCONF = "eagleproject.urls"

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

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {name} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.getenv('LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'requests': {
            'handlers': ['console'],
            'level': os.environ.get('REQUESTS_LOG_LEVEL', 'WARNING'),
            'propagate': True,
        },
        'urllib3': {
            'handlers': ['console'],
            'level': os.environ.get('REQUESTS_LOG_LEVEL', 'WARNING'),
            'propagate': True,
        },
    },
}

WSGI_APPLICATION = "eagleproject.wsgi.application"


# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases

DATABASES = {"default": env.db()}
if os.environ.get("DATABASE_HOST_OVERRIDE"):
    DATABASES["default"]["HOST"] = os.environ.get("DATABASE_HOST_OVERRIDE")
CONN_MAX_AGE = 100

# Password validation
# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "static")

REPORT_RECEIVER_EMAIL_LIST = os.environ.get("REPORT_RECEIVER_EMAIL_LIST")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL")
EMAIL_HOST = os.environ.get("EMAIL_HOST")
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
EMAIL_PORT = os.environ.get("EMAIL_PORT", 25)
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS") == "true"
ENABLE_REPORTS = os.environ.get("ENABLE_REPORTS")

ADMINS = [("Engineering", "engineering@originprotocol.com")]
DISCORD_BOT_NAME = os.environ.get("DISCORD_BOT_NAME", "OUSD Analytics Bot")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
OGN_DISCORD_WEBHOOK_URL = os.environ.get(
    "OGN_DISCORD_WEBHOOK_URL",
    DISCORD_WEBHOOK_URL
)
# Comma delimited User IDs (e.g. 'Mike Shultz#5937' is '386238710255058954')
# You can get this by Right clicking the name and "Copy ID" with developer mode
DISCORD_WEBHOOK_AT = os.environ.get("DISCORD_WEBHOOK_AT")

ETHERSCAN_API_KEY = os.environ.get("ETHERSCAN_API_KEY")

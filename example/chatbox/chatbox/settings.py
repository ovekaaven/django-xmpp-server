"""
Django settings for chatbox project.

Generated by 'django-admin startproject' using Django 2.0.3.

For more information on this file, see
https://docs.djangoproject.com/en/2.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.0/ref/settings/
"""

import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '&$w2-x+7m(hk-*s51^iq2-z&_^6^jg3&%xlq5m9na-pnx-ei0*'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']


# Application definition

INSTALLED_APPS = [
    'xmppserver',
    'xmppserver.sessiondb',
    'xmppserver.rosterdb',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'chatbox.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'chatbox/templates')
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'chatbox.wsgi.application'
ASGI_APPLICATION = 'chatbox.routing.application'


# Database
# https://docs.djangoproject.com/en/2.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/2.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/2.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.0/howto/static-files/

STATIC_URL = '/static/'


# Logging

LOGGING = {
    'version': 1,
    'formatters': {
        'timestamp': {
            'format': '%(asctime)s %(message)s',
        },
        'xmppstream': {
            'format': '%(asctime)s [%(sid)s] %(message)s',
        },
        'xmpptransport': {
            'format': '%(asctime)s [%(client)s] %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'timestamp',
        },
        'xmppstream': {
            'class': 'logging.StreamHandler',
            'formatter': 'xmppstream',
        },
        'xmpptransport': {
            'class': 'logging.StreamHandler',
            'formatter': 'xmpptransport',
        },
    },
    'loggers': {
        'xmppserver.stream': {
            'handlers': ['xmppstream'],
            'level': 'INFO',
            'propagate': True,
        },
        'xmppserver.transport': {
            'handlers': ['xmpptransport'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# XMPP Server

CHANNEL_LAYERS = {
    'xmppserver': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
        'CONFIG': {},
    }
}

XMPP_DOMAIN = 'localhost'
XMPP_SERVER = 'localhost:8000'
XMPP_SERVER_SECURE = False
XMPP_ALLOW_WEBSOCKETS = True
XMPP_ALLOW_ANONYMOUS_LOGIN = False
XMPP_ALLOW_PLAIN_LOGIN = True
XMPP_ALLOW_WEBUSER_LOGIN = False

XMPP_TLS_CERT_PATH = os.path.join(BASE_DIR, 'fullchain1.pem')
XMPP_TLS_PRIV_KEY_PATH = os.path.join(BASE_DIR, 'privkey1.pem')

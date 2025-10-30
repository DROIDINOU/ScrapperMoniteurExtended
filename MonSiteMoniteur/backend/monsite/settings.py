from dotenv import load_dotenv
from pathlib import Path
import os

# backend/settings.py --> /MonProjetFinalMoniteur/MonSiteMoniteur/backend/settings.py
BASE_DIR = Path(__file__).resolve().parent.parent  # backend/

# >>> MONTER D'UN SEUL NIVEAU <<<
ENV_PATH = BASE_DIR.parent.parent / ".env"
load_dotenv(ENV_PATH, override=True)
# --- MeiliSearch ---
MEILI_URL = os.getenv("MEILI_URL")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY")
MEILI_SEARCH_KEY = os.getenv("MEILI_MASTER_KEY")  # si tu n’as pas de clé SEARCH séparée
INDEX_NAME = os.getenv("INDEX_NAME")
INDEX_RUE_NAME = os.getenv("INDEX_RUE_NAME", "mesrues_be")
print("✅ .env utilisé :", ENV_PATH)
print("SECRET_KEY =", os.getenv("SECRET_KEY"))
print("DB USER/PASS =", os.getenv("DB_USER"), os.getenv("DB_PASSWORD"))
print("BASE_DIR =", BASE_DIR)
print("BASE_DIR.parent =", BASE_DIR.parent)
print("BASE_DIR.parent.parent =", BASE_DIR.parent.parent)
SECRET_KEY = os.getenv("SECRET_KEY")
print("SECRET_KEY:", SECRET_KEY)
# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['juriscope.onrender.com', 'localhost', '127.0.0.1', '6297ec3f0568.ngrok-free.app']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',  # Correcte la ligne ici
    'veille',  # Ajoute cette ligne pour ton application 'veille'
    'corsheaders',  # Ajoute cette ligne pour le CORS
]

SESSION_COOKIE_SAMESITE = "None"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "None"
CSRF_COOKIE_SECURE = True

CORS_ALLOWED_ORIGINS = [
    "https://hypothes.is",
    "https://6297ec3f0568.ngrok-free.app",
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Ajoute cette ligne
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'monsite.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv("DB_NAME"),
        'USER': os.getenv("DB_USER"),
'PASSWORD': os.getenv("DB_PASSWORD") or "",

        'HOST': os.getenv("DB_HOST"),
        'PORT': os.getenv("DB_PORT"),
    }
}



# Password validation
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

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'

# Répertoire où Django va collecter les fichiers statiques en production
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
# Configuration de WhiteNoise pour gérer les fichiers statiques en production
if not DEBUG:
    # Tell Django to copy static assets into a path called `staticfiles` (this is specific to Render)
    STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

    # Enable the WhiteNoise storage backend, which compresses static files to reduce disk use
    # and renames the files with unique names for each version to support long-term caching
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Enable Brotli compression (optionnel, mais recommandé pour les performances)
# STATICFILES_STORAGE = 'whitenoise.storage.StaticFilesStorage'

print("Fichiers statiques collectés à : ", STATIC_ROOT)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

"""Portable tests. PostgreSQL is still required to verify concurrent row locks."""
from .settings import *
from django.contrib.auth.hashers import PBKDF2PasswordHasher


class TestPBKDF2PasswordHasher(PBKDF2PasswordHasher):
    iterations = 1000

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != 'django.contrib.gis']
PASSWORD_HASHERS = ['nucleo.settings_test.TestPBKDF2PasswordHasher']
MEDIA_ROOT = BASE_DIR / '.test-downloads' / 'media'

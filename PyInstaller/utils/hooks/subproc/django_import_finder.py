#-----------------------------------------------------------------------------
# Copyright (c) 2005-2016, PyInstaller Development Team.
#
# Distributed under the terms of the GNU General Public License with exception
# for distributing bootloader.
#
# The full license is in the file COPYING.txt, distributed with this software.
#-----------------------------------------------------------------------------


"""
This module parses all Django dependencies from the module mysite.settings.py.

NOTE: With newer version of Django this is most likely the part of PyInstaller
      that will be broken.

Tested with Django 1.8.
"""

# Calling django.setup() avoids the exception AppRegistryNotReady()
# and also reads the project settings from DJANGO_SETTINGS_MODULE.
# https://stackoverflow.com/questions/24793351/django-appregistrynotready
import django
if hasattr(django, 'setup'):  # Added in Django 1.7
    django.setup()

import importlib
import logging

from django.conf import settings
from django.core.urlresolvers import RegexURLPattern, RegexURLResolver

logger = logging.getLogger(__name__)

hiddenimports = []

# Use a settings attribute, or a tuple of attributes/keys for nested settings
# (e.g. DATABASES, LOGGING, etc.) Use "*" to iterate over a list/tuple or the
# values of a dict. Below are all settings that might contain a Python dotted
# path, according to Django 1.9 docs.
SETTINGS = (
    'AUTH_PASSWORD_VALIDATORS',
    'AUTHENTICATION_BACKENDS',
    'CSRF_FAILURE_VIEW',
    'DATABASE_ROUTERS',
    'DEFAULT_EXCEPTION_REPORTER_FILTER',
    'DEFAULT_FILE_STORAGE',
    'EMAIL_BACKEND',
    'FILE_UPLOAD_HANDLERS',
    'FORMAT_MODULE_PATH',
    'FORMAT_MODULE_PATH',
    'INSTALLED_APPS',
    'LOGGING_CONFIG',
    'LOGIN_REDIRECT_URL',  # Deprecated in 1.8
    'LOGIN_URL',  # Deprecated in 1.8
    'MESSAGE_STORAGE',
    'MIDDLEWARE_CLASSES',
    'PASSWORD_HASHERS',
    'ROOT_URLCONF',
    'SESSION_ENGINE',
    'SESSION_SERIALIZER',
    'SIGNING_BACKEND',
    'STATICFILES_FINDERS',
    'STATICFILES_STORAGE',
    'TEMPLATE_CONTEXT_PROCESSORS',  # Deprecated in 1.8
    'TEMPLATE_LOADERS',  # Deprecated in 1.8
    'TEST_RUNNER',
    'WSGI_APPLICATION',
    ('CACHES', '*', 'BACKEND'),
    ('CACHES', '*', 'KEY_FUNCTION'),
    ('DATABASES', '*', 'ENGINE'),
    ('DATABASES', '*', 'TEST', 'ENGINE'),
    ('LOGGING', '*', '*', '()'),
    ('LOGGING', '*', '*', 'class'),
    ('MIGRATION_MODULES', '*'),
    ('SERIALIZATION_MODULES', '*'),
    ('TEMPLATES', 'BACKEND'),
    ('TEMPLATES', 'OPTIONS', 'context_processors'),
    ('TEMPLATES', 'OPTIONS', 'loaders'),
)


def get_nested_settings(keys, value):
    keys = list(keys)  # Copy keys as list, so we can pop items from it
    hiddenimports = []
    if keys:
        key = keys.pop(0)
        if key == '*':
            # Convert dict values to a list.
            if isinstance(value, dict):
                value = value.values()
            # Recurse to get value from all items in list.
            if isinstance(value, (list, tuple)):
                for item in value:
                    hiddenimports.extend(get_nested_settings(keys, item))
        else:
            # Get value from dict or object.
            if isinstance(value, dict):
                value = value.get(key, None)
            else:
                value = getattr(value, key, None)
            # Recurse when there are still more nested keys.
            if keys:
                hiddenimports.extend(get_nested_settings(keys, value))
            # Add non-empty values for key to hidden imports.
            elif value:
                if isinstance(value, (list, tuple)):
                    hiddenimports.extend(list(value))
                else:
                    hiddenimports.append(value)
    return hiddenimports

# Get hidden imports from settings.
for keys in SETTINGS:
    if not isinstance(keys, (list, tuple)):
        keys = (keys, )
    value = get_nested_settings(keys, settings)
    if value:
        logger.info('Found hidden import(s) in Django setting(s) %s: %s' % (
            ' > '.join(keys),
            ', '.join(value),
        ))
        hiddenimports.extend(value)

# Get hidden imports from installed AppConfig classes.
for app in settings.INSTALLED_APPS:
    try:
        importlib.import_module(app)
    except ImportError:
        logger.debug('Failed to import module or package: %s' % app)
        bits = app.split('.')
        mod = importlib.import_module('.'.join(bits[:-1]))
        config = getattr(mod, bits[-1])
        logger.info('Found hidden import in INSTALLED_APPS %s: %s' % (
            app,
            config.name,
        ))
        hiddenimports.append(config.name)


def find_url_callbacks(urls_module):
    hiddenimports = set()  # Use a set to de-dupe
    if isinstance(urls_module, list):
        urlpatterns = urls_module
    else:
        urlpatterns = urls_module.urlpatterns
    for pattern in urlpatterns:
        if isinstance(pattern, RegexURLPattern):
            hiddenimports.add(pattern.callback.__module__)
        elif isinstance(pattern, RegexURLResolver):
            hiddenimports.update(find_url_callbacks(pattern.urlconf_module))
    return list(hiddenimports)

# Get hidden imports from root URLconf.
if hasattr(settings, 'ROOT_URLCONF'):
    value = find_url_callbacks(importlib.import_module(settings.ROOT_URLCONF))
    if value:
        logger.info('Found hidden import(s) in root URLconf %s: %s' % (
            settings.ROOT_URLCONF,
            ', '.join(value),
        ))
        hiddenimports.extend(value)

# Some hidden imports might be a class or function, or not be a dotted path at
# all. Traverse up the dotted path until we get an importable module or
# package, and de-dupe.
packages = set()
for mod in hiddenimports:
    while mod:
        if mod in packages:  # Already seen
            break
        try:
            importlib.import_module(mod)  # Importable?
        except ImportError:
            # Drop last part of dotted path and try again.
            logger.debug('Failed to import module or package: %s' % mod)
            mod = '.'.join(mod.split('.')[:-1])
            continue
        packages.add(mod)
        break

if packages:
    logger.info('Found hidden imports in Django project: %s' % ', '.join(
        sorted(packages)))

# This print statement is then parsed and evaluated as Python code.
print(list(sorted(packages)))

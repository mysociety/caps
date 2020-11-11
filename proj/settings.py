"""
For more information on this file, see
https://docs.djangoproject.com/en/1.7/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.7/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
import socket
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATIC_URL = '/static/'

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

SITE_ROOT = os.path.realpath(os.path.dirname(__file__))

DEBUG = True

if DEBUG:
    IS_LIVE = False
    STATICFILES_STORAGE = 'pipeline.storage.NonPackagingPipelineStorage'
else:
    IS_LIVE = True
    STATICFILES_STORAGE = 'pipeline.storage.PipelineStorage'

ALLOWED_HOSTS = ["127.0.0.1",
                 "testserver",
                 "0.0.0.0",
                 "localhost"]

from conf.config import *  # stores database and key outside repo

LANGUAGE_CODE = 'en-uk'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'proj.universal.universal_context',
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

STATICFILES_DIRS = (
    (
        "bootstrap",
        os.path.join(BASE_DIR, "vendor", "bootstrap", "scss"),
    ),
    (
        "bootstrap",
        os.path.join(BASE_DIR, "vendor", "bootstrap", "js"),
    ),
    (
        "html5shiv",
        os.path.join(BASE_DIR, "vendor", "html5shiv"),
    ),
    (
        "jquery",
        os.path.join(BASE_DIR, "vendor", "jquery"),
    ),
    (
        "chartjs",
        os.path.join(BASE_DIR, "vendor", "chartjs"),
    )
)

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'pipeline.finders.PipelineFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder'
)

PIPELINE = {
    'STYLESHEETS': {
        'main': {
            'source_filenames': (
                'scss/main.scss',
            ),
            'output_filename': 'css/main.css',
        },
    },
    'JAVASCRIPT': {
        'main': {
            'source_filenames': (
                'js/main.js',
            ),
            'output_filename': 'js/main.js',
        },
    },

    'CSS_COMPRESSOR': 'django_pipeline_csscompressor.CssCompressor',
    'DISABLE_WRAPPER': True,
    'COMPILERS': (
        'pipeline.compilers.sass.SASSCompiler',
    ),
    'SHOW_ERRORS_INLINE':False,
    # Use the libsass commandline tool (that's bundled with libsass) as our
    # sass compiler, so there's no need to install anything else.
    'SASS_BINARY': SASSC_LOCATION
}

DATA_DIR = 'data'
PLANS_DIR = os.path.join(DATA_DIR, 'plans')
PLANS_CSV_KEY = '1tEnjJRaWsdXtCkMwA25-ZZ8D75zAY6c2GOOeUchZsnU'
PLANS_CSV_SHEET_NAME = 'Councils'
RAW_CSV_NAME = 'raw_plans.csv'
RAW_CSV = os.path.join(DATA_DIR, RAW_CSV_NAME)
PROCESSED_CSV_NAME = 'plans.csv'
PROCESSED_CSV = os.path.join(DATA_DIR, PROCESSED_CSV_NAME)


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django_filters',
    'haystack',
    'pipeline',
    'bootstrap4',
    'caps',
]

HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'haystack.backends.solr_backend.SolrEngine',
        'URL': SOLR_URL,
        'ADMIN_URL': SOLR_ADMIN_URL
    },
}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': REPOSITORY_DB_NAME,
        'USER': REPOSITORY_DB_USER,
        'PASSWORD': REPOSITORY_DB_PASS,
        'HOST': REPOSITORY_DB_HOST,
        'PORT': REPOSITORY_DB_PORT,
    }
}

MIDDLEWARE = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'htmlmin.middleware.HtmlMinifyMiddleware',
    'htmlmin.middleware.MarkRequestMiddleware',
)

ROOT_URLCONF = 'proj.urls'

WSGI_APPLICATION = 'proj.wsgi.application'

HTML_MINIFY = not DEBUG

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = False

USE_TZ = True

BOOTSTRAP4 = {
    'success_css_class': None,
}

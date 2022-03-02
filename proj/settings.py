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

STATIC_ROOT = os.path.join(BASE_DIR, "static")
STATIC_URL = "/static/"

MEDIA_ROOT = os.path.join(BASE_DIR, "media")
MEDIA_URL = "/media/"

SITE_ROOT = os.path.realpath(os.path.dirname(__file__))

ROOT_HOSTCONF = "proj.hosts"
DEFAULT_HOST = "cape"

HIDE_DEBUG_TOOLBAR = False
DEBUG = True

ALLOWED_HOSTS = [
    "127.0.0.1",
    "testserver",
    "0.0.0.0",
    "localhost",
    "councilclimatescorecards.com",
]

from conf.config import *  # stores database and key outside repo

if DEBUG:
    IS_LIVE = False
    STATICFILES_STORAGE = "pipeline.storage.NonPackagingPipelineStorage"
else:
    IS_LIVE = True
    STATICFILES_STORAGE = "pipeline.storage.PipelineManifestStorage"


LANGUAGE_CODE = "en-uk"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join(BASE_DIR, "templates"),
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "proj.universal.universal_context",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.request",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                "caps.context_processors.analytics",
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
        "vega",
        os.path.join(BASE_DIR, "vendor", "vega"),
    ),
    (
        "awesomplete",
        os.path.join(BASE_DIR, "vendor", "awesomplete"),
    ),
)

STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "pipeline.finders.PipelineFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
)

PIPELINE = {
    "STYLESHEETS": {
        "caps": {
            "source_filenames": ("caps/scss/main.scss",),
            "output_filename": "css/caps.css",
        },
        "scoring": {
            "source_filenames": ("scoring/scss/main.scss",),
            "output_filename": "css/scoring.css",
        },
    },
    "CSS_COMPRESSOR": "django_pipeline_csscompressor.CssCompressor",
    "DISABLE_WRAPPER": True,
    "COMPILERS": ("pipeline.compilers.sass.SASSCompiler",),
    "SHOW_ERRORS_INLINE": False,
    # Use the libsass commandline tool (that's bundled with libsass) as our
    # sass compiler, so there's no need to install anything else.
    "SASS_BINARY": SASSC_LOCATION,
}

DATA_DIR = "data"
PLANS_DIR = os.path.join(DATA_DIR, "plans")
PLANS_CSV_KEY = "1tEnjJRaWsdXtCkMwA25-ZZ8D75zAY6c2GOOeUchZsnU"
PLANS_CSV_SHEET_NAME = "Councils"
RAW_CSV_NAME = "raw_plans.csv"
RAW_CSV = os.path.join(DATA_DIR, RAW_CSV_NAME)
PROCESSED_CSV_NAME = "plans.csv"
PROCESSED_CSV = os.path.join(DATA_DIR, PROCESSED_CSV_NAME)

PROMISES_CSV_KEY = "1dWd8kOT4foXTvju386r1bfvf8jd5MrMaek-4DPNHs-8"
PROMISES_CSV_SHEET_NAME = "Sheet1"
PROMISES_CSV_NAME = "promises.csv"
PROMISES_CSV = os.path.join(DATA_DIR, PROMISES_CSV_NAME)

DECLARATIONS_CSV_KEY = "1fKyDs0TUwjVurpFNNR3-0IkJE-BxS1S7hT0Np8RhVFw"
DECLARATIONS_CSV_SHEET_NAME = "Council Adaptation + Ecological Emergency Data"
DECLARATIONS_CSV_NAME = "declarations.csv"
DECLARATIONS_CSV = os.path.join(DATA_DIR, DECLARATIONS_CSV_NAME)

PLAN_YEAR = 2021

PLAN_SCORECARD_DATASET_DETAILS = {
    "org": "mysociety",
    "repo": "climate_scorecard_data",
    "tag": "1.2.0",
    "private": True,
}

SCORED_PLANS_CSV_KEY = "1SctltlJq1CF6E1pmNHDzSZl29sth7NqvBuCOL5FJCJc"
SCORED_PLANS_CSV_SHEET_NAME = "Council Tracker"
SCORED_PLANS_CSV_NAME = "scored_plans.csv"
SCORED_PLANS_CSV = os.path.join(DATA_DIR, SCORED_PLANS_CSV_NAME)

TAGS_CSV_KEY = "1MwNlJIh8DhGxx3DD7oJPh8DQQqO1wt4LqcwvxnH-Agk"
TAGS_CSV_NAME = "tags.csv"
TAGS_CSV = os.path.join(DATA_DIR, TAGS_CSV_NAME)
COUNCIL_TAGS_CSV_SHEET_NAME = "Councils for Tag"
COUNCIL_TAGS_CSV_NAME = "council_tags.csv"
COUNCIL_TAGS_CSV = os.path.join(DATA_DIR, COUNCIL_TAGS_CSV_NAME)

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django_filters",
    "django_hosts",
    "haystack",
    "pipeline",
    "bootstrap4",
    "rest_framework",
    "simple_history",
    "caps",
    "scoring",
    "charting",
]

HAYSTACK_CONNECTIONS = {
    "default": {
        "ENGINE": "haystack.backends.solr_backend.SolrEngine",
        "URL": SOLR_URL,
        "ADMIN_URL": SOLR_ADMIN_URL,
    },
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": REPOSITORY_DB_NAME,
        "USER": REPOSITORY_DB_USER,
        "PASSWORD": REPOSITORY_DB_PASS,
        "HOST": REPOSITORY_DB_HOST,
        "PORT": REPOSITORY_DB_PORT,
    }
}

MIDDLEWARE = [
    "django_hosts.middleware.HostsRequestMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "htmlmin.middleware.HtmlMinifyMiddleware",
    "htmlmin.middleware.MarkRequestMiddleware",
    "django_hosts.middleware.HostsResponseMiddleware",
]

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 100,
}

ROOT_URLCONF = "proj.urls"

WSGI_APPLICATION = "proj.wsgi.application"

HTML_MINIFY = not DEBUG

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = False

USE_TZ = True

BOOTSTRAP4 = {
    "success_css_class": None,
}

if DEBUG and HIDE_DEBUG_TOOLBAR == False:
    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS = [ip[:-1] + "1" for ip in ips] + ["127.0.0.1", "10.0.2.2"]

    # debug toolbar has to come after django_hosts middleware
    MIDDLEWARE.insert(1, "debug_toolbar.middleware.DebugToolbarMiddleware")

    INSTALLED_APPS += ("debug_toolbar",)

    DEBUG_TOOLBAR_PANELS = [
        "debug_toolbar.panels.versions.VersionsPanel",
        "debug_toolbar.panels.timer.TimerPanel",
        "debug_toolbar.panels.settings.SettingsPanel",
        "debug_toolbar.panels.headers.HeadersPanel",
        "debug_toolbar.panels.request.RequestPanel",
        "debug_toolbar.panels.sql.SQLPanel",
        "debug_toolbar.panels.staticfiles.StaticFilesPanel",
        "debug_toolbar.panels.templates.TemplatesPanel",
        "debug_toolbar.panels.cache.CachePanel",
        "debug_toolbar.panels.signals.SignalsPanel",
        "debug_toolbar.panels.logging.LoggingPanel",
        "debug_toolbar.panels.redirects.RedirectsPanel",
    ]

# mainting pre 3.2 auto increment field
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

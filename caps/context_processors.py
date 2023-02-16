from django.conf import settings


def analytics(request):
    return {
        "GOOGLE_ANALYTICS": settings.GOOGLE_ANALYTICS,
        "GOOGLE_TAG_MANAGER": settings.GOOGLE_TAG_MANAGER,
        "GOOGLE_ANALYTICS_SCORECARDS": settings.GOOGLE_ANALYTICS_SCORECARDS,
    }

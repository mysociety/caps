from django.conf import settings


def analytics(request):
    return {
        "DEBUG": settings.DEBUG,
        "GOOGLE_ANALYTICS": settings.GOOGLE_ANALYTICS,
        "GOOGLE_MEASUREMENT_PROTOCOL_SECRET": settings.GOOGLE_MEASUREMENT_PROTOCOL_SECRET,
        "GOOGLE_TAG_MANAGER": settings.GOOGLE_TAG_MANAGER,
        "GOOGLE_ANALYTICS_SCORECARDS": settings.GOOGLE_ANALYTICS_SCORECARDS,
    }

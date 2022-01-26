from django.conf import settings


def analytics(request):
    return {
        "GOOGLE_ANALYTICS": settings.GOOGLE_ANALYTICS,
        "GOOGLE_ANALYTICS_SCORECARDS": settings.GOOGLE_ANALYTICS_SCORECARDS,
    }

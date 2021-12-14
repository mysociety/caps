from django.conf import settings


def analytics(request):
    return {"GOOGLE_ANALYTICS": settings.GOOGLE_ANALYTICS}

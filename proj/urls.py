from django.urls import include, path
from django.contrib import admin

from django.conf.urls.static import static
from django.conf import settings

urlpatterns = static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += [
    path("", include("caps.urls")),
]

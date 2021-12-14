from django.urls import include, path
from django.contrib import admin

import scoring.views as views

urlpatterns = [
    path('', views.HomePageView.as_view(), name='home'),
]

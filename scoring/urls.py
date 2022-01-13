from django.urls import include, path
from django.contrib import admin

import scoring.views as views

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home"),
    path('scoring/<str:council_type>/', views.HomePageView.as_view(), name='scoring'),
    path('councils/<slug:slug>/', views.CouncilView.as_view(), name='council'),
    path('questions/<slug:slug>/', views.QuestionView.as_view(), name='question'),
]

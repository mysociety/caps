from django.urls import include, path
from django.contrib import admin

import scoring.views as views

urlpatterns = [
    path('', views.HomePageView.as_view(), name='home'),
    path('scoring/<str:council_type>/', views.HomePageView.as_view(), name='scoring'),
    path('councils/<slug:slug>/', views.CouncilView.as_view(), name='council'),
    path('questions/<slug:slug>/', views.QuestionView.as_view(), name='question'),
    path('location/', views.LocationResultsView.as_view(), name='location_results'),
    path('methodology/', views.MethodologyView.as_view(), name='methodology'),
    path('about/', views.AboutView.as_view(), name='about'),
    path('contact/', views.ContactView.as_view(), name='contact'),
]

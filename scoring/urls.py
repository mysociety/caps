from django.urls import include, path
from django.contrib import admin

import scoring.views as views

urlpatterns = [
    path('', views.HomePageView.as_view(), name='home'),
    path('scoring/<str:council_type>/', views.HomePageView.as_view(), name='scoring'),
    path('councils/<slug:slug>/answers', views.CouncilAnswersView.as_view(), name='answers'),
    path('answers/<slug:slug>/', views.AnswerCouncilsView.as_view(), name='answercouncils'),
]
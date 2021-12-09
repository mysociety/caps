from django.urls import include, path
from django.contrib import admin

import league.views as views

urlpatterns = [
    path('', views.HomePageView.as_view(), name='home'),

    path('league/<str:council_type>/', views.HomePageView.as_view(), name='league'),

    path('councils/<slug:slug>/answers', views.CouncilAnswersView.as_view(), name='answers'),
    path('councils/<slug:slug>/section', views.CouncilSectionView.as_view(), name='section'),
    path('answers/<slug:slug>/', views.AnswerCouncilsView.as_view(), name='answercouncils'),
]

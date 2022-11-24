from django.urls import include, path
from django.contrib import admin
from django.conf import settings

import scoring.views as views

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home"),
    path("scoring/<str:council_type>/", views.HomePageView.as_view(), name="scoring"),
    path("councils/<slug:slug>/", views.CouncilView.as_view(), name="council"),
    path("questions/<slug:slug>/", views.QuestionView.as_view(), name="question"),
    path("location/", views.LocationResultsView.as_view(), name="location_results"),
    path("methodology/", views.MethodologyView.as_view(), name="methodology"),
    path(
        "staging-methodology2023/",
        views.Methodology2023View.as_view(),
        name="methodology2023",
    ),
    path("about/", views.AboutView.as_view(), name="about"),
    path("contact/", views.ContactView.as_view(), name="contact"),
    path(
        "how-to-use-the-scorecards/",
        views.HowToUseView.as_view(),
        name="how-to-use-the-scorecards",
    ),
    path("down/", views.DownPageView.as_view(), name="downpage"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]

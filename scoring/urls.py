from django.conf import settings
from django.contrib import admin
from django.urls import include, path

import scoring.views as views

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home"),
    path("scoring/<str:council_type>/", views.HomePageView.as_view(), name="scoring"),
    path("councils/<slug:slug>/", views.CouncilView.as_view(), name="council"),
    path("questions/<slug:slug>/", views.QuestionView.as_view(), name="question"),
    path("location/", views.LocationResultsView.as_view(), name="location_results"),
    path(
        "plan-scorecards-2022/methodology/",
        views.MethodologyView.as_view(),
        name="methodology2022",
    ),
    path(
        "methodology/",
        views.Methodology2023View.as_view(),
        name="methodology",
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
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]

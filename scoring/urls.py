from django.conf import settings
from django.contrib import admin
from django.urls import include, path

import scoring.views as views

handler404 = views.NotFoundPageView.as_view()

app_name = "scoring"
scoring_patterns = [
    path("", views.HomePageView.as_view(), name="home"),
    path("scoring/<str:council_type>/", views.HomePageView.as_view(), name="scoring"),
    path(
        "scoring/<str:council_type>/preview/",
        views.CouncilTypeTopPerformerView.as_view(),
        name="council_type_top_preview",
    ),
    path(
        "councils/<slug:slug>/preview/",
        views.CouncilPreview.as_view(),
        name="council_preview",
    ),
    path(
        "councils/<slug:slug>/preview/top-performer",
        views.CouncilPreviewTopPerfomer.as_view(),
        name="council_top_performer_preview",
    ),
    path("councils/<slug:slug>/", views.CouncilView.as_view(), name="council"),
    path("sections/<str:code>/", views.SectionView.as_view(), name="section"),
    path("sections/", views.SectionsView.as_view(), name="sections"),
    path(
        "section/<slug:slug>/top-performer/preview/",
        views.SectionTopPerformerPreview.as_view(),
        name="section_top_preview",
    ),
    path(
        "section/<slug:slug>/top-performer/<str:council>/preview/",
        views.SectionCouncilTopPerformerPreview.as_view(),
        name="section_top_council_preview",
    ),
    path(
        "section/<slug:slug>/<str:type>/preview/",
        views.SectionPreview.as_view(),
        name="section_preview",
    ),
    path("question/<str:code>/", views.QuestionView.as_view(), name="question"),
    path("location/", views.LocationResultsView.as_view(), name="location_results"),
    path(
        "methodology/",
        views.MethodologyView.as_view(),
        name="methodology",
    ),
    path("about/", views.AboutView.as_view(), name="about"),
]

non_scoring_patterns = [
    path("contact/", views.ContactView.as_view(), name="contact"),
    path(
        "how-to-use-the-scorecards/",
        views.HowToUseView.as_view(),
        name="how-to-use-the-scorecards",
    ),
    path("down/", views.DownPageView.as_view(), name="downpage"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("privacy/", views.PrivacyView.as_view(), name="privacy"),
    # used for testing page in debug mode
    path("404/", views.NotFoundPageView.as_view(), name="404"),
]

urlpatterns = [
    path("", include((scoring_patterns, "scoring"), namespace="scoring")),
    path("", include((non_scoring_patterns, "generic"), namespace="generic")),
    path(
        "plan-scorecards-2022/",
        include(("scoring2022.urls", "scoring2022"), namespace="scoring2022"),
    ),
    path(
        "<year>/", include((scoring_patterns, "year_scoring"), namespace="year_scoring")
    ),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]

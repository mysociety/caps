from django.conf import settings
from django.contrib import admin
from django.urls import include, path

import scoring.views as views

app_name = "scoring"
scoring_patterns = (
    [
        path("", views.HomePageView.as_view(), name="home"),
        path(
            "scoring/<str:council_type>/", views.HomePageView.as_view(), name="scoring"
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
        path(
            "councils/<slug:slug>/preview/top-performer-overall",
            views.CouncilPreviewTopPerformerOverall.as_view(),
            name="council_top_performer_overall_preview",
        ),
        path("councils/<slug:slug>/", views.CouncilView.as_view(), name="council"),
        path("sections/<str:code>/", views.SectionView.as_view(), name="section"),
        path("sections/", views.SectionsView.as_view(), name="sections"),
        path(
            "section/<slug:slug>/preview/",
            views.SectionPreview.as_view(),
            name="section_preview",
        ),
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
        path("privacy/", views.PrivacyView.as_view(), name="privacy"),
        path("preview/", views.ScorecardsPreviewView.as_view(), name="preview"),
    ],
    "scoring",
)
urlpatterns = [
    path("", include(scoring_patterns)),
    path(
        "plan-scorecards-2022/",
        include(("scoring2022.urls", "scoring2022"), namespace="scoring2022"),
    ),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]

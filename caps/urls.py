from django.urls import include, path
from django.contrib import admin

import caps.views as views

urlpatterns = [
    path('', views.HomePageView.as_view(), name='home'),
    path('councils/<slug:slug>/', views.CouncilDetailView.as_view(), name='council'),
    path('search/', views.SearchResultsView.as_view(), name='search_results'),
    path('councils/', views.CouncilListView.as_view(), name='council_list'),
    path('postcode/', views.PostcodeResultsView.as_view(), name='postcode_results'),
    path('admin/', admin.site.urls),
]

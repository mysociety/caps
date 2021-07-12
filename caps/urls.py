from django.urls import include, path
from django.contrib import admin

import haystack.generic_views
from caps.forms import HighlightedSearchForm
import caps.views as views

urlpatterns = [
    path('', views.HomePageView.as_view(), name='home'),
    path('councils/<slug:slug>/', views.CouncilDetailView.as_view(), name='council'),
    path('search/', views.SearchResultsView.as_view(form_class=HighlightedSearchForm), name='search_results'),
    path('councils/', views.CouncilListView.as_view(), name='council_list'),
    path('location/', views.LocationResultsView.as_view(), name='location_results'),
    path('about/', views.AboutView.as_view(), name='about'),
    path('ajax/mailchimp_email', views.MailchimpView.as_view(), name='mailchimp_hook'),
    path('admin/', admin.site.urls),

]

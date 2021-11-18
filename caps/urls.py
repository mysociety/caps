from django.urls import include, path
from django.contrib import admin

import haystack.generic_views
from caps.forms import HighlightedSearchForm
import caps.views as views
import caps.api.views as api_views
from caps.api import routers

router = routers.Router()
router.register(r'councils', api_views.CouncilViewSet, basename='council')
router.register(r'searchterms', api_views.SearchTermViewSet)
router.register(r'commitments', api_views.CommitmentsViewSet)

urlpatterns = [
    path('', views.HomePageView.as_view(), name='home'),
    path('councils/<slug:slug>/', views.CouncilDetailView.as_view(), name='council'),
    path('councils/<slug:slug>/answers', views.CouncilAnswersView.as_view(), name='answers'),
    path('search/', views.SearchResultsView.as_view(form_class=HighlightedSearchForm), name='search_results'),
    path('councils/', views.CouncilListView.as_view(), name='council_list'),
    path('location/', views.LocationResultsView.as_view(), name='location_results'),
    path('about/', views.AboutView.as_view(), name='about'),
    path('about/data/', views.AboutDataView.as_view(), name='about_data'),
    path('ajax/mailchimp_email', views.MailchimpView.as_view(), name='mailchimp_hook'),
    path('net-zero-local-hero/', views.NetZeroLocalHeroView.as_view(), name='net_zero_local_hero'),
    path('style/', views.StyleView.as_view(), name='style'),
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/councils/<str:authority_code>/commitments', api_views.CouncilCommitmentsViewSet.as_view({'get': 'list'}), name='council-commitments')

]

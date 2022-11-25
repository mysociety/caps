from cape.api.views import APIView
from rest_framework import routers


class Router(routers.DefaultRouter):
    APIRootView = APIView

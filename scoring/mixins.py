from django.contrib.auth.mixins import AccessMixin
from django.conf import settings
from django.shortcuts import redirect


class CheckForDownPageMixin(AccessMixin):
    login_url = "/login/"
    redirect_field_name = "redirect_to"

    def dispatch(self, request, *args, **kwargs):
        if not getattr(settings, "SCORECARDS_PRIVATE", False):
            return super().dispatch(request, *args, **kwargs)

        if not request.user.is_authenticated:
            return redirect("downpage")

        return super().dispatch(request, *args, **kwargs)

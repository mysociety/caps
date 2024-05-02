from django.conf import settings


class AddYearMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        year = settings.PLAN_YEAR
        if view_kwargs.get("year") is not None:
            try:
                year = int(view_kwargs["year"])
            except ValueError:
                year = settings.PLAN_YEAR

        request.year = year

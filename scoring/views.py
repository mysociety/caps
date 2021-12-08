from django.views.generic import ListView
from django.db.models import Subquery, OuterRef

from caps.models import Council
from scoring.models import PlanScore, PlanSection, PlanSectionScore

class HomePageView(ListView):
    template_name = "scoring/home.html"

    def get_queryset(self):
        sort = self.request.GET.get('sort_by')
        qs = Council.objects.annotate(
            score=Subquery(
                PlanScore.objects.filter(council_id=OuterRef('id'),year='2021').values('weighted_total')
            )
        )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        councils = context['object_list'].values()
        context['plan_sections'] = PlanSection.objects.filter(year=2021).all()

        all_scores = PlanSectionScore.get_all_council_scores()

        for council in councils:
            council['all_scores'] = all_scores[council['id']]

        codes = PlanSection.section_codes()

        context['council_data'] = councils
        return context

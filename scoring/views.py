from django.views.generic import ListView
from django.db.models import Subquery, OuterRef, Q

from caps.models import Council
from scoring.models import PlanScore, PlanSection, PlanSectionScore

from scoring.forms import ScoringSort

class HomePageView(ListView):
    template_name = "scoring/home.html"

    def get_queryset(self):
        authority_type = self.kwargs.get('council_type', '')
        qs = Council.objects.annotate(
            score=Subquery(
                PlanScore.objects.filter(council_id=OuterRef('id'),year='2021').values('weighted_total')
            )
        ).order_by('-score')

        try:
            group = Council.SCORING_GROUPS[authority_type]
        except:
            group = Council.SCORING_GROUPS['single']

        qs = qs.filter(
            authority_type__in=group['types'],
            country__in=group['countries']
        )

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        councils = context['object_list'].values()
        context['plan_sections'] = PlanSection.objects.filter(year=2021).all()

        averages = PlanSection.get_average_scores()
        all_scores = PlanSectionScore.get_all_council_scores()

        for council in councils:
            council['all_scores'] = all_scores[council['id']]
            council['percentage'] = round( ( council['score'] / averages['total']['max'] ) * 100 )

        codes = PlanSection.section_codes()

        form = ScoringSort(self.request.GET)
        if form.is_valid():
            sort = form.cleaned_data['sort_by']
            if sort != '':
                councils = sorted(councils, key=lambda council: 0 if council['score'] == 0 else council['all_scores'][sort]['score'], reverse=True)
        else:
            form = ScoringSort()

        context['form'] = form
        context['council_data'] = councils
        context['averages'] = averages
        return context

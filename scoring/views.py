from django.views.generic import ListView
from django.db.models import Subquery, OuterRef, Q

from caps.models import Council
from scoring.models import PlanScore, PlanSection, PlanSectionScore

class HomePageView(ListView):
    template_name = "scoring/home.html"

    def get_queryset(self):
        authority_type = self.kwargs.get('council_type', '')
        sort = self.request.GET.get('sort_by')
        qs = Council.objects.annotate(
            score=Subquery(
                PlanScore.objects.filter(council_id=OuterRef('id'),year='2021').values('total')
            )
        ).order_by('-score')

        if authority_type != '':
            if authority_type == 'unitary':
                qs = qs.filter(authority_type='UA')
            elif authority_type == 'district':
                qs = qs.filter(Q(authority_type='MD') | Q(authority_type='NMD'))
            elif authority_type == 'county':
                qs = qs.filter(authority_type='CTY')
            elif authority_type == 'london':
                qs = qs.filter(Q(authority_type='LBO') | Q(authority_type='CTY'))
            elif authority_type == 'combined':
                qs = qs.filter(authority_type='COMB')
            elif authority_type == 'scotland':
                qs = qs.filter(country=Council.SCOTLAND)
            elif authority_type == 'wales':
                qs = qs.filter(country=Council.WALES)
            elif authority_type == 'ni':
                qs = qs.filter(country=Council.NORTHERN_IRELAND)
            elif authority_type == 'england':
                qs = qs.filter(country=Council.ENGLAND)
        else:
            qs = qs.filter(authority_type='UA')

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

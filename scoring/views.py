from django.views.generic import ListView, DetailView
from django.db.models import Subquery, OuterRef, Q

from caps.models import Council
from scoring.models import PlanScore, PlanSection, PlanSectionScore, PlanQuestion

from scoring.forms import ScoringSort

class HomePageView(ListView):
    template_name = "scoring/home.html"

    def get_queryset(self):
        authority_type = self.kwargs.get('council_type', '')
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

        form = ScoringSort(self.request.GET)
        if form.is_valid():
            sort = form.cleaned_data['sort_by']
            if sort != '':
                councils = sorted(councils, key=lambda council: 0 if council['score'] == 0 else council['all_scores'][sort]['score'], reverse=True)
        else:
            form = ScoringSort()

        context['form'] = form
        context['council_data'] = councils
        return context

class CouncilAnswersView(DetailView):
    model = Council
    context_object_name = 'council'
    template_name = 'council_answers.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        council = context.get('council')

        plan = PlanScore.objects.get(council=council, year=2021)

        # do this in raw SQL as otherwise we need a third query and an extra loop below
        questions = PlanQuestion.objects.raw(
            "select q.id, q.code, q.text, q.question_type, q.max_score, s.code as section_code, a.answer, a.score \
            from scoring_planquestion q join scoring_plansection s on q.section_id = s.id \
            left join scoring_planquestionscore a on q.id = a.plan_question_id \
            where s.year = '2021' and ( a.plan_score_id = %s or a.plan_score_id is null) order by q.code",
            [council.id]
        )

        section_qs = PlanSectionScore.objects.select_related('plan_section').filter(
            plan_score__council=context['council'],
            plan_section__year=2021
        )

        sections = {}
        for section in section_qs.all():
            sections[section.plan_section.code] = {
                'description': section.plan_section.description,
                'max_score': section.plan_section.max_score,
                'score': section.score,
                'answers': []
            }

        for question in questions:
            section = question.section_code
            q = {
                'code': question.code,
                'display_code': question.code.replace('{}_'.format(question.section_code), ''),
                'question': question.text,
                'type': question.question_type,
                'max': question.max_score,
                'section': question.section.code,
                'answer': question.answer or '-',
                'score': question.score or 0,
            }
            sections[section]['answers'].append(q)

        context['plan'] = plan
        context['sections'] = sections
        return context

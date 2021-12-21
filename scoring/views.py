from django.views.generic import ListView, DetailView
from django.db.models import Subquery, OuterRef, Q, Avg

from caps.models import Council
from scoring.models import PlanScore, PlanSection, PlanSectionScore, PlanQuestion, PlanQuestionScore

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

class CouncilAnswersView(DetailView):
    model = Council
    context_object_name = 'council'
    template_name = 'council_answers.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        council = context.get('council')
        plan_score = PlanScore.objects.get(council=council, year=2021)

        section_qs = PlanSectionScore.objects.select_related('plan_section').filter(
            plan_score__council=council,
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

        group = council.get_scoring_group()

        # get average section scores for authorities of the same type
        section_avgs = PlanSectionScore.objects.select_related('plan_section').filter(
            plan_score__total__gt=0,
            plan_score__council__authority_type__in=group['types'],
            plan_score__council__country__in=group['countries'],
            plan_section__year=2021
        ).values('plan_section__code').annotate(avg_score=Avg('score')) #, distinct=True))

        for section in section_avgs.all():
            sections[section['plan_section__code']]['avg'] = round(section['avg_score'], 1)

        # do this in raw SQL as otherwise we need a third query and an extra loop below
        questions = PlanQuestion.objects.raw(
            "select q.id, q.code, q.text, q.question_type, q.max_score, s.code as section_code, a.answer, a.score \
            from scoring_planquestion q join scoring_plansection s on q.section_id = s.id \
            left join scoring_planquestionscore a on q.id = a.plan_question_id \
            where s.year = '2021' and ( a.plan_score_id = %s or a.plan_score_id is null) order by q.code",
            [plan_score.id]
        )

        for question in questions:
            section = question.section_code
            q = {
                'code': question.code,
                'display_code': question.code.replace('{}_'.format(question.section_code), '', 1),
                'question': question.text,
                'type': question.question_type,
                'max': question.max_score,
                'section': question.section.code,
                'answer': question.answer or '-',
                'score': question.score or 0,
            }
            sections[section]['answers'].append(q)

        context['plan_score'] = plan_score
        context['sections'] = sections
        return context

class AnswerCouncilsView(DetailView):
    model = PlanQuestion
    context_object_name = 'question'
    template_name = 'question_answers.html'
    slug_field = 'code'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        question = context.get('question')

        answers = PlanQuestionScore.objects.filter(
            plan_question=question
        ).select_related(
            'plan_score',
            'plan_score__council'
        ).order_by( "plan_score__council__name")

        context['question'] = question
        context['answers'] = answers
        return context

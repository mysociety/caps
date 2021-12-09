from django.views.generic import ListView, DetailView
from django.db.models import Subquery, OuterRef

from caps.models import Council
from league.models import PlanScore, PlanSection, PlanSectionScore, PlanQuestion, PlanQuestionScore

class HomePageView(ListView):
    template_name = "league/home.html"

    def get_queryset(self):
        authority_type = self.kwargs.get('council_type', '')
        sort = self.request.GET.get('sort_by')
        qs = Council.objects.annotate(
            score=Subquery(
                PlanScore.objects.filter(council_id=OuterRef('id'),year='2021').values('total')
            )
        ).order_by('-score')

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
            from league_planquestion q join league_plansection s on q.section_id = s.id \
            left join league_planquestionscore a on q.id = a.plan_question_id \
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
        ).select_related('plan_score', 'plan_score__council')

        context['question'] = question
        context['answers'] = answers
        return context

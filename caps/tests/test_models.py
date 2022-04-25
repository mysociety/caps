from django.test import TestCase

from caps.models import Council, PlanDocument, SavedSearch


class PlanDocumentStartEndEndYearsFromTimePeriodTestCase(TestCase):
    def test_simple_case(self):
        expected = (2020, 2030)
        actual = PlanDocument.start_and_end_year_from_time_period("2020-2030")
        self.assertEqual(expected, actual)

    def test_no_dates_set_to_none(self):
        expected = (None, None)
        actual = PlanDocument.start_and_end_year_from_time_period("Not yet published")
        self.assertEqual(expected, actual)

    def test_dates_then_text_parsed(self):
        expected = (2020, 2030)
        actual = PlanDocument.start_and_end_year_from_time_period(
            '2020-2030: "aim to become carbon neutral by 2030, and 80% by 2025."'
        )
        self.assertEqual(expected, actual)


class PlanDocumentDocumentTypeCodeTestCase(TestCase):
    def test_simple_case(self):
        expected = PlanDocument.ACTION_PLAN
        actual = PlanDocument.document_type_code("Action plan")
        self.assertEqual(expected, actual)

    def test_capitalisation_normalised(self):
        expected = PlanDocument.CLIMATE_STRATEGY
        actual = PlanDocument.document_type_code("Climate STraTegy")
        self.assertEqual(expected, actual)

    def test_invalid_entry(self):
        expected = None
        actual = PlanDocument.document_type_code("Something else")
        self.assertEqual(expected, actual)

    def test_whitespace_removed(self):
        expected = PlanDocument.ACTION_PLAN
        actual = PlanDocument.document_type_code("Action plan ")
        self.assertEqual(expected, actual)


class PlanDocumentScopeCodeTestCase(TestCase):
    def test_simple_case(self):
        expected = PlanDocument.COUNCIL_ONLY
        actual = PlanDocument.scope_code("Council only")
        self.assertEqual(expected, actual)

    def test_capitalisation_normalised(self):
        expected = PlanDocument.WHOLE_AREA
        actual = PlanDocument.scope_code("WhOle AreA")
        self.assertEqual(expected, actual)

    def test_invalid_entry(self):
        expected = None
        actual = PlanDocument.scope_code("Something else")
        self.assertEqual(expected, actual)

    def test_whitespace_removed(self):
        expected = PlanDocument.ACTION_PLAN
        actual = PlanDocument.scope_code("Council only ")
        self.assertEqual(expected, actual)


class PlanDocumentStatusCodeTestCase(TestCase):
    def test_simple_case(self):
        expected = PlanDocument.DRAFT
        actual = PlanDocument.status_code("Draft")
        self.assertEqual(expected, actual)

    def test_capitalisation_normalised(self):
        expected = PlanDocument.APPROVED
        actual = PlanDocument.status_code("aPProVed")
        self.assertEqual(expected, actual)

    def test_invalid_entry(self):
        expected = None
        actual = PlanDocument.status_code("Something else")
        self.assertEqual(expected, actual)

    def test_whitespace_removed(self):
        expected = PlanDocument.APPROVED
        actual = PlanDocument.status_code(" Approved")
        self.assertEqual(expected, actual)


class PlanDocumentBooleanFromTextTestCase(TestCase):
    def test_simple_case(self):
        expected = False
        actual = PlanDocument.boolean_from_text("N")
        self.assertEqual(expected, actual)

    def test_capitalisation(self):
        expected = True
        actual = PlanDocument.boolean_from_text("y")
        self.assertEqual(expected, actual)

    def test_yes_no(self):
        expected = True
        actual = PlanDocument.boolean_from_text("yes")
        self.assertEqual(expected, actual)

    def test_invalid_entry(self):
        expected = None
        actual = PlanDocument.boolean_from_text("yawp")
        self.assertEqual(expected, actual)


class CouncilPercentWithPlanTestCase(TestCase):
    def setUp(self):
        plan_council = Council.objects.create(
            name="Borsetshire",
            slug="borsetshire",
            authority_code="BORS",
            gss_code="E00000001",
            country=Council.ENGLAND,
        )
        plan = PlanDocument.objects.create(
            document_type=PlanDocument.ACTION_PLAN,
            council=plan_council,
            url="http://example.com",
            url_hash="xxxxxxx",
            file_type="PDF",
        )
        no_plan_council = Council.objects.create(
            name="Setborshire",
            slug="Setborshire",
            gss_code="E00000002",
            authority_code="SBOR",
            country=Council.ENGLAND,
        )
        non_plan_doc_council = Council.objects.create(
            name="West Borsetshire",
            slug="west_borsetshire",
            gss_code="E00000003",
            authority_code="WBOR",
            country=Council.ENGLAND,
        )

        not_plan = PlanDocument.objects.create(
            document_type=PlanDocument.SUMMARY_DOCUMENT,
            council=non_plan_doc_council,
            url="http://example.com",
            url_hash="xxxxxxx",
            file_type="PDF",
        )

    def test_councils_percent_with_plan(self):
        actual = Council.percent_with_plan()
        self.assertEqual(33, actual)


class SavedSearchesTestCase(TestCase):
    def setUp(self):
        search_with_results = SavedSearch.objects.create(
            user_query="turbines", result_count=12, search_key="q"
        )

        search_with_no_results = SavedSearch.objects.create(
            user_query="elephants", result_count=0, search_key="q"
        )

    def test_searches_with_no_results_ignored(self):
        recent_qs = SavedSearch.objects.most_recent()
        self.assertEqual(recent_qs.count(), 1)
        recent = [res["user_query"] for res in recent_qs]
        self.assertEqual(recent, ["turbines"])

        popular_qs = SavedSearch.objects.most_popular()
        self.assertEqual(popular_qs.count(), 1)
        popular = [res["user_query"] for res in popular_qs]
        self.assertEqual(popular, ["turbines"])

    def test_popular_searches(self):
        searches = [
            "turbines",
            "gas",
            "wind",
            "wind",
            "ev",
            "turbines",
            "solar",
            "solar",
        ]
        for search in searches:
            SavedSearch.objects.create(
                user_query=search, result_count=12, search_key="q"
            )

        popular_qs = SavedSearch.objects.most_popular()
        self.assertEqual(popular_qs.count(), 5)
        popular = [[res["user_query"], res["times_seen"]] for res in popular_qs]
        self.assertEqual(
            popular, [["turbines", 3], ["solar", 2], ["wind", 2], ["ev", 1], ["gas", 1]]
        )

        popular_qs = SavedSearch.objects.most_popular(threshold=2)
        self.assertEqual(popular_qs.count(), 3)
        popular = [[res["user_query"], res["times_seen"]] for res in popular_qs]
        self.assertEqual(popular, [["turbines", 3], ["solar", 2], ["wind", 2]])


class CouncilFoeSlugTestCase(TestCase):
    def test_london_borough(self):
        council = Council.objects.create(
            name="London Borough of Southwark",
            slug="southwark",
            country=Council.ENGLAND,
            authority_code="E1",
            authority_type="LBO",
            gss_code="E1",
            website_url="http://example.org",
        )

        self.assertEqual(council.foe_slug, "southwark")

    def test_borough(self):
        council = Council.objects.create(
            name="Ashford Borough Council",
            slug="southwark",
            country=Council.ENGLAND,
            authority_code="E1",
            authority_type="NMD",
            gss_code="E1",
            website_url="http://example.org",
        )

        self.assertEqual(council.foe_slug, "ashford")

    def test_county_is_blank(self):
        council = Council.objects.create(
            name="Oxfordshire County Council",
            slug="southwark",
            country=Council.ENGLAND,
            authority_code="E1",
            authority_type="CTY",
            gss_code="E1",
            website_url="http://example.org",
        )

        self.assertEqual(council.foe_slug, "")

    def test_unitary(self):
        council = Council.objects.create(
            name="Cornwall Council (Unitary)",
            slug="southwark",
            country=Council.ENGLAND,
            authority_code="E1",
            authority_type="UA",
            gss_code="E1",
            website_url="http://example.org",
        )

        self.assertEqual(council.foe_slug, "cornwall")

    def test_city(self):
        council = Council.objects.create(
            name="City of Leeds",
            slug="southwark",
            country=Council.ENGLAND,
            authority_code="E1",
            authority_type="MD",
            gss_code="E1",
            website_url="http://example.org",
        )

        self.assertEqual(council.foe_slug, "leeds")

    def test_ampersand(self):
        council = Council.objects.create(
            name="London Borough of Hammersmith & Fulham",
            slug="southwark",
            country=Council.ENGLAND,
            authority_code="E1",
            authority_type="LBO",
            gss_code="E1",
            website_url="http://example.org",
        )

        self.assertEqual(council.foe_slug, "hammersmith-and-fulham")

    def test_of(self):
        council = Council.objects.create(
            name="Isle of Wight",
            slug="southwark",
            country=Council.ENGLAND,
            authority_code="E1",
            authority_type="UA",
            gss_code="E1",
            website_url="http://example.org",
        )

        self.assertEqual(council.foe_slug, "isle-wight")

    def test_non_alpha(self):
        council = Council.objects.create(
            name="Somewhere's There-under-that Council",
            slug="southwark",
            country=Council.ENGLAND,
            authority_code="E1",
            authority_type="LBO",
            gss_code="E1",
            website_url="http://example.org",
        )

        self.assertEqual(council.foe_slug, "somewheres-there-under-that")

import re
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from caps.models import (
    Council,
    CouncilTag,
    EmergencyDeclaration,
    PlanDocument,
    Promise,
    Tag,
)
from scoring.models import PlanYear


class TestPageRenders(TestCase):
    def setUp(self):
        self.client = Client()
        council = Council.objects.create(
            name="Borsetshire", slug="borsetshire", country=Council.ENGLAND
        )

        PlanYear.objects.create(year=2023, is_current=True)

    def test_home_page(self):
        url = reverse("home")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "caps/home.html")

    def test_council_detail(self):
        url = reverse("council", args=["borsetshire"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "caps/council_detail.html")

    @patch("caps.forms.HighlightedSearchForm.search")
    def test_search_results(self, mock_search):
        mock_search.return_value = [], []
        url = reverse("search_results")
        response = self.client.get(url, {"q": "ev charging"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "caps/search_results.html")

    def test_council_list(self):
        url = reverse("council_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "caps/council_list.html")


class TestPostcodeSearch(TestCase):
    def setUp(self):
        Council.objects.create(
            name="Borsetshire",
            slug="borsetshire",
            country=Council.ENGLAND,
            authority_code="BOS",
            gss_code="E14000111",
        )

        Council.objects.create(
            name="Borsetshire District",
            slug="borsetshire-district",
            country=Council.ENGLAND,
            authority_code="BOD",
            gss_code="E14000222",
        )

        felpersham = Council.objects.create(
            name="Felpersham Combined Authority",
            slug="felpersham",
            country=Council.ENGLAND,
            authority_code="FEL",
            gss_code="E14000444",
        )
        Council.objects.create(
            name="Ambridge",
            slug="ambridge",
            country=Council.ENGLAND,
            authority_code="AMB",
            gss_code="E14000333",
            combined_authority=felpersham,
        )

        PlanYear.objects.create(year=2023, is_current=True)

    @patch("caps.mapit.session")
    def test_postcode_to_one_council_redirects_to_council(self, mapit_session):
        mapit_session.get.return_value.json.return_value = {
            "areas": {
                "11111": {
                    "id": 11111,
                    "codes": {"gss": "E14000111", "unit_id": "11111"},
                    "name": "Borsetshire Council",
                    "country": "E",
                    "type": "CTY",
                }
            }
        }
        response = self.client.get("/location/?pc=BO11AD", follow=True)
        self.assertRedirects(response, "/councils/borsetshire/")

    @patch("caps.mapit.session")
    def test_postcode_to_two_councils_shows_results(self, mapit_session):
        mapit_session.get.return_value.json.return_value = {
            "areas": {
                "11111": {
                    "id": 11111,
                    "codes": {"gss": "E14000111", "unit_id": "11111"},
                    "name": "Borsetshire Council",
                    "country": "E",
                    "type": "CTY",
                },
                "22222": {
                    "id": 22222,
                    "codes": {"gss": "E14000222", "unit_id": "22222"},
                    "name": "Borsetshire District",
                    "country": "E",
                    "type": "DIS",
                },
            }
        }
        response = self.client.get("/location/?pc=BO11AE", follow=True)
        self.assertTemplateUsed(response, "caps/location_results.html")

    @patch("caps.mapit.session")
    def test_postcode_to_council_and_combined_authority_shows_results(
        self, mapit_session
    ):
        mapit_session.get.return_value.json.return_value = {
            "areas": {
                "33333": {
                    "id": 33333,
                    "codes": {"gss": "E14000333", "unit_id": "33333"},
                    "name": "Ambridge",
                    "country": "E",
                    "type": "DIS",
                }
            }
        }
        response = self.client.get("/location/?pc=BO11AF", follow=True)
        self.assertTemplateUsed(response, "caps/location_results.html")

    def test_empty_submission_shows_results_page(self):
        response = self.client.get("/location/?pc=")
        self.assertTemplateUsed(response, "caps/location_results.html")


class TestCouncilDetailPage(TestCase):
    promise = None

    def setUp(self):
        council = Council.objects.create(
            name="Borsetshire",
            slug="borsetshire",
            country=Council.ENGLAND,
            authority_code="BOS",
            gss_code="E14000111",
        )

        self.promise = Promise.objects.create(
            council=council,
            has_promise=True,
            text="this is a promise",
            source_name="council website",
            source="http://borsetshire.gov.uk/promise/",
            target_year="2045",
        )

        PlanYear.objects.create(year=2023, is_current=True)

    def test_council_has_promise(self):
        url = reverse("council", args=["borsetshire"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.content, rb"this is a promise")

    def test_council_past_promises_not_shown(self):
        Promise.objects.create(
            council=self.promise.council,
            has_promise=True,
            text="this is a superseded promise",
            source="http://borsetshire.gov.uk/old-promise/",
            target_year="2050",
            status=Promise.SUPERSEDED,
        )
        Promise.objects.create(
            council=self.promise.council,
            has_promise=True,
            text="this is a withdrawn promise",
            source="http://borsetshire.gov.uk/withdrawn-promise/",
            target_year="2030",
            status=Promise.WITHDRAWN,
        )
        url = reverse("council", args=["borsetshire"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["promises"]), [self.promise])
        self.assertRegex(response.content, rb"this is a promise")
        self.assertNotRegex(response.content, rb"superseded promise")
        self.assertNotRegex(response.content, rb"withdrawn promise")

    def test_council_has_no_promise(self):
        self.promise.has_promise = False
        self.promise.save()
        url = reverse("council", args=["borsetshire"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response.content,
            rb"We couldn\xe2\x80\x99t find any climate pledges from this council",
        )

    def test_council_no_promise_data(self):
        self.promise.delete()
        url = reverse("council", args=["borsetshire"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response.content,
            rb"checked whether this council has made any climate pledges",
        )


class TestCouncilListPage(TestCase):
    def create_council(self, name, *promises):
        council = Council.objects.create(
            name=name,
            slug=name.lower().replace(" ", "-"),
            authority_code=name[:4].upper(),
            gss_code=f"E0000{Council.objects.count():04}",
            country=Council.ENGLAND,
        )
        for promise in promises:
            Promise.objects.create(council=council, has_promise=True, **promise)
        return council

    def setUp(self):
        council_ops = {"domain": Promise.COUNCIL_OPERATIONS}
        whole_area = {"domain": Promise.WHOLE_AREA}

        plan_council = self.create_council("Borsetshire")
        PlanDocument.objects.create(
            document_type=PlanDocument.ACTION_PLAN,
            council=plan_council,
            url="http://example.com",
            url_hash="xxxxxxx",
            file_type="PDF",
        )
        PlanDocument.objects.create(
            document_type=PlanDocument.CLIMATE_STRATEGY,
            council=plan_council,
            url="http://example.org",
            url_hash="xxxxxxy",
            file_type="PDF",
        )

        self.create_council(
            "Setborshire",
            {**council_ops, "target_year": 2030},
            {**whole_area, "target_year": 2050},
            # past promises, which shouldn't count
            {**whole_area, "target_year": 2025, "status": Promise.SUPERSEDED},
            {**council_ops, "target_year": 2025, "status": Promise.WITHDRAWN},
            {**council_ops, "type": Promise.WITHDRAWAL},
        )

        non_plan_doc_council = self.create_council("West Borsetshire")
        PlanDocument.objects.create(
            document_type=PlanDocument.CLIMATE_STRATEGY,
            council=non_plan_doc_council,
            url="http://example.net",
            url_hash="xxxxxxz",
            file_type="PDF",
        )
        EmergencyDeclaration.objects.create(
            council=non_plan_doc_council,
            date_declared="2020-04-20",
        )

        # fully carbon neutral once both scope targets are met
        self.create_council(
            "Scopeshire",
            {**council_ops, "scope": Promise.SCOPES_1_2, "target_year": 2030},
            {**council_ops, "scope": Promise.SCOPE_3, "target_year": 2040},
            # an unspecified scope target wins over split ones
            {**whole_area, "target_year": 2045},
            {**whole_area, "scope": Promise.SCOPES_1_2, "target_year": 2030},
            {**whole_area, "scope": Promise.SCOPE_3, "target_year": 2035},
        )
        self.create_council("Areashire", {**whole_area, "target_year": 2035})
        # only a scope 1 & 2 target, so not fully carbon neutral
        self.create_council(
            "Halfshire",
            {**council_ops, "scope": Promise.SCOPES_1_2, "target_year": 2030},
        )
        # every promise withdrawn
        self.create_council(
            "Withdrawnshire",
            {**council_ops, "target_year": 2030, "status": Promise.WITHDRAWN},
            {**council_ops, "type": Promise.WITHDRAWAL},
        )
        # checked, and no promise found
        council = self.create_council("Nopromiseshire")
        Promise.objects.create(council=council, has_promise=False)

    def get_names(self, **params):
        response = self.client.get(reverse("council_list"), params)
        return sorted(c.name for c in response.context["filter"].qs)

    def test_council_list(self):
        url = reverse("council_list")
        response = self.client.get(url)
        context = response.context
        councils = context["filter"].qs

        self.assertEqual(councils.count(), 8)
        councils = {
            council["name"]: council
            for council in councils.values("num_plans", "name", "declared_emergency")
        }

        self.assertEqual(councils["Borsetshire"]["num_plans"], 1)
        self.assertEqual(councils["Borsetshire"]["declared_emergency"], None)
        self.assertEqual(councils["Setborshire"]["num_plans"], None)
        self.assertEqual(councils["West Borsetshire"]["num_plans"], None)
        self.assertEqual(
            councils["West Borsetshire"]["declared_emergency"].strftime("%Y-%m-%d"),
            "2020-04-20",
        )

    def test_carbon_neutral_years(self):
        response = self.client.get(reverse("council_list"))
        councils = {
            council["name"]: (
                council["carbon_neutral_year_council"],
                council["carbon_neutral_year_area"],
                council["carbon_neutral_year"],
                council["promises_checked"],
            )
            for council in response.context["filter"].qs.values(
                "name",
                "carbon_neutral_year_council",
                "carbon_neutral_year_area",
                "carbon_neutral_year",
                "promises_checked",
            )
        }
        self.assertEqual(
            councils,
            {
                "Areashire": (None, 2035, 2035, True),
                "Borsetshire": (None, None, None, False),
                "Halfshire": (None, None, None, True),
                "Nopromiseshire": (None, None, None, True),
                "Scopeshire": (2040, 2045, 2040, True),
                "Setborshire": (2030, 2050, 2030, True),
                "West Borsetshire": (None, None, None, False),
                "Withdrawnshire": (None, None, None, True),
            },
        )

    def test_council_list_promise_filter(self):
        self.assertEqual(self.get_names(promise_combined="2025"), [])
        self.assertEqual(self.get_names(promise_combined="2030"), ["Setborshire"])
        self.assertEqual(
            self.get_names(promise_combined="2040"),
            ["Areashire", "Scopeshire", "Setborshire"],
        )
        self.assertEqual(
            self.get_names(promise_combined="any_promise"),
            ["Areashire", "Scopeshire", "Setborshire"],
        )
        self.assertEqual(
            self.get_names(promise_combined="no_target"),
            ["Halfshire", "Nopromiseshire", "Withdrawnshire"],
        )
        self.assertEqual(
            self.get_names(promise_combined="unknown"),
            ["Borsetshire", "West Borsetshire"],
        )

    def test_council_list_promise_filter_by_domain(self):
        self.assertEqual(
            self.get_names(promise_area="2045"),
            ["Areashire", "Scopeshire"],
        )
        self.assertEqual(
            self.get_names(promise_council="2040"),
            ["Scopeshire", "Setborshire"],
        )
        self.assertEqual(
            self.get_names(promise_area="no_target"),
            ["Halfshire", "Nopromiseshire", "Withdrawnshire"],
        )
        self.assertEqual(
            self.get_names(promise_council="no_target"),
            ["Areashire", "Halfshire", "Nopromiseshire", "Withdrawnshire"],
        )
        self.assertEqual(
            self.get_names(promise_council="unknown"),
            ["Borsetshire", "West Borsetshire"],
        )

    def test_council_list_shows_unknown_and_no_target(self):
        response = self.client.get(reverse("council_list"))
        cells = re.findall(
            rb'<a href="/councils/([a-z-]+)/">.*?data-column="promise"[^>]*>\s*([^<]*?)\s*</td>',
            response.content,
            re.DOTALL,
        )
        self.assertEqual(
            dict(cells),
            {
                b"areashire": b"2035",
                b"borsetshire": b"Unknown",
                b"halfshire": b"No target",
                b"nopromiseshire": b"No target",
                b"scopeshire": b"2040",
                b"setborshire": b"2030",
                b"west-borsetshire": b"Unknown",
                b"withdrawnshire": b"No target",
            },
        )

    def test_council_list_sort_by_promise_year(self):
        # sorting by a promise join used to list councils once per promise
        response = self.client.get(reverse("council_list"), {"sort": "promise_year"})
        names = [c.name for c in response.context["filter"].qs]
        self.assertEqual(names[:3], ["Setborshire", "Areashire", "Scopeshire"])
        self.assertEqual(len(names), 8)


class TestTagDetailPage(TestCase):
    def test_tag_page_shows_carbon_neutral_years(self):
        tag = Tag.objects.create(
            name="Tagged",
            slug="tagged",
            description_singular="tagged",
            description_plural="tagged",
            colour="red",
        )
        for name, scope, year in [
            ("Borsetshire", Promise.SCOPES_1_2, 2030),
            ("Setborshire", Promise.SCOPE_NOT_SPECIFIED, 2035),
        ]:
            council = Council.objects.create(
                name=name,
                slug=name.lower(),
                authority_code=name[:4].upper(),
                gss_code=f"E0000000{Council.objects.count()}",
                country=Council.ENGLAND,
            )
            CouncilTag.objects.create(council=council, tag=tag)
            Promise.objects.create(
                council=council,
                has_promise=True,
                domain=Promise.COUNCIL_OPERATIONS,
                scope=scope,
                target_year=year,
            )
        Council.objects.create(
            name="Untagged",
            slug="untagged",
            authority_code="UNTA",
            gss_code="E00000099",
            country=Council.ENGLAND,
        )

        response = self.client.get(reverse("tag", args=["tagged"]))
        self.assertEqual(response.status_code, 200)
        years = {
            council.name: council.carbon_neutral_year
            for council in response.context["councils"]
        }
        self.assertEqual(years, {"Borsetshire": None, "Setborshire": 2035})
        self.assertRegex(response.content, rb">\s*No target\s*<")


class TestSearchPage(TestCase):
    def test_search_results_detects_postcode(self):
        url = reverse("search_results")
        response = self.client.get(url, {"q": "EH99 1SP"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "caps/search_results.html")
        self.assertRegex(response.content, rb"Looking for your local council")


class TestMarkDownView(TestCase):
    def test_page_works(self):
        url = reverse("content", args=("mrp",))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_missing_template_404(self):
        url = reverse("content", args=("missing-template",))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

from scoring.models import PlanYearConfig

SECTION_WEIGHTINGS = {
    "Buildings & Heating": {
        "single": 20,
        "district": 25,
        "county": 20,
        "northern-ireland": 20,
    },
    "Transport": {
        "single": 20,
        "district": 5,
        "county": 30,
        "northern-ireland": 15,
    },
    "Planning & Land Use": {
        "single": 15,
        "district": 25,
        "county": 5,
        "northern-ireland": 15,
    },
    "Governance & Finance": {
        "single": 15,
        "district": 15,
        "county": 15,
        "northern-ireland": 20,
    },
    "Biodiversity": {
        "single": 10,
        "district": 10,
        "county": 10,
        "northern-ireland": 10,
    },
    "Collaboration & Engagement": {
        "single": 10,
        "district": 10,
        "county": 10,
        "northern-ireland": 10,
    },
    "Waste Reduction & Food": {
        "single": 10,
        "district": 10,
        "county": 10,
        "northern-ireland": 10,
    },
    "Transport (CA)": {
        "combined": 25,
    },
    "Buildings & Heating & Green Skills (CA)": {
        "combined": 25,
    },
    "Governance & Finance (CA)": {
        "combined": 20,
    },
    "Planning & Biodiversity (CA)": {
        "combined": 10,
    },
    "Collaboration & Engagement (CA)": {
        "combined": 20,
    },
}


ORGANISATIONS = [
    {"name": "20’s Plenty for Us"},
    {"name": "Abundance Investment"},
    {"name": "Active Travel Academy"},
    {"name": "Ad Free Cities"},
    {"name": "ADEPT"},
    {"name": "Anthesis"},
    {"name": "Architects Action Network"},
    {"name": "Association of Local Government Ecologists"},
    {"name": "Badvertising"},
    {"name": "Brighton Peace and Environment Centre"},
    {"name": "British Lung Foundation"},
    {"name": "Buglife"},
    {"name": "Campaign for Better Transport"},
    {"name": "Carbon Co-op"},
    {"name": "Chartered Institute of Public Finance and Accountancy"},
    {"name": "CLES"},
    {"name": "Climate Conversations"},
    {"name": "Climate Emergency Manchester"},
    {"name": "Climate Museum UK"},
    {"name": "Collective for Climate Action"},
    {"name": "Community Energy England"},
    {"name": "Community Rights Planning"},
    {"name": "CoMoUK"},
    {"name": "Crossing Footprints"},
    {"name": "Culture Declares Emergency"},
    {"name": "Cycle Streets"},
    {"name": "Cycling UK"},
    {"name": "Democracy Club"},
    {"name": "Department of Transport"},
    {"name": "Energy Savings Trust"},
    {"name": "Food For Life"},
    {"name": "Food Matters"},
    {"name": "Friends of the Earth"},
    {"name": "Generation Rent"},
    {"name": "Green Finance Institute"},
    {"name": "Green Flag (Keep Britain Tidy)"},
    {"name": "Institute for Local Government"},
    {"name": "Involve"},
    {"name": "Living Streets"},
    {"name": "Local Partnerships"},
    {"name": "London Cycling Campaign"},
    {"name": "Making Places Together"},
    {"name": "mySociety"},
    {"name": "National Farmers’ Union"},
    {"name": "Passivhaus Homes"},
    {"name": "Pesticides Action Network"},
    {"name": "PETA (People for the Ethical Treatment of Animals)"},
    {"name": "Place Based Carbon Calculator"},
    {"name": "Planning Aid Wales"},
    {"name": "Planning Scotland"},
    {"name": "Plantlife"},
    {"name": "Plastic Free Communities"},
    {"name": "Possible"},
    {"name": "ProVeg"},
    {"name": "Quantum Strategy & Technology"},
    {"name": "Solar Together"},
    {"name": "Southampton Climate Action Network"},
    {"name": "Sustain"},
    {"name": "Sustrans"},
    {"name": "The Campaign to Protect Rural England"},
    {"name": "The Climate Change Committee"},
    {"name": "The Soil Association"},
    {"name": "The Wildlife Trusts"},
    {"name": "Town and Country Planning Association"},
    {"name": "Trade Union Congress"},
    {"name": "Transport Action Network"},
    {"name": "Transport for New Homes"},
    {"name": "Tree Economics"},
    {"name": "Turing Institute"},
    {"name": "UK Divest"},
    {"name": "WasteDataFlow"},
    {"name": "Wirral Environmental Network"},
    {"name": "Wildlife & Countryside Link"},
    {"name": "Winchester Action on Climate Change"},
    {"name": "Zap Map"},
]

NATIONS = [
    {
        "slug": "england",
        "name": "England",
        "statistic_label": "Average Single Tier council score",
        "description": "We've summarised the key findings from across the 324 English councils and mayoral authorities to provide an overview of the results from the 2025 Council Climate Action Scorecards.",
        "description_long": """
            We’ve summarised the key findings from across the 324 English councils and mayoral authorities to provide an overview of the results from the 2025 Council Climate Action Scorecards.

            Whilst the scores vary across England, it is noticeable that, of the lowest scoring councils in the UK, 80% are in England. There are low scoring councils across all four types of English authorities: district, county, single tier and mayoral, with at least 10% of councils across each type of English authority scoring 20% or below. And, whilst most legislation is the same across all four nations, in England there is no statutory duty for councils to act on climate.
        """,
        "cta_label": "View English scores",
    },
    {
        "slug": "scotland",
        "name": "Scotland",
        "statistic_label": "Average score",
        "description": "We've summarised the key findings from across the councils in Scotland to provide a Scottish overview of these councils' results in the 2025 Council Climate Action Scorecards.",
        "description_long": """
            We've summarised the key findings from across the councils in Scotland to provide a Scottish overview of these councils' results in the 2025 Council Climate Action Scorecards.

            Whilst the scores vary across Scotland, it is noticeable that, of the lowest scoring councils in the UK, none are Welsh or Scottish. Whilst most legislation is the same across all 4 nations, in Scotland they have set a net zero target for 2045 and Scottish councils have a statutory duty to contribute towards this, as well as to report on their emissions.
        """,
        "cta_label": "View Scottish scores",
    },
    {
        "slug": "northern-ireland",
        "name": "Northern Ireland",
        "statistic_label": "Average score",
        "description": "We've summarised the key findings from the 2025 Council Climate Action Scorecards to provide a comprehensive overview of Northern Irish councils' climate action progress.",
        "description_long": """
            We’ve summarised the key findings from the 2025 Council Climate Action Scorecards  to provide an overview of Northern Irish councils’ climate action.

            The scores vary across Northern Ireland, and on average, Northern Irish councils score lower than other nations in the UK. Northern Irish councils have fewer powers than other councils in the UK in relation to schools, housing and transport. Whilst most legislation is the same across all four nations, Northern Irish and English councils (unlike in Wales and Scotland) do not have a statutory duty to work towards net zero across their whole operations or council area.
        """,
        "cta_label": "View Northern Irish scores",
    },
    {
        "slug": "wales",
        "name": "Wales",
        "statistic_label": "Average score",
        "description": "We've summarised the key findings from across the 22 councils in Wales to provide a Welsh overview of these councils' results in the 2025 Council Climate Action Scorecards.",
        "description_long": """
            We’ve summarised the key findings from across the 22 councils in Wales to provide a Welsh overview of these councils’ results in the 2025 Council Climate Action Scorecards.

            Whilst the scores vary across Wales, it is noticeable that, of the lowest scoring councils in the UK, none are Welsh or Scottish. And, whilst most legislation is the same across all 4 nations, in Wales in 2017, the Welsh Government set the ambition of achieving a carbon neutral public sector by 2030, which includes Welsh councils.
        """,
        "cta_label": "View Welsh scores",
    },
]

THEMES = [
    {
        "slug": "adaptation",
        "name": "Adaptation",
        "description": "Councils play a vital role in mitigating climate change by reducing emissions, but with increasingly frequent and more intense heatwaves, floods and wildfires, they must also lead on climate adaptation.",
        "description_long": """
            Councils play a vital role in mitigating climate change by reducing emissions, but with increasingly frequent and more intense heatwaves, floods and wildfires, they must also lead on climate adaptation. Councils can build climate resilient communities by supporting local food production, planting trees, and ensuring that both new and existing homes are climate-resilient. Embedding resilience into council policies, strategies, and engagement is essential to making adaptation a core part of council operations.

            The Scorecards include 93 questions, almost all of which contribute both to reducing emissions and increasing resilience in councils and communities. For this adaptation focused infographic, we've highlighted the questions that are most relevant to climate adaptation with the majority not featured in the other infographics.
        """,
        "cta_label": "View Adaptation",
    },
    {
        "slug": "cost-saving",
        "name": "Cost Saving",
        "description": "Climate action is sometimes misperceived as a less urgent priority when money is tight, yet so many climate actions save residents and councils money, pay for themselves in the long term, or even generate income.",
        "description_long": """
            Councils have responsibility for a wide range of services, including schools, primary care, roads, bins and housing but since 2010 in particular, the budgets available for vital services have not been keeping up with the need. Sometimes climate action is misperceived as a less urgent priority against other work at a time when money is tight, both for councils and residents.

            Yet so many climate actions save residents and councils money, or pay for themselves in the long term or even generate income.

            According to a recent study commissioned by CE UK, for every £200 per capita increase in a council's spending power, a 0.8% improvement in its Scorecards performance is observed. This shows that when given the appropriate resources, councils are able to deliver more climate action. The study also shows that local community support and political will are equally important.

            For this infographic, we've highlighted the questions that cover actions councils can take to reduce residents bills, save costs to the councils and generate income, all whilst taking action towards net zero.
        """,
        "cta_label": "View Cost Saving",
    },
]

VALID = ["NATIONS", "ORGANISATIONS", "SECTION_WEIGHTINGS", "THEMES"]

def get_config(key, year, default=None):
    conf = default
    try:
        conf = PlanYearConfig.objects.get(name=key, year__year=year).value
    except PlanYearConfig.DoesNotExist:
        u_key = key.upper()
        if u_key in VALID:
            conf = globals()[u_key]

    return conf

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

NATIONS_SOCIAL_GRAPHICS = {
    "england": {
        "pdf": {
            "src_pdf": "scoring/img/social-graphics/england/scorecards-england.pdf",
            "src_jpg": "scoring/img/social-graphics/england/england-graphic.jpg",
            "height": 1159,
            "width": 2100,
        },
        "zip": "scoring/img/social-graphics/england/england-graphics.zip",
        "images": [
            {
                "src_facebook": "scoring/img/social-graphics/england/facebook-1@2x.png",
                "src_instagram": "scoring/img/social-graphics/england/instagram-1@2x.png",
                "alt": "England Leading the Way; 79% of councils have reduced mowing or created wildflower habitat in their area; 85% of councils, including all county councils, have a named climate Portfolio Holder",
            },
            {
                "src_facebook": "scoring/img/social-graphics/england/facebook-2@2x.png",
                "src_instagram": "scoring/img/social-graphics/england/instagram-2@2x.png",
                "alt": "England Leading the Way; 83% of councils help residents retrofit their homes; 81% of councils have a Climate Action Plan with SMART targets",
            },
            {
                "src_facebook": "scoring/img/social-graphics/england/facebook-3@2x.png",
                "src_instagram": "scoring/img/social-graphics/england/instagram-3@2x.png",
                "alt": "England Room for Improvement; 60% of English planning authorities have set the highest water efficiency standards for new builds",
            },
            {
                "src_facebook": "scoring/img/social-graphics/england/facebook-4@2x.png",
                "src_instagram": "scoring/img/social-graphics/england/instagram-4@2x.png",
                "alt": "England Room for Improvement; 62% of transport authorities have low-emission buses used on routes; 62% of councils produced an annual Climate Action Plan update report",
            },
            {
                "src_facebook": "scoring/img/social-graphics/england/facebook-5@2x.png",
                "src_instagram": "scoring/img/social-graphics/england/instagram-5@2x.png",
                "alt": "England Falling Behind; 17% of English planning authorities have set net zero standards for building new housing; 7% of councils have adopted a detailed decision making process that puts the climate crisis at the heart of all council decisions",
            },
            {
                "src_facebook": "scoring/img/social-graphics/england/facebook-6@2x.png",
                "src_instagram": "scoring/img/social-graphics/england/instagram-6@2x.png",
                "alt": "England Falling Behind; Only 7 English councils recycle more than 60% of their waste; No councils are above 70% waste recycling",
            },
            {
                "src_facebook": "scoring/img/social-graphics/england/facebook-7@2x.png",
                "src_instagram": "scoring/img/social-graphics/england/instagram-7@2x.png",
                "alt": "England Falling Behind; East Devon is the only English council that produces less than 300kg of residual waste per household",
            },
            {
                "src_facebook": "scoring/img/social-graphics/england/facebook-8@2x.png",
                "src_instagram": "scoring/img/social-graphics/england/instagram-8@2x.png",
                "alt": "England Average Score by Council Type; 35% for Single Tier, 29% for District, 35% for County, 45% for Mayoral Authority",
            },
        ],
    },
    "wales": {
        "pdf": {
            "src_pdf": "scoring/img/social-graphics/wales/scorecards-wales.pdf",
            "src_jpg": "scoring/img/social-graphics/wales/wales-graphic.jpg",
            "height": 1159,
            "width": 2100,
        },
        "zip": "scoring/img/social-graphics/wales/wales-graphics.zip",
        "images": [
            {
                "src_facebook": f"scoring/img/social-graphics/wales/facebook-{i}@2x.png",
                "src_instagram": f"scoring/img/social-graphics/wales/instagram-{i}@2x.png",
                "alt": f"Wales Overview Graphic {i}",
            }
            for i in range(1, 6)  # Assuming 5 graphics
        ],
    },
}

VALID = ["NATIONS_SOCIAL_GRAPHICS", "NATIONS", "ORGANISATIONS", "SECTION_WEIGHTINGS"]


def get_config(key, year, default=None):
    conf = default
    try:
        conf = PlanYearConfig.objects.get(name=key, year__year=year).value
    except PlanYearConfig.DoesNotExist:
        u_key = key.upper()
        if u_key in VALID:
            conf = globals()[u_key]

    return conf

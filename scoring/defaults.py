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

VALID = ["ORGANISATIONS", "SECTION_WEIGHTINGS"]


def get_config(key, year, default=None):
    conf = default
    try:
        conf = PlanYearConfig.objects.get(name=key, year__year=year).value
    except PlanYearConfig.DoesNotExist:
        u_key = key.upper()
        if u_key in VALID:
            conf = globals()[u_key]

    return conf

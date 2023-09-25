from django import forms


class ScoringSort(forms.Form):
    SORT_OPTIONS = [
        ("", "Total"),
        ("s1_b_h", "Buildings & Heating"),
        ("s2_tran", "Transport"),
        ("s3_p_lu", "Planning & Land Use"),
        ("s4_g_f", "Governance & Finance"),
        ("s5_bio", "Biodiversity"),
        ("s6_c_e", "Collaboration & Engagment"),
        ("s7_wr_f", "Waste Reduction & Food"),
    ]

    sort_by = forms.ChoiceField(choices=SORT_OPTIONS, required=False)


class ScoringSortCA(forms.Form):
    SORT_OPTIONS = [
        ("", "Total"),
        ("s1_b_h_gs_ca", "Buildings & Heating & Green Skills"),
        ("s2_tran_ca", "Transport"),
        ("s3_p_b_ca", "Planning & Biodiversity"),
        ("s4_g_f_ca", "Governance & Finance"),
        ("s5_c_e", "Collaboration & Engagment"),
    ]

    sort_by = forms.ChoiceField(choices=SORT_OPTIONS, required=False)

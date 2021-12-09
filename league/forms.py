from django import forms

class LeagueSort(forms.Form):
    SORT_OPTIONS = [
        ('', 'Total'),
        ('s1_gov', 'Governance'),
        ('s2_m_a', 'Mitigation'),
        ('s3_c_a', 'Commitment'),
        ('s4_coms', 'Community'),
        ('s5_mset', 'Measuring'),
        ('s6_cb', 'Co-benefits'),
        ('s7_dsi', 'Diversity'),
        ('s8_est', 'Education'),
        ('s9_ee', 'Ecological'),
    ]

    sort_by = forms.ChoiceField(choices=SORT_OPTIONS, required=False)

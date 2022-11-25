"""
functions and pandas api to speed up working with
local authority data

"""
from functools import lru_cache
from typing import Callable, Optional, List
import string
import pandas as pd
import numpy as np

la_lookup_url = "https://raw.githubusercontent.com/mysociety/uk_local_authority_names_and_codes/main/data/uk_local_authorities.csv"
name_lookup_url = "https://raw.githubusercontent.com/mysociety/uk_local_authority_names_and_codes/main/data/lookup_name_to_registry.csv"
gss_code = "https://raw.githubusercontent.com/mysociety/uk_local_authority_names_and_codes/main/data/lookup_gss_to_registry.csv"


@lru_cache
def get_la_df(include_historical: bool = False) -> pd.DataFrame:
    """
    retrieve the big grid of all local authority details from the repo
    """
    df = pd.read_csv(la_lookup_url)
    if include_historical is False:
        df = df.loc[df["end-date"].isnull()]
    return df


@lru_cache
def gss_registry_lookup(allow_none: bool = False) -> Callable:
    """
    retrieve a function that can be applied to convert gss codes to
    three letter codes
    """
    df = pd.read_csv(gss_code)
    df["gss-code"] = df["gss-code"].str.strip()
    lookup = df.set_index("gss-code")["local-authority-code"].to_dict()

    def convert(v):
        v = v.strip()
        result = lookup.get(v, None)
        if result is None and allow_none is False:
            raise ValueError(f"{v} not found in gss column")
        return result

    return convert


def remove_punctuations(text):
    for punctuation in string.punctuation + string.whitespace:
        text = text.replace(punctuation, "")
    return text


@lru_cache
def name_registry_lookup(allow_none: bool = False) -> Callable:
    """
    returns a function that will convert the name to 3-letter reg code
    """

    banned_words = ["council", "unitary"]

    df = pd.read_csv(name_lookup_url)
    df["la name"] = df["la name"].str.lower().str.strip()
    for b in banned_words:
        df["la name"] = df["la name"].str.replace(b, "", regex=False)
    df["la name"] = df["la name"].apply(remove_punctuations)
    lookup = df.set_index("la name")["local-authority-code"].to_dict()

    def convert(v):
        if isinstance(v, str) is False:
            v = str(v)
        v_lower = v.lower().strip()
        for b in banned_words:
            v_lower = v_lower.replace(b, "")
        v_lower = remove_punctuations(v_lower)
        result = lookup.get(v_lower, None)
        if result is None and allow_none is False:
            raise ValueError(f"{v_lower} not found in name column")
        return result

    return convert


@pd.api.extensions.register_dataframe_accessor("la")
class LAPDAccessor(object):
    """
    extention to pandas dataframe
    """

    def __init__(self, pandas_obj):
        self._obj = pandas_obj

    def get_council_info(
        self,
        items: Optional[List[str]] = None,
        merge_type: str = "left",
        include_historical: bool = False,
    ) -> pd.DataFrame:
        """
        retrieve columns from comparison LA spreadsheet.
        Set merge_type to right to expand to include authorities not
        in the original dataset
        """

        df = self._obj
        if "local-authority-code" not in df.columns:
            df = df.la.create_code_column()
        adf = get_la_df(include_historical=include_historical)
        if items:
            adf = adf[["local-authority-code"] + items]
        return df.merge(adf, how=merge_type)

    def just_lower_tier(self) -> pd.DataFrame:
        """
        return just lower tier and unitary rows from the current dataframe
        """
        higher_codes = ["CTY", "COMB", "SRA"]
        df = self._obj
        added = False
        if "local-authority-type" not in df.columns:
            df = df.la.get_council_info(["local-authority-type"])
            added = True
        lower_mask = ~df["local-authority-type"].isin(higher_codes)
        if added:
            df = df.drop(columns=["local-authority-type"])
        return df.loc[lower_mask]

    def create_code_column(
        self,
        from_type: str = "name",
        source_col: Optional[str] = None,
        code_col_name: str = "local-authority-code",
        allow_none: bool = False,
    ) -> pd.DataFrame:
        """
        Create registry code column
        """
        if from_type == "name":
            lookup_func = name_registry_lookup(allow_none)
        elif from_type == "gss":
            lookup_func = gss_registry_lookup(allow_none)
        else:
            raise ValueError(f"Unaccepted from type '{from_type}'")
        df = self._obj
        if source_col is None:
            for col in df.columns:
                first_value = df[col].iloc[0]
                try:
                    lookup_func(first_value)
                    source_col = col
                    break
                except ValueError:
                    pass
        if source_col is None:
            raise ValueError(
                "Could not find a column with a valid name in the first row"
            )

        df[code_col_name] = df[source_col].apply(lookup_func)

        return df

    def to_current(
        self,
        columns: Optional[List[str]] = None,
        aggfunc="sum",
        weight_on: Optional[str] = None,
        comparison_column: str = "replaced-by",
        upgrade_absent: bool = True,
    ) -> pd.DataFrame:
        """
        If given values by primary authority, this may be former authorities.
        This uses the lookup of how authorities were merged to update this data.
        the aggfunc is anything pandas .agg function can expect. So 'mean', 'sum',
        or a custom function that returns a dataframe from a series input.
        'weight_on' will give a mean that's been weighted by a column in the lookup table.
        Good values are 'pop_2020' or 'area'
        """
        df = self._obj
        cols_to_fetch = [comparison_column]
        if columns is None:
            columns = list(df.columns)
        if aggfunc != "mean" and weight_on:
            raise ValueError("If using weight_on must also use mean.")
        if weight_on:

            def aggfunc(x):
                return np.average(x, weights=df.loc[x.index, weight_on])

            cols_to_fetch.append(weight_on)
        df = df.la.get_council_info(
            cols_to_fetch,
            include_historical=True,
        )
        if weight_on:
            df[weight_on] = df[weight_on].fillna(1)
        if upgrade_absent:
            df[comparison_column] = np.where(
                df[comparison_column].isna(),
                df["local-authority-code"],
                df[comparison_column],
            )
        return (
            df[[comparison_column] + columns]
            .groupby(comparison_column)
            .agg(aggfunc)
            .rename_axis(index="local-authority-code")
            .reset_index()
        )

    def to_higher(
        self,
        columns: Optional[List[str]] = None,
        aggfunc="mean",
        weight_on: Optional[str] = None,
        comparison_column: str = "county-la",
        upgrade_absent: bool = False,
    ) -> pd.DataFrame:
        """
        If given values by primary authority, we may want the overlapping authorities
        (upper level, regional partnerships, etc)
        This uses the lookup of how authorities were merged to update this data.
        the aggfunc is anything pandas .agg function can expect. So 'mean', 'sum',
        or a custom function that returns a dataframe from a series input.
        'weight_on' will give a mean that's been weighted by a column in the lookup table.
        Good values are 'pop_2020' or 'area'
        """
        return self.to_current(
            columns, aggfunc, weight_on, comparison_column, upgrade_absent
        )


@pd.api.extensions.register_series_accessor("la")
class LASeriesAccessor(object):
    """
    extention to python series to more easily work with local authority data
    """

    def __init__(self, pandas_obj):
        self._obj = pandas_obj

    def name_to_code(self, allow_none=False) -> pd.Series:
        """
        convert a column of local authority names to 3 letter code
        """
        return self._obj.apply(name_registry_lookup(allow_none))

    def gss_to_code(self, allow_none=False) -> pd.Series:
        """
        convert a column of gss codes to local authority names
        """
        return self._obj.apply(gss_registry_lookup(allow_none))

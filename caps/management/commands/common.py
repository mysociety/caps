import pandas as pd
from functools import lru_cache, wraps


def get_dataset_url(repo: str, package: str, version: str, file: str):
    """
    Get url to a dataset from the mysociety.github.io website.
    """
    return f"https://mysociety.github.io/{repo}/data/{package}/{version}/{file}"


def get_dataset_df(repo: str, package: str, version: str, file: str):
    """
    Get a dataframe from a dataset from the mysociety.github.io website.
    """
    url = get_dataset_url(repo, package, version, file)
    return pd.read_csv(url)


def cache_and_wrap(func):
    cached_function = lru_cache(func)

    @wraps(func)
    def inner(*args, **kwargs):
        return cached_function(*args, **kwargs)

    return inner

from __future__ import annotations

import string
from dataclasses import dataclass, field
from hashlib import md5
from typing import Dict, Iterable, List, Union
from urllib.parse import urlencode, urlparse, urlunparse

import altair as alt
import pandas as pd
from cryptography.fernet import Fernet
from django.conf import settings
from pandas.io.formats.style import Styler


@dataclass
class ChartBundle:
    """
    The chart bundle contains the dataframe and the altair chart.
    To create multiple-rendering options.

    """

    label: str
    alt_title: str
    df: Union[pd.DataFrame, Styler]
    chart: alt.Chart
    logo_src: str = "/static/charting/img/mysociety-logo-white-background.jpg"
    data_source: str = ""
    spec: str = field(init=False)
    ident: str = field(init=False)
    image_url: str = field(init=False)

    def __post_init__(self):
        self.spec = self.chart.to_json()
        self.ident = self.get_ident()
        self.image_url = ""
        # Commented out until URI length issue resolved
        # self.image_url = self.get_image_url()

    def get_ident(self) -> str:
        encoded_spec = self.spec.encode("utf-8")
        hash = md5(encoded_spec).hexdigest()
        ident = ""
        for h in hash:
            if h in string.digits:
                ident += chr(65 + 8 + int(h))
            else:
                ident += h

        return ident[:6]

    def get_image_url(self) -> str:
        """
        get url for server image
        """

        encrypt = False
        spec = self.spec
        if settings.VEGALITE_ENCRYPT_KEY:
            key = settings.VEGALITE_ENCRYPT_KEY.encode()
            spec = Fernet(key).encrypt(spec.encode())
            encrypt = True

        parameters = urlencode(
            {"spec": spec, "format": "png", "encrypted": encrypt, "width": 700}
        )
        url_parts = list(urlparse(settings.VEGALITE_SERVER_URL))
        url_parts[2] = "convert_spec"
        url_parts[4] = parameters
        return urlunparse(url_parts)


@dataclass
class ChartCollection:
    items: Dict[str, ChartBundle] = field(default_factory=dict)

    def register(self, item: ChartBundle) -> ChartCollection:
        self.items[item.label] = item
        return self

    def __getitem__(self, label: str) -> ChartBundle:
        return self.items[label]

    def __iter__(self) -> Iterable[ChartBundle]:
        return iter(self.items.values())

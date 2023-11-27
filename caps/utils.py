import os
import re
import dateutil.parser
import pandas as pd


def convert_bytes(num):
    """
    this function will convert bytes to MB.... GB... etc
    """
    for x in ["bytes", "KB", "MB", "GB", "TB"]:
        if num < 1024.0:
            return "%3.1f %s" % (num, x)
        num /= 1024.0


def file_size(file_path):
    """
    this function will return the file size
    """
    if os.path.isfile(file_path):
        file_info = os.stat(file_path)
        return convert_bytes(file_info.st_size)


def is_valid_postcode(postcode):
    pc = postcode.upper().replace(" ", "")

    # See http://www.govtalk.gov.uk/gdsc/html/noframes/PostCode-2-1-Release.htm
    in_re = "ABDEFGHJLNPQRSTUWXYZ"
    fst = "ABCDEFGHIJKLMNOPRSTUWYZ"
    sec = "ABCDEFGHJKLMNOPQRSTUVWXY"
    thd = "ABCDEFGHJKSTUW"
    fth = "ABEHMNPRVWXY"

    patterns = [
        rf"^[{fst}][1-9]\d[{in_re}][{in_re}]$",
        rf"^[{fst}][1-9]\d\d[{in_re}][{in_re}]$",
        rf"^[{fst}][{sec}]\d\d[{in_re}][{in_re}]$",
        rf"^[{fst}][{sec}][1-9]\d\d[{in_re}][{in_re}]$",
        rf"^[{fst}][1-9][{thd}]\d[{in_re}][{in_re}]$",
        rf"^[{fst}][{sec}][1-9][{fth}]\d[{in_re}][{in_re}]$",
    ]

    for pat in patterns:
        if re.search(pat, pc):
            return pc

    return None


def date_from_text(date_entry):
    """
    Return a date object given a text date, or none if there is no parsable
    date. This will strip any time information from the parsed date.
    """
    if pd.isnull(date_entry):
        return None
    return dateutil.parser.parse(date_entry, dayfirst=True).date()


def integer_from_text(entry):
    """
    Return a value from a pandas data field is it's not null
    """
    if pd.isnull(entry):
        return None
    else:
        return entry


def char_from_text(entry):
    """
    Return a value from a pandas data field is it's not null
    """
    if pd.isnull(entry):
        return ""
    else:
        return entry


def boolean_from_text(entry):
    """
    Return a boolean value given a text description, or None if the
    description isn't a coercible entry
    """
    if pd.isnull(entry):
        return None
    descriptions_to_booleans = {"y": True, "n": False, "yes": True, "no": False}
    return descriptions_to_booleans.get(entry.strip().lower())


def gen_natsort_lamda(keyfunc=None):
    if keyfunc is None:
        keyfunc = lambda k: k

    return lambda q: [
        int(t) if t.isdigit() else t.lower() for t in re.split("(\d+)", keyfunc(q))
    ]


def clean_links(links: str):
    # Evidence "links" can be one of:
    # - an empty line
    # - a string like "Airports:"
    # - a string like "www.whatever.com/…"
    # - a string like "http://www…"
    # So attempt to tidy them up, before passing to
    # a template filter like domain_human or urlizetrunc.
    link_list = []
    for line in links.splitlines():
        if line == "":
            pass
        elif line.startswith("www."):
            link_list.append(f"http://{line}")
        else:
            link_list.append(line)
    return link_list

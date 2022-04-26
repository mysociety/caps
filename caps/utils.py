import os
import re


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
        rf"^[{fst}][1-9][$thd]\d[{in_re}][{in_re}]$",
        rf"^[{fst}][{sec}][1-9][{fth}]\d[{in_re}][{in_re}]$",
    ]

    for pat in patterns:
        if re.search(pat, pc):
            return pc

    return None

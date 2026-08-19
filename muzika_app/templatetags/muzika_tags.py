# muzika_app/templatetags/muzika_tags.py
from django import template
import re

register = template.Library()


@register.filter
def get_item(dictionary, key):
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.filter
def pluralize_lt(value, forms):
    """
    Lietuviška daugiskaita. Pateikiamos 3 formos, atskirtos kableliais:
    "vienaskaita,daugiskaita,kilmininkas" pvz. "daina,dainos,dainų".

    Taisyklės:
    - baigiasi 1 (bet ne 11): 1 forma  -> 1 daina, 21 daina
    - baigiasi 2-9 (bet ne 12-19): 2 forma -> 2 dainos, 24 dainos
    - baigiasi 0 arba 11-19: 3 forma -> 0 dainų, 11 dainų, 10 dainų
    """
    try:
        n = int(value)
    except (ValueError, TypeError):
        return ""

    parts = forms.split(",")
    if len(parts) != 3:
        return forms

    singular, plural, genitive = parts
    n = abs(n)
    last_two = n % 100
    last = n % 10

    if last == 0 or 11 <= last_two <= 19:
        return genitive
    elif last == 1:
        return singular
    else:
        return plural


@register.filter
def youtube_id(url):
    """
    Ištraukia YouTube vaizdo įrašo ID iš įvairių nuorodų formatų:
    - https://www.youtube.com/watch?v=VIDEOID
    - https://youtu.be/VIDEOID
    - https://www.youtube.com/embed/VIDEOID
    - https://www.youtube.com/shorts/VIDEOID
    - https://www.youtube.com/live/VIDEOID
    Grąžina video ID arba tuščią eilutę.
    """
    if not url:
        return ""
    patterns = [
        r"(?:youtube\.com/watch\?(?:.*&)?v=)([\w-]{11})",
        r"(?:youtu\.be/)([\w-]{11})",
        r"(?:youtube\.com/embed/)([\w-]{11})",
        r"(?:youtube\.com/shorts/)([\w-]{11})",
        r"(?:youtube\.com/live/)([\w-]{11})",
        r"(?:youtube\.com/v/)([\w-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return ""


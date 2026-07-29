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
    """Lietuviska daugiskaita: "vienaskaita,daugiskaita,kilmininkas"."""
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
    """Istraukia YouTube video ID is ivairiu nuoroda formatu."""
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

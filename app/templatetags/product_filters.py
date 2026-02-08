import json
from django.utils.safestring import mark_safe
from django import template

register = template.Library()


@register.filter
def to_json(value):
    """Serialize a list/dict to JSON for use in data attributes. Returns empty array string for invalid values."""
    if value is None:
        return mark_safe("[]")
    try:
        out = json.dumps(value)
        return mark_safe(out)
    except (TypeError, ValueError):
        return mark_safe("[]")

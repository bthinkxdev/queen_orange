import json
from django.utils.safestring import mark_safe
from django import template

register = template.Library()


@register.filter
def price_inr(value):
    """Format decimal as Indian price: '₹ 1,299' (integer only, with comma)."""
    if value is None:
        return "₹ 0"
    try:
        n = int(float(value))
        s = str(n)
        if len(s) > 3:
            parts = []
            while s:
                parts.append(s[-3:])
                s = s[:-3]
            s = ",".join(reversed(parts))
        return f"₹ {s}"
    except (TypeError, ValueError):
        return "₹ 0"


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

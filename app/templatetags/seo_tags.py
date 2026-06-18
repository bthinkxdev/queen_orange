from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def absolute_uri(context, location=""):
    """Build an absolute URL for Open Graph / social sharing."""
    request = context.get("request")
    if not request:
        return location
    return request.build_absolute_uri(location)

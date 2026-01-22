"""
Template filters for file utilities
"""
import os
from django import template

register = template.Library()


@register.filter
def file_exists(image_field):
    """
    Check if an ImageField file actually exists on disk
    Usage: {% if form.instance.image|file_exists %}
    """
    if not image_field:
        return False
    
    try:
        # Check if the field has a name (file reference exists)
        if not image_field.name:
            return False
        
        # Get the full path to the file
        file_path = image_field.path
        return os.path.exists(file_path) and os.path.isfile(file_path)
    except (ValueError, AttributeError, OSError):
        # If path doesn't exist, field is empty, or file system error
        return False


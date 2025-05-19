from django import template
from django.template.defaultfilters import filesizeformat as default_filesizeformat

register = template.Library()

@register.filter(name='filesizeformat')
def filesizeformat(bytes_value):
    """Format rozmiaru pliku w czytelną postać"""
    if not bytes_value:
        return '-'
    return default_filesizeformat(bytes_value)
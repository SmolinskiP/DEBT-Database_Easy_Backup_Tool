from django import template

register = template.Library()

@register.filter(name='add_class')
def add_class(value, arg):
    """Dodaje klasę CSS do pola formularza"""
    return value.as_widget(attrs={'class': arg})
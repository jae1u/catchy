from __future__ import annotations

from django import template
from django.forms import BoundField, Form

register = template.Library()


@register.filter(name="getfield")
def getfield(form: Form, name: str) -> BoundField | None:
    if name in form.fields:
        return form[name]
    return None

from django import template

register = template.Library()

_COMPANY_TYPE_LABELS = {
    "manufacturing": {"pl": "produkcyjna", "en": "manufacturing"},
    "services": {"pl": "usługowa", "en": "services"},
    "trading": {"pl": "handlowa", "en": "trading"},
}


@register.filter
def company_type_label(company_type, language_code):
    lang = "pl" if language_code == "pl" else "en"
    return _COMPANY_TYPE_LABELS.get(company_type, {"pl": "inna", "en": "other"})[lang]

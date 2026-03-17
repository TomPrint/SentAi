from django import forms

from .models import Organization


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = [
            "name",
            "slug",
            "legal_name",
            "website_url",
            "contact_email",
            "phone_number",
            "address_line",
            "city",
            "postal_code",
            "country",
            "primary_language",
            "short_description_en",
            "short_description_pl",
            "long_description_en",
            "long_description_pl",
            "public",
            "allow_ai_indexing",
        ]
        widgets = {
            "long_description_en": forms.Textarea(attrs={"rows": 5}),
            "long_description_pl": forms.Textarea(attrs={"rows": 5}),
        }

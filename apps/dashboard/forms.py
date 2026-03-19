from django import forms

from apps.accounts.models import USER_PLAN_ORGANIZATION_LIMITS, UserPlanTier


class UserPlanUpdateForm(forms.Form):
    plan_tier = forms.ChoiceField(
        choices=UserPlanTier.choices,
        widget=forms.RadioSelect(attrs={"class": "plan-tier-radio"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if self.user and not self.is_bound:
            self.fields["plan_tier"].initial = self.user.plan_tier

    def clean_plan_tier(self):
        selected_tier = self.cleaned_data["plan_tier"]
        if not self.user or self.user.is_superuser:
            return selected_tier

        current_count = self.user.organizations.count()
        new_limit = USER_PLAN_ORGANIZATION_LIMITS[selected_tier]
        if current_count > new_limit:
            raise forms.ValidationError(
                f"You currently have {current_count} company pages. "
                f"Please reduce to {new_limit} or fewer before selecting this plan."
            )
        return selected_tier

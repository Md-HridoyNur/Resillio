from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import Profile

PORTALS = [
    ("admin", "Administrator"),
    ("coordinator", "NGO / Relief Officer"),
    ("volunteer", "Volunteer"),
]


class RegistrationForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=[
            ("volunteer", "Volunteer"),
            ("coordinator", "NGO / Relief Officer"),
            ("community", "Community / Donor"),
        ]
    )
    organization = forms.CharField(
        max_length=120,
        required=False,
        label="Organization / NGO name",
        help_text="Required for officer applications. An administrator must approve officer access.",
    )
    area = forms.CharField(max_length=100, required=False, label="Primary area")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "first_name", "email", "role", "organization", "area"]

    def clean(self):
        data = super().clean()
        if data.get("role") == "coordinator" and not data.get("organization"):
            self.add_error("organization", "Enter your organization / NGO name.")
        return data

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            from .services import area

            Profile.objects.create(
                user=user,
                role=self.cleaned_data["role"],
                organization=self.cleaned_data.get("organization", ""),
                area=area(self.cleaned_data.get("area", "")),
            )
        return user


class PortalAuthenticationForm(AuthenticationForm):
    """Portal choice never grants permission; the stored account role is authoritative."""

    def clean(self):
        data = super().clean()
        user = self.get_user()
        portal = self.request.POST.get("portal") or self.request.GET.get("portal", "")
        if user and portal:
            profile = Profile.objects.filter(user=user).first()
            role = (
                "admin" if user.is_staff else (profile.role if profile else "community")
            )
            if (
                portal not in ["admin", "coordinator", "volunteer", "community"]
                or role != portal
            ):
                raise forms.ValidationError(
                    "This account belongs to a different portal. Choose its account type below."
                )
        return data

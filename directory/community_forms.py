"""Forms for the additive community, security, and data-quality features."""

from django import forms

from .models import AlumniStory, CommunityGroup, GroupPost, Resource


class SavedSearchForm(forms.Form):
    name = forms.CharField(max_length=100)
    query = forms.CharField(
        max_length=500,
        required=False,
        help_text="Optional alumni search query string, for example batch=080&field_of_study=BCT.",
    )


class CommunityGroupForm(forms.ModelForm):
    class Meta:
        model = CommunityGroup
        fields = ["name", "description", "batch", "program", "is_public"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class GroupPostForm(forms.ModelForm):
    class Meta:
        model = GroupPost
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 3})}


class StoryForm(forms.ModelForm):
    class Meta:
        model = AlumniStory
        fields = ["title", "body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 8})}


class SkillForm(forms.Form):
    name = forms.CharField(max_length=100, label="Skill")
    level = forms.ChoiceField(choices=(("basic", "Basic"), ("working", "Working knowledge"), ("advanced", "Advanced")))


class ResourceForm(forms.ModelForm):
    class Meta:
        model = Resource
        fields = ["title", "description", "category", "url"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class ApiTokenForm(forms.Form):
    name = forms.CharField(max_length=100, help_text="Use a name such as Reporting integration.")


class ConflictReviewForm(forms.Form):
    status = forms.ChoiceField(choices=(("resolved", "Resolve"), ("ignored", "Ignore")))
    resolution_note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class SecurityCodeForm(forms.Form):
    code = forms.CharField(max_length=6, min_length=6, label="Verification code")

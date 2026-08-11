from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    # Keep the allauth signup URL on the roll-number registration flow so
    # every account has a linked alumni record and can use roll-number login.
    path("signup/", views.register, name="signup"),
    path("register/", views.register, name="register"),
    path("claim/", views.claim_record, name="claim-record"),
    path("profile/edit/", views.edit_profile, name="edit-profile"),
]

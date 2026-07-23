from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("claim/", views.claim_record, name="claim-record"),
    path("profile/edit/", views.edit_profile, name="edit-profile"),
]

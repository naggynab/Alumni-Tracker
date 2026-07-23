from django.urls import path

from . import views

app_name = "directory"

urlpatterns = [
    path("", views.home, name="home"),
    path("alumni/", views.alumni_list, name="alumni-list"),
    path("alumni/<int:pk>/", views.alumnus_detail, name="alumnus-detail"),
    path("me/", views.my_profile, name="my-profile"),
]

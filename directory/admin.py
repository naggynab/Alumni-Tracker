from django.contrib import admin

from .models import Alumnus


@admin.register(Alumnus)
class AlumnusAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "batch",
        "field_of_study",
        "current_city",
        "current_country",
        "employer_organization",
        "is_claimed",
    )
    list_filter = ("field_of_study", "batch", "current_country", "employment_status", "is_public")
    search_fields = (
        "first_name",
        "middle_name",
        "last_name",
        "employer_organization",
        "current_city",
        "class_roll_no",
    )
    list_per_page = 50
    autocomplete_fields = ()
    raw_id_fields = ("user_account",)

    @admin.display(boolean=True, description="Claimed")
    def is_claimed(self, obj):
        return obj.is_claimed

from django.contrib import admin
from django.conf import settings
from django.contrib.auth.models import Group

from .models import (
    AlumniEvent,
    Alumnus,
    ClaimReview,
    ContactRequest,
    CorrectionRequest,
    EventRegistration,
    FollowUp,
    JobPosting,
    MentorshipProfile,
    MentorshipRequest,
    ActivityLog,
    AlumniFavorite,
    AlumniSkill,
    AlumniStory,
    ApiToken,
    CommunityGroup,
    DataConflict,
    FurtherStudy,
    GroupMembership,
    GroupPost,
    Notification,
    Resource,
    SavedSearch,
    Skill,
    SkillEndorsement,
    Survey,
    SurveyResponse,
    TwoFactorCode,
    TwoFactorSetting,
)


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
    actions = ("grant_department_officers",)

    @admin.display(boolean=True, description="Claimed")
    def is_claimed(self, obj):
        return obj.is_claimed

    @admin.action(description="Grant Department Report access to linked users")
    def grant_department_officers(self, request, queryset):
        group, _created = Group.objects.get_or_create(name=settings.DEPARTMENT_GROUP_NAME)
        users = [record.user_account for record in queryset if record.user_account_id]
        group.user_set.add(*users)
        self.message_user(request, f"Granted access to {len(users)} linked user(s).")


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ("alumnus", "status", "reason", "next_contact_at", "updated_at")
    list_filter = ("status", "next_contact_at")
    search_fields = ("alumnus__first_name", "alumnus__last_name", "alumnus__class_roll_no")
    raw_id_fields = ("alumnus", "created_by", "updated_by")


@admin.register(FurtherStudy)
class FurtherStudyAdmin(admin.ModelAdmin):
    list_display = ("alumnus", "degree_level", "degree", "institution", "country")
    list_filter = ("degree_level", "country")
    search_fields = ("alumnus__first_name", "alumnus__last_name", "institution", "degree")
    raw_id_fields = ("alumnus",)


@admin.register(ClaimReview)
class ClaimReviewAdmin(admin.ModelAdmin):
    list_display = ("alumnus", "claimant", "status", "reviewer", "created_at", "reviewed_at")
    list_filter = ("status",)
    search_fields = ("alumnus__first_name", "alumnus__last_name", "alumnus__class_roll_no")
    raw_id_fields = ("alumnus", "claimant", "reviewer")


@admin.register(CorrectionRequest)
class CorrectionRequestAdmin(admin.ModelAdmin):
    list_display = ("alumnus", "field_name", "status", "requester", "created_at", "reviewed_at")
    list_filter = ("status", "field_name")
    search_fields = ("alumnus__first_name", "alumnus__last_name", "alumnus__class_roll_no")
    raw_id_fields = ("alumnus", "requester", "reviewer")


@admin.register(MentorshipProfile)
class MentorshipProfileAdmin(admin.ModelAdmin):
    list_display = ("alumnus", "headline", "is_available", "max_mentees", "updated_at")
    list_filter = ("is_available",)
    search_fields = ("alumnus__first_name", "alumnus__last_name", "expertise")
    raw_id_fields = ("alumnus",)


@admin.register(MentorshipRequest)
class MentorshipRequestAdmin(admin.ModelAdmin):
    list_display = ("mentor", "mentee", "status", "created_at", "responded_at")
    list_filter = ("status",)
    search_fields = ("mentor__first_name", "mentor__last_name", "mentee__first_name", "mentee__last_name")
    raw_id_fields = ("mentor", "mentee")


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ("title", "organization", "employment_type", "status", "deadline", "created_at")
    list_filter = ("status", "employment_type")
    search_fields = ("title", "organization", "description")
    raw_id_fields = ("posted_by", "reviewed_by")


@admin.register(AlumniEvent)
class AlumniEventAdmin(admin.ModelAdmin):
    list_display = ("title", "starts_at", "location", "status", "organizer")
    list_filter = ("status", "starts_at")
    search_fields = ("title", "description", "location")
    raw_id_fields = ("organizer", "reviewed_by")


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ("event", "attendee", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("event__title", "attendee__email")
    raw_id_fields = ("event", "attendee")


@admin.register(ContactRequest)
class ContactRequestAdmin(admin.ModelAdmin):
    list_display = ("sender", "recipient", "status", "created_at", "responded_at")
    list_filter = ("status",)
    search_fields = ("sender__email", "recipient__email", "message")
    raw_id_fields = ("sender", "recipient")


@admin.register(CommunityGroup)
class CommunityGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "batch", "program", "is_public", "created_at")
    list_filter = ("is_public", "batch", "program")
    search_fields = ("name", "description", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(GroupPost)
class GroupPostAdmin(admin.ModelAdmin):
    list_display = ("group", "author", "is_hidden", "created_at")
    list_filter = ("is_hidden", "group")
    search_fields = ("body",)
    raw_id_fields = ("group", "author")


@admin.register(AlumniStory)
class AlumniStoryAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "author", "created_at", "reviewed_at")
    list_filter = ("status",)
    search_fields = ("title", "body")
    raw_id_fields = ("author", "reviewed_by")


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "status", "submitted_by", "created_at")
    list_filter = ("status", "category")
    search_fields = ("title", "description", "url")
    raw_id_fields = ("submitted_by", "reviewed_by")


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "created_by", "created_at", "closes_at")
    list_filter = ("status",)
    search_fields = ("title", "description")
    raw_id_fields = ("created_by",)


admin.site.register([
    ActivityLog,
    AlumniFavorite,
    AlumniSkill,
    ApiToken,
    GroupMembership,
    Notification,
    SavedSearch,
    Skill,
    SkillEndorsement,
    SurveyResponse,
    TwoFactorCode,
    TwoFactorSetting,
    DataConflict,
])

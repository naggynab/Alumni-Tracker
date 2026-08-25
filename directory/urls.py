from django.urls import path

from . import views
from . import student_views
from . import community_views

app_name = "directory"

urlpatterns = [
    path("", views.home, name="home"),
    path("alumni/", views.alumni_list, name="alumni-list"),
    path("alumni/<int:pk>/", views.alumnus_detail, name="alumnus-detail"),
    path("me/", views.my_profile, name="my-profile"),
    path("me/completeness/", views.profile_completeness_page, name="profile-completeness"),
    path("student/", student_views.student_services, name="student-services"),
    path("student/notifications/", community_views.notification_list, name="notifications"),
    path("student/notifications/<int:notification_id>/read/", community_views.notification_read, name="notification-read"),
    path("student/saved-searches/", community_views.saved_searches, name="saved-searches"),
    path("student/saved-searches/<int:search_id>/delete/", community_views.saved_search_delete, name="saved-search-delete"),
    path("student/favorites/", community_views.favorite_list, name="favorites"),
    path("student/favorites/<int:alumnus_id>/toggle/", community_views.favorite_toggle, name="favorite-toggle"),
    path("student/communities/", community_views.community_groups, name="community-groups"),
    path("student/communities/create/", community_views.community_group_create, name="community-group-create"),
    path("student/communities/<slug:slug>/", community_views.community_group, name="community-group"),
    path("student/communities/<slug:slug>/post/", community_views.community_group_post, name="community-group-post"),
    path("student/stories/", community_views.stories, name="stories"),
    path("student/stories/submit/", community_views.story_submit, name="story-submit"),
    path("student/skills/", community_views.skills, name="skills"),
    path("student/skills/<int:skill_id>/endorse/", community_views.endorse_skill, name="endorse-skill"),
    path("student/surveys/", community_views.surveys, name="surveys"),
    path("student/surveys/<int:survey_id>/", community_views.survey_detail, name="survey-detail"),
    path("student/resources/", community_views.resources, name="resources"),
    path("student/resources/submit/", community_views.resource_submit, name="resource-submit"),
    path("student/recommendations/", community_views.recommendations, name="recommendations"),
    path("student/resume.pdf", community_views.resume_pdf, name="resume-pdf"),
    path("student/activity/", community_views.activity_history, name="activity-history"),
    path("student/api-tokens/", community_views.api_tokens, name="api-tokens"),
    path("student/api-tokens/<int:token_id>/revoke/", community_views.api_token_revoke, name="api-token-revoke"),
    path("student/security/", community_views.security, name="security"),
    path(
        "student/corrections/",
        student_views.correction_requests,
        name="correction-requests",
    ),
    path(
        "student/mentorship/",
        student_views.mentorship_hub,
        name="mentorship",
    ),
    path(
        "student/mentorship/profile/",
        student_views.mentorship_profile,
        name="mentorship-profile",
    ),
    path(
        "student/mentorship/request/<int:mentor_id>/",
        student_views.mentorship_request,
        name="mentorship-request",
    ),
    path(
        "student/mentorship/request/<int:request_id>/decision/",
        student_views.mentorship_decision,
        name="mentorship-decision",
    ),
    path("student/jobs/", student_views.job_board, name="job-board"),
    path("student/jobs/submit/", student_views.job_submit, name="job-submit"),
    path("student/events/", student_views.event_list, name="event-list"),
    path("student/events/submit/", student_views.event_submit, name="event-submit"),
    path(
        "student/events/<int:event_id>/registration/",
        student_views.event_registration,
        name="event-registration",
    ),
    path(
        "student/contacts/",
        student_views.contact_requests,
        name="contact-requests",
    ),
    path(
        "student/contacts/send/",
        student_views.contact_request_create,
        name="contact-request-create",
    ),
    path(
        "student/contacts/<int:request_id>/decision/",
        student_views.contact_request_decision,
        name="contact-request-decision",
    ),
    path("reports/department/", views.department_report, name="department-report"),
    path(
        "reports/department/data-quality/",
        views.department_data_quality,
        name="department-data-quality",
    ),
    path(
        "reports/department/compare/",
        views.department_report_compare,
        name="department-report-compare",
    ),
    path(
        "reports/department/follow-ups/",
        views.follow_up_queue,
        name="follow-up-queue",
    ),
    path(
        "reports/department/follow-ups/new/<int:alumnus_id>/",
        views.follow_up_create,
        name="follow-up-create",
    ),
    path(
        "reports/department/follow-ups/<int:pk>/",
        views.follow_up_edit,
        name="follow-up-edit",
    ),
    path(
        "reports/department/verification/",
        views.department_verification,
        name="department-verification",
    ),
    path(
        "reports/department/verification/<int:review_id>/",
        views.department_verification_review,
        name="department-verification-review",
    ),
    path(
        "reports/department/roles/",
        views.department_roles,
        name="department-roles",
    ),
    path(
        "reports/department/corrections/",
        student_views.correction_review_queue,
        name="correction-review-queue",
    ),
    path(
        "reports/department/corrections/<int:request_id>/",
        student_views.correction_review,
        name="correction-review",
    ),
    path(
        "reports/department/student-requests/",
        student_views.student_request_replies,
        name="student-requests",
    ),
    path(
        "reports/department/community-moderation/",
        student_views.community_moderation,
        name="community-moderation",
    ),
    path("reports/department/content-moderation/", community_views.community_content_moderation, name="content-moderation"),
    path("reports/department/conflicts/", community_views.data_conflicts, name="data-conflicts"),
    path(
        "reports/department/export/<str:breakdown>/",
        views.department_report_export,
        name="department-report-export",
    ),
]

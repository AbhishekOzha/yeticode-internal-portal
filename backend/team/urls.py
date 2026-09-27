from django.urls import path

from . import chat, leave, reviews, views

urlpatterns = [
    path("team/office-hours/", views.OfficeHoursListView.as_view(), name="office-hours"),
    path("team/office-hours/me/", views.MyOfficeHoursView.as_view(), name="my-office-hours"),
    path("team/office-hours/<uuid:pk>/", views.OfficeHoursDetailView.as_view(), name="office-hours-detail"),
    path("chat/contacts/", chat.ChatContactsView.as_view(), name="chat-contacts"),
    path("chat/messages/", chat.ChatMessagesView.as_view(), name="chat-messages"),
    path("chat/messages/<uuid:pk>/audio/", chat.ChatAudioView.as_view(), name="chat-audio"),
    path("chat/messages/<uuid:pk>/file/", chat.ChatFileView.as_view(), name="chat-file"),
    path("chat/read/", chat.ChatReadView.as_view(), name="chat-read"),
    path("chat/updates/", chat.ChatUpdatesView.as_view(), name="chat-updates"),
    path("chat/groups/", chat.ChatGroupsView.as_view(), name="chat-groups"),
    path("chat/groups/<uuid:pk>/", chat.ChatGroupDetailView.as_view(), name="chat-group"),
    path("chat/groups/<uuid:pk>/leave/", chat.ChatGroupLeaveView.as_view(), name="chat-group-leave"),
    path("team/reviews/", reviews.ReviewWriteView.as_view(), name="reviews"),
    path("team/reviews/people/", reviews.ReviewPeopleView.as_view(), name="review-people"),
    path("team/reviews/summary/", reviews.ReviewSummaryView.as_view(), name="review-summary"),
    path("team/reviews/<uuid:pk>/", reviews.ReviewDeleteView.as_view(), name="review-detail"),
    path("team/leave/", leave.MyLeaveView.as_view(), name="leave"),
    path("team/leave/requests/", leave.TeamLeaveView.as_view(), name="leave-requests"),
    path("team/leave/<uuid:pk>/cancel/", leave.CancelLeaveView.as_view(), name="leave-cancel"),
    path("team/leave/<uuid:pk>/decide/", leave.DecideLeaveView.as_view(), name="leave-decide"),
]

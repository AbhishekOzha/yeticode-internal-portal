from django.urls import path

from . import chat, reviews, views

urlpatterns = [
    path("team/office-hours/", views.OfficeHoursListView.as_view(), name="office-hours"),
    path("team/office-hours/me/", views.MyOfficeHoursView.as_view(), name="my-office-hours"),
    path("team/office-hours/<int:pk>/", views.OfficeHoursDetailView.as_view(), name="office-hours-detail"),
    path("chat/contacts/", chat.ChatContactsView.as_view(), name="chat-contacts"),
    path("chat/messages/", chat.ChatMessagesView.as_view(), name="chat-messages"),
    path("chat/messages/<int:pk>/audio/", chat.ChatAudioView.as_view(), name="chat-audio"),
    path("chat/messages/<int:pk>/file/", chat.ChatFileView.as_view(), name="chat-file"),
    path("chat/read/", chat.ChatReadView.as_view(), name="chat-read"),
    path("chat/updates/", chat.ChatUpdatesView.as_view(), name="chat-updates"),
    path("chat/groups/", chat.ChatGroupsView.as_view(), name="chat-groups"),
    path("chat/groups/<int:pk>/", chat.ChatGroupDetailView.as_view(), name="chat-group"),
    path("chat/groups/<int:pk>/leave/", chat.ChatGroupLeaveView.as_view(), name="chat-group-leave"),
    path("team/reviews/", reviews.ReviewWriteView.as_view(), name="reviews"),
    path("team/reviews/people/", reviews.ReviewPeopleView.as_view(), name="review-people"),
    path("team/reviews/summary/", reviews.ReviewSummaryView.as_view(), name="review-summary"),
    path("team/reviews/<int:pk>/", reviews.ReviewDeleteView.as_view(), name="review-detail"),
]

from django.urls import path

from . import reviews, views

urlpatterns = [
    path("team/office-hours/", views.OfficeHoursListView.as_view(), name="office-hours"),
    path("team/office-hours/me/", views.MyOfficeHoursView.as_view(), name="my-office-hours"),
    path("team/office-hours/<int:pk>/", views.OfficeHoursDetailView.as_view(), name="office-hours-detail"),
    path("chat/contacts/", views.ChatContactsView.as_view(), name="chat-contacts"),
    path("chat/messages/", views.ChatMessagesView.as_view(), name="chat-messages"),
    path("chat/messages/<int:pk>/audio/", views.ChatAudioView.as_view(), name="chat-audio"),
    path("chat/messages/<int:pk>/file/", views.ChatFileView.as_view(), name="chat-file"),
    path("chat/read/", views.ChatReadView.as_view(), name="chat-read"),
    path("chat/updates/", views.ChatUpdatesView.as_view(), name="chat-updates"),
    path("team/reviews/", reviews.ReviewWriteView.as_view(), name="reviews"),
    path("team/reviews/people/", reviews.ReviewPeopleView.as_view(), name="review-people"),
    path("team/reviews/summary/", reviews.ReviewSummaryView.as_view(), name="review-summary"),
    path("team/reviews/<int:pk>/", reviews.ReviewDeleteView.as_view(), name="review-detail"),
]

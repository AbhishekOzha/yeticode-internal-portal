from django.urls import path

from . import views

urlpatterns = [
    path("team/office-hours/", views.OfficeHoursListView.as_view(), name="office-hours"),
    path("team/office-hours/me/", views.MyOfficeHoursView.as_view(), name="my-office-hours"),
    path("team/office-hours/<int:pk>/", views.OfficeHoursDetailView.as_view(), name="office-hours-detail"),
    path("chat/contacts/", views.ChatContactsView.as_view(), name="chat-contacts"),
    path("chat/messages/", views.ChatMessagesView.as_view(), name="chat-messages"),
    path("chat/read/", views.ChatReadView.as_view(), name="chat-read"),
    path("chat/updates/", views.ChatUpdatesView.as_view(), name="chat-updates"),
]

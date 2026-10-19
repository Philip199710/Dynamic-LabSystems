from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("", views.chat_home, name="home"),
    path("new/", views.create_channel, name="create_channel"),
    path("unread.json", views.unread_total, name="unread"),
    path("<int:pk>/", views.channel_view, name="channel"),
    path("<int:pk>/messages/", views.channel_messages, name="messages"),
    path("<int:pk>/send/", views.send_message, name="send"),
]

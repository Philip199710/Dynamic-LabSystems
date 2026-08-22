from django.urls import path

from . import views

app_name = "labtests"

urlpatterns = [
    path("sample/<int:sample_pk>/assign/", views.assign_test, name="assign"),
    path("<int:pk>/result/", views.enter_result, name="enter_result"),
    path("my-worklist/", views.my_worklist, name="my_worklist"),
]

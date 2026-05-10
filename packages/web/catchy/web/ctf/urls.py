from django.urls import path

from . import views

app_name = "ctf"

urlpatterns = [
    path("", views.index, name="index"),
    path("secrets/", views.secret_list, name="secret_list"),
    path("secrets/new/", views.secret_create, name="secret_create"),
    path("agents/", views.agent_list, name="agent_list"),
    path("agents/new/", views.agent_create, name="agent_create"),
    path("agents/<slug:slug>/", views.agent_detail, name="agent_detail"),
    path("agents/<slug:slug>/edit/", views.agent_update, name="agent_update"),
    path("ctfs/new/", views.ctf_create, name="ctf_create"),
    path("ctfs/<slug:slug>/", views.ctf_detail, name="ctf_detail"),
    path("ctfs/<slug:slug>/edit/", views.ctf_update, name="ctf_update"),
    path("ctfs/<slug:ctf_slug>/challenges/new/", views.challenge_create, name="challenge_create"),
    path(
        "ctfs/<slug:ctf_slug>/challenges/<slug:challenge_id>/",
        views.challenge_detail,
        name="challenge_detail",
    ),
    path(
        "ctfs/<slug:ctf_slug>/challenges/<slug:challenge_id>/edit/",
        views.challenge_update,
        name="challenge_update",
    ),
    path(
        "ctfs/<slug:ctf_slug>/challenges/<slug:challenge_id>/threads/new/",
        views.thread_create,
        name="thread_create",
    ),
    path("threads/<int:pk>/", views.thread_detail, name="thread_detail"),
    path("threads/<int:pk>/publish/", views.thread_publish, name="thread_publish"),
    path("threads/<int:pk>/steer/", views.thread_steer, name="thread_steer"),
    path("threads/<int:pk>/stream/", views.thread_stream, name="thread_stream"),
]

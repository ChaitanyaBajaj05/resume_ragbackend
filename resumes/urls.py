from django.urls import path
from .views import (
    RegisterView,
    ResumeUploadView,
    ResumeListView,
    ResumeDetailView,
    AskView,
    JobListView,
    JobCreateView,
    JobDetailView,
    JobMatchView
)
from rest_framework_simplejwt.views import TokenObtainPairView

urlpatterns = [
    path("register/", RegisterView.as_view()),
    path("resumes/", ResumeListView.as_view()),
    path("resumes/upload/", ResumeUploadView.as_view()),
    path("resumes/<uuid:id>/", ResumeDetailView.as_view()),
    path("ask/", AskView.as_view()),

    # Jobs
    path("jobs/", JobCreateView.as_view(), name="job-create"),
    path("jobs/list/", JobListView.as_view(), name="job-list"),
    path("jobs/<uuid:id>/", JobDetailView.as_view()),
    path("jobs/<uuid:id>/match/", JobMatchView.as_view()),
]

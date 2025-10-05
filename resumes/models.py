from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
import uuid
from django.conf import settings

# ----------------------------
# Custom User Model
# ----------------------------
class User(AbstractUser):
    ROLE_CHOICES = (("candidate", "candidate"), ("recruiter", "recruiter"), ("admin", "admin"))
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="candidate")

    # Override groups & permissions to avoid clashes with auth.User
    groups = models.ManyToManyField(
        Group,
        related_name="resumes_user_set",  # unique related_name
        blank=True,
        help_text="The groups this user belongs to.",
        verbose_name="groups",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="resumes_user_permissions_set",  # unique related_name
        blank=True,
        help_text="Specific permissions for this user.",
        verbose_name="user permissions",
    )


# ----------------------------
# Resume Upload Model
# ----------------------------
def upload_to(instance, filename):
    return f"resumes/{instance.id}/{filename}"


class Resume(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    filename = models.CharField(max_length=255)
    original_file = models.FileField(upload_to=upload_to, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=(("processing", "processing"), ("processed", "processed"), ("failed", "failed")),
        default="processing",
    )
    redacted = models.BooleanField(default=True)
    summary = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.filename} ({self.id})"


class ResumeChunk(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name="chunks")
    chunk_text = models.TextField()
    chunk_order = models.IntegerField()
    page_number = models.IntegerField(null=True, blank=True)
    char_start = models.IntegerField(null=True, blank=True)
    char_end = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


# ----------------------------
# Job & Match Models
# ----------------------------
class Job(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField()
    requirements = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)


class MatchReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE)
    score = models.FloatField()
    evidence = models.JSONField(default=list)
    missing_requirements = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)


# ----------------------------
# Idempotency Key Model
# ----------------------------
class IdempotencyKey(models.Model):
    key = models.CharField(max_length=255, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    endpoint = models.CharField(max_length=255)
    request_hash = models.CharField(max_length=255)
    response_body = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

from django.contrib import admin
from .models import Resume, ResumeChunk, Job, MatchReport, IdempotencyKey
admin.site.register(Resume)
admin.site.register(ResumeChunk)
admin.site.register(Job)
admin.site.register(MatchReport)
admin.site.register(IdempotencyKey)

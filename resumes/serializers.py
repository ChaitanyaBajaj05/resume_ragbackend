from rest_framework import serializers
from .models import Resume, ResumeChunk, Job, MatchReport
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id","username","email","role")

class ResumeChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResumeChunk
        fields = ("id","chunk_text","chunk_order","page_number","char_start","char_end")

class ResumeSerializer(serializers.ModelSerializer):
    chunks = ResumeChunkSerializer(many=True, read_only=True)
    class Meta:
        model = Resume
        fields = ("id","filename","uploaded_at","status","redacted","summary","chunks")

class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = ("id","owner","title","description","requirements","created_at")
        read_only_fields = ("owner","created_at")

class MatchReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = MatchReport
        fields = ("id","job","resume","score","evidence","missing_requirements","created_at")

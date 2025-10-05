from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.response import Response
from rest_framework.decorators import api_view

@api_view(['GET'])
def health(request):
    return Response({"status":"ok"})

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/", include("resumes.urls")),
    path("api/health", health),
    path(".well-known/hackathon.json", lambda r: Response({"project":"ResumeRAG","version":"1.0"})),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

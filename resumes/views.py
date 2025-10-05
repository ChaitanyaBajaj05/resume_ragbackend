from rest_framework.views import APIView
from rest_framework import generics, status, permissions
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .models import Resume, ResumeChunk, Job, MatchReport, IdempotencyKey
from .serializers import ResumeSerializer, JobSerializer, MatchReportSerializer, ResumeChunkSerializer
from .tasks import process_resume_sync
from .utils import query_index
from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied
User = get_user_model()

class RegisterView(APIView):
    permission_classes = []
    def post(self, request):
        data = request.data
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")
        role = data.get("role","candidate")
        if not username or not password:
            return Response({"error":{"code":"FIELD_REQUIRED","field":"username/password","message":"username and password required"}}, status=400)
        user = User.objects.create_user(username=username,email=email,password=password)
        user.role = role
        user.save()
        return Response({"id":user.id,"username":user.username,"email":user.email,"role":user.role}, status=201)

class ResumeUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = (permissions.IsAuthenticated,)
    def post(self, request):
        file = request.FILES.get("file")
        owner_id = request.data.get("owner_id")
        if not file:
            return Response({"error":{"code":"FIELD_REQUIRED","field":"file","message":"file required"}}, status=400)
        resume = Resume.objects.create(filename=file.name, original_file=file, status="processing")
        # if candidate uploaded, set owner
        if owner_id:
            try:
                user = User.objects.get(id=owner_id)
                resume.owner = user
                resume.save()
            except:
                pass
        # process sync (or enqueue)
        try:
            process_resume_sync(str(resume.id))
        except Exception as e:
            resume.status = "failed"
            resume.save()
        # update idempotency response if present
        key = request.headers.get("Idempotency-Key")
        if key:
            try:
                ik = IdempotencyKey.objects.filter(key=key).first()
                if ik:
                    ik.response_body = {"id":str(resume.id),"filename":resume.filename,"status":resume.status}
                    ik.save()
            except:
                pass
        return Response({"id":str(resume.id),"filename":resume.filename,"status":resume.status}, status=202)

class ResumeListView(generics.ListAPIView):
    serializer_class = ResumeSerializer
    permission_classes = (permissions.IsAuthenticated,)
    def get_queryset(self):
        q = self.request.query_params.get("q")
        qs = Resume.objects.all().order_by("-uploaded_at")
        if q:
            # naive text search in summary or in chunk text (could be expanded to semantic)
            qs = qs.filter(Q(summary__icontains=q) | Q(filename__icontains=q))
        return qs

class ResumeDetailView(generics.RetrieveAPIView):
    serializer_class = ResumeSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = "id"
    queryset = Resume.objects.all()
    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        ser = self.get_serializer(obj)
        data = ser.data
        # redact if not recruiter and resume.redacted True
        if obj.redacted and request.user.role != "recruiter":
            # remove PII-like things in the chunks
            for c in data.get("chunks", []):
                c["chunk_text"] = c["chunk_text"].replace("REDACTED_EMAIL","[REDACTED]").replace("REDACTED_PHONE","[REDACTED]")
        return Response(data)

class AskView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    def post(self, request):
        q = request.data.get("query")
        k = int(request.data.get("k",5))
        if not q:
            return Response({"error":{"code":"FIELD_REQUIRED","field":"query","message":"query required"}}, status=400)
        results = query_index(q, k=k)
        answers = []
        for r in results:
            chunk_id = r.get("chunk_id")
            score = r.get("score")
            try:
                chunk = ResumeChunk.objects.get(id=chunk_id)
                answers.append({
                    "resume_id": str(chunk.resume.id),
                    "score": score,
                    "evidence": [{
                        "chunk_id": str(chunk.id),
                        "text": chunk.chunk_text[:500],
                        "page": chunk.page_number,
                        "start": chunk.char_start,
                        "end": chunk.char_end
                    }]
                })
            except:
                continue
        return Response({"query_id":"q_"+str(hash(q)),"answers":answers})
class JobListView(generics.ListAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = JobSerializer

    def get_queryset(self):
        # Assuming all jobs are "open"
        return Job.objects.all().order_by("-created_at")


class JobCreateView(generics.CreateAPIView):
    serializer_class = JobSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def perform_create(self, serializer):
        user = self.request.user
        # Allow both 'recruiter' and 'admin' to create jobs
        if user.role not in ["recruiter", "admin"]:
            raise PermissionDenied("Only recruiters and admins can create jobs.")
        serializer.save(owner=user)

class JobDetailView(generics.RetrieveAPIView):
    serializer_class = JobSerializer
    permission_classes = (permissions.IsAuthenticated,)
    queryset = Job.objects.all()
    lookup_field = "id"

class JobMatchView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    def post(self, request, id):
        top_n = int(request.data.get("top_n", 10))
        job = get_object_or_404(Job, id=id)
        # aggregate resume-level score by querying job title+requirements
        query_text = f"{job.title}. Requirements: {'; '.join(job.requirements or [])}. {job.description}"
        hits = query_index(query_text, k=top_n*5)
        # map chunk hits to resume scores
        resume_scores = {}
        from .models import ResumeChunk
        for h in hits:
            cid = h.get("chunk_id")
            score = h.get("score")
            try:
                chunk = ResumeChunk.objects.get(id=cid)
            except:
                continue
            rid = str(chunk.resume.id)
            resume_scores.setdefault(rid, {"score_sum":0,"evidence":[],"count":0})
            resume_scores[rid]["score_sum"] += score
            resume_scores[rid]["count"] += 1
            resume_scores[rid]["evidence"].append({"chunk_id":str(chunk.id),"text":chunk.chunk_text[:300],"score":score})
        # produce ranked list
        ranked = []
        for rid, d in resume_scores.items():
            # deterministic tie break: use uploaded_at then resume id
            resume = Resume.objects.get(id=rid)
            score = d["score_sum"] / max(1, d["count"])
            ranked.append({"resume":resume, "score": score, "evidence": d["evidence"]})
        # sort by score desc, tie-breaker: uploaded_at desc then id
        ranked.sort(key=lambda x: (x["score"], x["resume"].uploaded_at, str(x["resume"].id)), reverse=True)
        matches = []
        # compute missing requirements by searching evidence text for requirement strings
        for r in ranked[:top_n]:
            found_reqs = []
            missing = []
            text_blob = " ".join([e["text"] for e in r["evidence"]])
            for req in job.requirements or []:
                if req.lower() in text_blob.lower():
                    found_reqs.append(req)
                else:
                    missing.append(req)
            matches.append({
                "resume_id": str(r["resume"].id),
                "score": float(r["score"]),
                "evidence": r["evidence"],
                "missing_requirements": missing
            })
            # optionally store MatchReport
            MatchReport.objects.create(job=job, resume=r["resume"], score=r["score"], evidence=r["evidence"], missing_requirements=missing)
        return Response({"job_id": str(job.id), "matches": matches})

from .models import Resume, ResumeChunk
from .utils import extract_text_from_pdf, chunk_text, add_chunks_to_index, redact_pii
from django.conf import settings
import os

def process_resume_sync(resume_id):
    resume = Resume.objects.get(id=resume_id)
    path = resume.original_file.path
    text = extract_text_from_pdf(path)
    # detect and redact PII stored separately
    redacted_text = redact_pii(text)
    # chunk the redacted text for retrieval
    chunks = chunk_text(redacted_text, chunk_size=250, overlap=50)
    chunk_objs = []
    for c in chunks:
        rc = ResumeChunk.objects.create(
            resume=resume,
            chunk_text=c["text"],
            chunk_order=c["order"],
            page_number=None
        )
        chunk_objs.append(rc)
    # add to faiss
    add_chunks_to_index(chunk_objs)
    resume.status = "processed"
    resume.summary = (redacted_text[:800])
    resume.save()
    return True

# If using Celery, you can define a Celery task:
# from celery import shared_task
# @shared_task
# def process_resume_task(resume_id):
#     return process_resume_sync(resume_id)

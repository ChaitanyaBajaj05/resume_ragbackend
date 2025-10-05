from .models import Resume, ResumeChunk
from .utils import extract_text_from_pdf, chunk_text, add_chunks_to_index, redact_pii

def process_resume_sync(resume_id):
    resume = Resume.objects.get(id=resume_id)
    path = resume.original_file.path
    text = extract_text_from_pdf(path)
    # redact PII from extracted text
    redacted_text = redact_pii(text)
    # chunk redacted text
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
    # add chunks to FAISS index
    add_chunks_to_index(chunk_objs)
    # update resume status and summary
    resume.status = "processed"
    resume.summary = redacted_text[:800]
    resume.save()
    return True

# Optional Celery task example:
# from celery import shared_task
# @shared_task
# def process_resume_task(resume_id):
#     return process_resume_sync(resume_id)

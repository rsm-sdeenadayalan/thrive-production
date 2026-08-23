"""Corpus ingestion: text -> heading-aware chunks -> embedded rows."""

import re

from django.db import transaction

from rsm_thrive.models import Document, DocumentChunk

_HEADING = re.compile(r"^#{1,6}\s+(.*)$")


def chunk_text(text, max_chars=1400, overlap=200):
    sections = []  # (heading, [lines])
    current = ("", [])
    for line in text.splitlines():
        match = _HEADING.match(line)
        if match:
            sections.append(current)
            current = (match.group(1).strip(), [])
        else:
            current[1].append(line)
    sections.append(current)

    chunks = []
    for heading, lines in sections:
        body = "\n".join(lines).strip()
        if not body:
            continue
        if len(body) <= max_chars:
            chunks.append({"heading": heading, "text": body})
            continue
        # split on paragraph boundaries, carrying `overlap` chars forward
        paragraphs = [p for p in re.split(r"\n\s*\n", body) if p.strip()]
        piece = ""
        for paragraph in paragraphs:
            if piece and len(piece) + 2 + len(paragraph) > max_chars:
                chunks.append({"heading": heading, "text": piece[:max_chars]})
                piece = piece[-overlap:]
            piece = (piece + "\n\n" + paragraph).strip() if piece else paragraph
        if piece:
            chunks.append({"heading": heading, "text": piece[:max_chars]})
    return chunks


def extract_pdf_text(path):
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


@transaction.atomic
def ingest_document(source, title, kind, destinations, text, embeddings):
    Document.objects.filter(source=source).delete()
    doc = Document.objects.create(source=source, title=title, kind=kind,
                                  destinations=destinations)
    chunks = chunk_text(text)
    if chunks:
        vectors = embeddings.embed([c["text"] for c in chunks])
        DocumentChunk.objects.bulk_create([
            DocumentChunk(document=doc, seq=seq, heading=c["heading"],
                          text=c["text"], embedding=vector)
            for seq, (c, vector) in enumerate(zip(chunks, vectors))
        ])
    return doc

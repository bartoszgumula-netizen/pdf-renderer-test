from fastapi import FastAPI, HTTPException, Header, Response
from pydantic import BaseModel
from typing import Optional, Dict, Any
import base64
import fitz  # PyMuPDF
import io
import os


API_TOKEN = os.environ.get("RENDERER_API_TOKEN", "change-me")

app = FastAPI()


class RenderRequest(BaseModel):
    jobId: str
    sourcePdfBase64: str
    ocr: Dict[str, Any]
    targetLanguage: str = "de"
    mode: str = "visible_overlay"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/render")
def render_pdf(
    req: RenderRequest,
    authorization: Optional[str] = Header(default=None)
):
    expected = f"Bearer {API_TOKEN}"

    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        source_pdf_bytes = base64.b64decode(req.sourcePdfBase64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 PDF")

    try:
        doc = fitz.open(stream=source_pdf_bytes, filetype="pdf")

        for item in req.ocr.get("items", []):
            page_index = int(item.get("page", 1)) - 1

            if page_index < 0 or page_index >= len(doc):
                continue

            bbox = item.get("bbox")
            if not bbox or len(bbox) != 4:
                continue

            page = doc[page_index]
            rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])

            text = item.get("translatedText") or item.get("text") or ""

            page.insert_textbox(
                rect,
                text,
                fontsize=8,
                fontname="helv",
                color=(0, 0, 0)
            )

        output = io.BytesIO()
        doc.save(output)
        doc.close()

        return Response(
            content=output.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{req.jobId}-rendered.pdf"',
                "X-Renderer-Job-Id": req.jobId
            }
        )

    except Exception:
        raise HTTPException(status_code=500, detail="PDF rendering failed")

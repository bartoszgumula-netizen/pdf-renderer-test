from fastapi import FastAPI, HTTPException, Header, Response
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
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


def box_to_rect(box: Dict[str, Any]) -> fitz.Rect:
    x = float(box.get("x", 0))
    y = float(box.get("y", 0))
    width = float(box.get("width", 0))
    height = float(box.get("height", 0))
    return fitz.Rect(x, y, x + width, y + height)


def insert_text(page, rect, text, fontsize=8):
    if not text:
        return

    page.insert_textbox(
        rect,
        str(text),
        fontsize=fontsize,
        fontname="helv",
        color=(0, 0, 0)
    )


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

        if len(doc) == 0:
            raise HTTPException(status_code=400, detail="PDF has no pages")

        page = doc[0]

        for item in req.ocr.get("items", []):
            label = item.get("label", {})
            value = item.get("value", {})

            label_text = label.get("value", "")
            value_text = value.get("value", "")

            label_box = label.get("boundingBox", {})
            value_box = value.get("boundingBox", {})

            if label_box:
                label_rect = box_to_rect(label_box)
                insert_text(page, label_rect, label_text, fontsize=7)

            if value_box:
                value_rect = box_to_rect(value_box)
                insert_text(page, value_rect, value_text, fontsize=9)

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

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="PDF rendering failed")

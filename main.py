from fastapi import FastAPI, HTTPException, Header, Response
from pydantic import BaseModel
from typing import Optional, Dict, Any
import fitz  # PyMuPDF
import io
import os


API_TOKEN = os.environ.get("RENDERER_API_TOKEN", "change-me")

app = FastAPI()


class RenderRequest(BaseModel):
    jobId: str
    ocr: Dict[str, Any]
    targetLanguage: str = "de"
    mode: str = "json_to_pdf"


@app.get("/health")
def health():
    return {"status": "ok"}


def box_to_rect(box: Dict[str, Any]) -> fitz.Rect:
    x = float(box.get("x", 0))
    y = float(box.get("y", 0))
    width = float(box.get("width", 0))
    height = float(box.get("height", 0))
    return fitz.Rect(x, y, x + width, y + height)


def insert_textbox(page, rect, text, fontsize=10):
    if not text:
        return

    page.insert_textbox(
        rect,
        str(text),
        fontsize=fontsize,
        fontname="helv",
        color=(0, 0, 0),
        align=1
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
        page_dimensions = req.ocr.get("pageDimensions", {})
        page_width = float(page_dimensions.get("width", 988))
        page_height = float(page_dimensions.get("height", 988))

        doc = fitz.open()
        page = doc.new_page(width=page_width, height=page_height)

        # Draw labels and values
        for item in req.ocr.get("items", []):
            label = item.get("label", {})
            value = item.get("value", {})

            label_text = label.get("value", "")
            value_text = value.get("value", "")

            label_box = label.get("boundingBox", {})
            value_box = value.get("boundingBox", {})

            if label_box:
                label_rect = box_to_rect(label_box)
                insert_textbox(page, label_rect, label_text, fontsize=8)

            if value_box:
                value_rect = box_to_rect(value_box)
                insert_textbox(page, value_rect, value_text, fontsize=12)

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

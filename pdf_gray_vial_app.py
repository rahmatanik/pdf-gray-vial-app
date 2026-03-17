import io
import os
import tempfile
from typing import Optional, Tuple

import fitz  # PyMuPDF
import numpy as np
import streamlit as st
from PIL import Image

st.set_page_config(page_title="Gray Vial PDF Processor", page_icon="🧪", layout="centered")


def find_target_image(page: fitz.Page) -> Optional[int]:
    """Return the xref of the most likely vial photo on page 1.

    Heuristic:
    - choose the largest embedded raster image on the page
    - this matches the lab-report layout the user provided
    """
    images = page.get_images(full=True)
    if not images:
        return None
    target = max(images, key=lambda x: x[2] * x[3])
    return target[0]


def tone_preserving_grayscale(img: Image.Image, brightness_lift: float = 24.0, contrast_scale: float = 0.90) -> Image.Image:
    """Convert to grayscale while preserving shadow detail so the cap doesn't crush to black."""
    rgb = img.convert("RGB")
    arr = np.asarray(rgb).astype(np.float32)

    # standard luminance
    gray = arr[..., 0] * 0.299 + arr[..., 1] * 0.587 + arr[..., 2] * 0.114

    # soften contrast and lift shadows
    gray = gray * contrast_scale + brightness_lift
    gray = np.clip(gray, 0, 255).astype(np.uint8)

    out = np.stack([gray, gray, gray], axis=-1)
    return Image.fromarray(out, mode="RGB")


def process_pdf_bytes(pdf_bytes: bytes) -> Tuple[bytes, bytes, str]:
    """Process the first page's vial image only and return:
    - output pdf bytes
    - preview image bytes (processed vial image)
    - status message
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if doc.page_count < 1:
        raise ValueError("PDF has no pages.")

    page = doc[0]
    target_xref = find_target_image(page)
    if target_xref is None:
        raise ValueError("No embedded image found on page 1.")

    pix = fitz.Pixmap(doc, target_xref)
    if pix.alpha:
        pix = fitz.Pixmap(fitz.csRGB, pix)

    original_img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    processed_img = tone_preserving_grayscale(original_img)

    img_buffer = io.BytesIO()
    processed_img.save(img_buffer, format="PNG", optimize=True)
    processed_img_bytes = img_buffer.getvalue()

    # Replace only the embedded vial image. This keeps layout/text/chromatogram untouched.
    page.replace_image(target_xref, stream=processed_img_bytes)

    out = io.BytesIO()
    doc.save(out, garbage=4, deflate=True, clean=True)
    doc.close()

    return out.getvalue(), processed_img_bytes, "Processed successfully. Only the embedded vial photo on page 1 was changed."


st.title("Gray Vial PDF Processor")
st.caption("Drag and drop a lab report PDF. The app keeps the report intact and changes only the medicine vial photo on page 1 to grayscale.")

with st.expander("What this app does", expanded=False):
    st.markdown(
        """
- Keeps layout, text, footer, chromatogram, spacing, and page structure unchanged
- Changes only the embedded vial image on page 1
- Uses tone-preserving grayscale to avoid the cap turning crushed black
- Returns a downloadable processed PDF
        """
    )

uploaded = st.file_uploader("Drop your PDF here", type=["pdf"])

col1, col2 = st.columns(2)
with col1:
    brightness_lift = st.slider("Shadow lift", min_value=0, max_value=60, value=24, help="Raise dark tones so the cap stays gray instead of black.")
with col2:
    contrast_scale = st.slider("Contrast soften", min_value=0.70, max_value=1.10, value=0.90, step=0.01, help="Lower values soften contrast and reduce black crush.")

# patch processor with UI controls
if uploaded:
    pdf_bytes = uploaded.read()

    def process_pdf_bytes_custom(pdf_bytes: bytes) -> Tuple[bytes, bytes, str]:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if doc.page_count < 1:
            raise ValueError("PDF has no pages.")

        page = doc[0]
        target_xref = find_target_image(page)
        if target_xref is None:
            raise ValueError("No embedded image found on page 1.")

        pix = fitz.Pixmap(doc, target_xref)
        if pix.alpha:
            pix = fitz.Pixmap(fitz.csRGB, pix)

        original_img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")

        rgb = np.asarray(original_img).astype(np.float32)
        gray = rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114
        gray = gray * float(contrast_scale) + float(brightness_lift)
        gray = np.clip(gray, 0, 255).astype(np.uint8)
        processed_img = Image.fromarray(np.stack([gray, gray, gray], axis=-1), mode="RGB")

        img_buffer = io.BytesIO()
        processed_img.save(img_buffer, format="PNG", optimize=True)
        processed_img_bytes = img_buffer.getvalue()

        page.replace_image(target_xref, stream=processed_img_bytes)

        out = io.BytesIO()
        doc.save(out, garbage=4, deflate=True, clean=True)
        doc.close()

        return out.getvalue(), processed_img_bytes, "Processed successfully."

    try:
        output_pdf, preview_png, status = process_pdf_bytes_custom(pdf_bytes)
        st.success(status)

        st.subheader("Preview of processed vial image")
        st.image(preview_png, use_container_width=True)

        base_name = os.path.splitext(uploaded.name)[0]
        output_name = f"{base_name}_gray.pdf"

        st.download_button(
            label="Download processed PDF",
            data=output_pdf,
            file_name=output_name,
            mime="application/pdf",
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"Processing failed: {e}")

st.markdown("---")
st.markdown("Run locally with: `streamlit run pdf_gray_vial_app.py`")

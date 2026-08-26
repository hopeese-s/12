import os
import io
import re
import time
import zipfile
import logging
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import pymupdf as fitz

from app.config import get_download_dir

logger = logging.getLogger("converter")

def sanitize_filename(name: str, fallback: str = "converted_file") -> str:
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    return cleaned if cleaned else fallback

def pdf_to_images(
    pdf_bytes: bytes, 
    original_filename: str = "document.pdf",
    output_format: str = "jpg", 
    dpi: int = 150, 
    quality: int = 90
) -> Dict[str, Any]:
    """
    Converts each page of a PDF document into high-resolution JPG or PNG images.
    If multiple pages, also creates a .zip package.
    """
    download_dir = get_download_dir()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)
    
    if total_pages == 0:
        raise ValueError("PDF document has no pages.")

    base_name = os.path.splitext(sanitize_filename(original_filename, "document"))[0]
    out_ext = "jpg" if output_format.lower() in ["jpg", "jpeg"] else "png"
    
    # Calculate scale factor for requested DPI (72 dpi is 1.0 scale)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    
    page_files = []
    zip_buffer = io.BytesIO() if total_pages > 1 else None
    zf = zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) if zip_buffer else None
    
    try:
        for page_num in range(total_pages):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(matrix=mat, alpha=False if out_ext == "jpg" else True)
            
            img_data = pix.tobytes("jpg" if out_ext == "jpg" else "png")
            
            # If JPG quality optimization needed, route through PIL
            if out_ext == "jpg" and quality != 95:
                pil_img = Image.open(io.BytesIO(img_data))
                if pil_img.mode in ("RGBA", "P"):
                    pil_img = pil_img.convert("RGB")
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=quality, optimize=True)
                img_data = buf.getvalue()

            page_fname = f"{base_name}_page_{page_num + 1}.{out_ext}"
            page_fpath = os.path.join(download_dir, page_fname)
            
            with open(page_fpath, "wb") as f:
                f.write(img_data)
                
            page_files.append({
                "page": page_num + 1,
                "filename": page_fname,
                "filepath": page_fpath,
                "download_url": f"/downloads/{page_fname}",
                "size_bytes": len(img_data),
                "width": pix.width,
                "height": pix.height
            })
            
            if zf:
                zf.writestr(page_fname, img_data)
    finally:
        if zf:
            zf.close()

    zip_filename = None
    zip_download_url = None
    
    if total_pages > 1 and zip_buffer:
        zip_filename = f"{base_name}_all_pages.zip"
        zip_filepath = os.path.join(download_dir, zip_filename)
        with open(zip_filepath, "wb") as f:
            f.write(zip_buffer.getvalue())
        zip_download_url = f"/downloads/{zip_filename}"

    return {
        "success": True,
        "total_pages": total_pages,
        "format": out_ext.upper(),
        "dpi": dpi,
        "pages": page_files,
        "zip_filename": zip_filename,
        "zip_download_url": zip_download_url
    }

def images_to_pdf(
    image_items: List[Tuple[str, bytes]], 
    output_filename: str = "combined_images.pdf"
) -> Dict[str, Any]:
    """
    Combines multiple images (JPG, PNG, WEBP, BMP, GIF, TIFF) into a single PDF document.
    """
    if not image_items:
        raise ValueError("No images provided for conversion.")

    download_dir = get_download_dir()
    clean_name = sanitize_filename(output_filename, "combined_images.pdf")
    if not clean_name.lower().endswith(".pdf"):
        clean_name += ".pdf"

    final_filepath = os.path.join(download_dir, clean_name)
    
    pdf_doc = fitz.open()

    for original_name, img_bytes in image_items:
        try:
            # Load with PIL to ensure valid format and color mode
            pil_img = Image.open(io.BytesIO(img_bytes))
            
            # Convert to RGB if RGBA/P
            if pil_img.mode in ("RGBA", "LA", "P"):
                rgb_img = Image.new("RGB", pil_img.size, (255, 255, 255))
                if pil_img.mode == "P":
                    pil_img = pil_img.convert("RGBA")
                rgb_img.paste(pil_img, mask=pil_img.split()[-1] if len(pil_img.split()) == 4 else None)
                pil_img = rgb_img
            elif pil_img.mode != "RGB":
                pil_img = pil_img.convert("RGB")

            # Save to temporary JPEG buffer for PyMuPDF
            img_buf = io.BytesIO()
            pil_img.save(img_buf, format="JPEG", quality=95)
            img_data = img_buf.getvalue()

            # Insert into PDF page matching image dimensions
            img_rect = fitz.Rect(0, 0, pil_img.width, pil_img.height)
            page = pdf_doc.new_page(width=pil_img.width, height=pil_img.height)
            page.insert_image(img_rect, stream=img_data)

        except Exception as e:
            logger.warning(f"Skipping invalid image {original_name}: {e}")

    if len(pdf_doc) == 0:
        raise ValueError("Could not process any of the provided images.")

    pdf_doc.save(final_filepath, deflate=True)
    pdf_doc.close()

    file_size = os.path.getsize(final_filepath)

    return {
        "success": True,
        "filename": clean_name,
        "filepath": final_filepath,
        "download_url": f"/downloads/{clean_name}",
        "total_pages": len(image_items),
        "size_bytes": file_size
    }

def convert_image(
    image_bytes: bytes, 
    original_filename: str, 
    target_format: str = "jpg", 
    quality: int = 90
) -> Dict[str, Any]:
    """
    Converts an image between formats (JPG, PNG, WEBP, BMP, TIFF, GIF).
    """
    download_dir = get_download_dir()
    target_ext = target_format.lower().strip()
    if target_ext in ["jpeg", "jpg"]:
        target_ext = "jpg"
        pil_fmt = "JPEG"
    elif target_ext == "png":
        pil_fmt = "PNG"
    elif target_ext == "webp":
        pil_fmt = "WEBP"
    elif target_ext == "bmp":
        pil_fmt = "BMP"
    elif target_ext == "tiff":
        pil_fmt = "TIFF"
    else:
        target_ext = "jpg"
        pil_fmt = "JPEG"

    pil_img = Image.open(io.BytesIO(image_bytes))

    # If converting to JPG, handle alpha channel
    if pil_fmt == "JPEG" and pil_img.mode in ("RGBA", "LA", "P"):
        rgb_img = Image.new("RGB", pil_img.size, (255, 255, 255))
        if pil_img.mode == "P":
            pil_img = pil_img.convert("RGBA")
        rgb_img.paste(pil_img, mask=pil_img.split()[-1] if len(pil_img.split()) == 4 else None)
        pil_img = rgb_img

    base_name = os.path.splitext(sanitize_filename(original_filename, "image"))[0]
    out_filename = f"{base_name}.{target_ext}"
    out_filepath = os.path.join(download_dir, out_filename)

    save_kwargs = {}
    if pil_fmt in ["JPEG", "WEBP"]:
        save_kwargs["quality"] = quality
    if pil_fmt == "JPEG":
        save_kwargs["optimize"] = True

    pil_img.save(out_filepath, format=pil_fmt, **save_kwargs)
    file_size = os.path.getsize(out_filepath)

    return {
        "success": True,
        "filename": out_filename,
        "filepath": out_filepath,
        "download_url": f"/downloads/{out_filename}",
        "format": target_ext.upper(),
        "width": pil_img.width,
        "height": pil_img.height,
        "size_bytes": file_size
    }

def merge_pdfs(pdf_items: List[Tuple[str, bytes]], output_filename: str = "merged.pdf") -> Dict[str, Any]:
    """
    Merges multiple PDF files into a single PDF.
    """
    if not pdf_items:
        raise ValueError("No PDF files provided to merge.")

    download_dir = get_download_dir()
    clean_name = sanitize_filename(output_filename, "merged_document.pdf")
    if not clean_name.lower().endswith(".pdf"):
        clean_name += ".pdf"

    final_filepath = os.path.join(download_dir, clean_name)
    
    merged_doc = fitz.open()

    total_pages = 0
    for original_name, pdf_bytes in pdf_items:
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            merged_doc.insert_pdf(doc)
            total_pages += len(doc)
            doc.close()
        except Exception as e:
            logger.warning(f"Skipping corrupt PDF {original_name}: {e}")

    if len(merged_doc) == 0:
        raise ValueError("Could not merge any of the provided PDF documents.")

    merged_doc.save(final_filepath, deflate=True)
    merged_doc.close()

    file_size = os.path.getsize(final_filepath)

    return {
        "success": True,
        "filename": clean_name,
        "filepath": final_filepath,
        "download_url": f"/downloads/{clean_name}",
        "total_pages": total_pages,
        "size_bytes": file_size
    }

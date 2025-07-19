from pdftext.extraction import dictionary_output
import argparse
import json
import pypdfium2 as pdfium
import asyncio
import aiofiles
import io
import base64
import os
from pathlib import Path
from typing import List, Optional, Dict, Any, Union, Tuple
from PIL import Image, ImageDraw
from pdftext.schema import Bbox


def parse_range_str(range_str: str) -> List[int]:
    """Parse a string of page ranges into a list of page numbers.

    Examples:
        "1,2-4,10" -> [0, 1, 2, 3, 9]  # 0-indexed
    """
    pages = []
    for part in range_str.split(","):
        if "-" in part:
            start, end = map(int, part.split("-"))
            pages.extend(range(start - 1, end))  # Convert to 0-indexed
        else:
            pages.append(int(part) - 1)  # Convert to 0-indexed
    return pages


def extract_text_from_pdf(
    pdf_path: str,
    sort: bool = False,
    page_range: Optional[str] = None,
    flatten_pdf: bool = False,
    keep_chars: bool = False,
    keep_hyphens: bool = False,
    workers: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Extract text from PDF synchronously using dictionary_output."""
    pdf_path = Path(pdf_path)

    # Extract page range if provided
    pages = None
    if page_range is not None:
        pdf_doc = pdfium.PdfDocument(pdf_path)
        pages = parse_range_str(page_range)
        doc_len = len(pdf_doc)
        pdf_doc.close()
        if not all(0 <= p < doc_len for p in pages):
            raise ValueError("Invalid page number(s) provided")

    # Extract text using dictionary_output
    extracted_data = dictionary_output(
        pdf_path,
        sort=sort,
        page_range=pages,
        flatten_pdf=flatten_pdf,
        keep_chars=keep_chars,
        workers=workers,
        disable_links=True,
    )

    return extracted_data


def preprocess_image(page_image: Union[str, io.BytesIO]) -> Image.Image:
    """Preprocess the page image from base64 string or BytesIO object."""
    if isinstance(page_image, io.BytesIO):
        image = Image.open(page_image)
    else:
        image_data = base64.b64decode(page_image)
        image = Image.open(io.BytesIO(image_data))
    return image


def resize_image(image: Image.Image, max_size: int) -> Image.Image:
    """Resize image if it exceeds the maximum size."""
    # Calculate current size in bytes (approximate)
    current_size = image.width * image.height * len(image.getbands())

    if current_size <= max_size:
        return image

    # Calculate scale factor to reduce to max_size
    scale_factor = (max_size / current_size) ** 0.5
    new_width = int(image.width * scale_factor)
    new_height = int(image.height * scale_factor)

    return image.resize((new_width, new_height), Image.LANCZOS)


def get_encoded_image(pil_image: Image.Image) -> str:
    """Convert PIL image to base64 encoded string."""
    max_size = 3 * 1024 * 1024  # 3 MB
    pil_image = resize_image(pil_image, max_size)
    img_bytes = io.BytesIO()
    pil_image.save(img_bytes, format="PNG")
    img_bytes = img_bytes.getvalue()
    encoded_img = base64.b64encode(img_bytes).decode("utf-8")
    return encoded_img


def rescale_bbox(
    src_bbox: List[float], dst_bbox: List[float], bbox: List[float]
) -> List[float]:
    """Rescale a bounding box from one coordinate system to another."""
    src_width = src_bbox[2] - src_bbox[0]
    src_height = src_bbox[3] - src_bbox[1]
    dst_width = dst_bbox[2] - dst_bbox[0]
    dst_height = dst_bbox[3] - dst_bbox[1]

    x_scale = dst_width / src_width
    y_scale = dst_height / src_height

    return [
        dst_bbox[0] + (bbox[0] - src_bbox[0]) * x_scale,
        dst_bbox[1] + (bbox[1] - src_bbox[1]) * y_scale,
        dst_bbox[0] + (bbox[2] - src_bbox[0]) * x_scale,
        dst_bbox[1] + (bbox[3] - src_bbox[1]) * y_scale,
    ]


def union_bbox(bbox1: Optional[List[float]], bbox2: List[float]) -> List[float]:
    """Compute the union of two bounding boxes."""
    if bbox1 is None:
        return bbox2
    return [
        min(bbox1[0], bbox2[0]),
        min(bbox1[1], bbox2[1]),
        max(bbox1[2], bbox2[2]),
        max(bbox1[3], bbox2[3]),
    ]


def visualize_bboxes(
    page: Dict[str, Any],
    text_color: str = "red",
    image_color: str = "blue",
    crop_flag: bool = True,
) -> Tuple[str, Image.Image]:
    """Draw bounding boxes on the page image and return the encoded image and PIL Image."""
    # Extract all bboxes from the page
    text_bboxes = []
    image_bboxes = []

    blocks = page.get("blocks", [])
    page_image = page.get("page_image", "")
    width = page.get("width", 0)
    height = page.get("height", 0)

    for block in blocks:
        # all_bboxes.append(block.get('bbox', []))
        for line in block.get("lines", []):
            # all_bboxes.append(line.get('bbox', []))
            for span in line.get("spans", []):
                text_bboxes.append(span.get("bbox", []))

    images = page.get("images", [])
    for image in images:
        image_bboxes.append(image.bbox)

    img = preprocess_image(page_image)
    img_bbox = [0, 0, img.size[0], img.size[1]]

    # Scale page bboxes to image coordinates
    page_bbox = [0, 0, width, height]
    scaled_text_bboxes = [
        rescale_bbox(page_bbox, img_bbox, bbox) for bbox in text_bboxes
    ]
    scaled_image_bboxes = [
        rescale_bbox(page_bbox, img_bbox, bbox) for bbox in image_bboxes
    ]
    all_scaled_bboxes = scaled_text_bboxes + scaled_image_bboxes

    # Draw boxes on the image
    draw = ImageDraw.Draw(img)
    for box in scaled_text_bboxes:
        draw.rectangle(box, outline=text_color, width=1)
    for box in scaled_image_bboxes:
        draw.rectangle(box, outline=image_color, width=1)

    if crop_flag and all_scaled_bboxes:
        # Find the union of all bboxes
        missing_boxes_bound = None
        for box in all_scaled_bboxes:
            missing_boxes_bound = union_bbox(missing_boxes_bound, box)

        # Add some padding
        padding = img.height * 0.05
        crop = (
            max(0, missing_boxes_bound[0] - padding),
            max(0, missing_boxes_bound[1] - padding),
            min(img.width, missing_boxes_bound[2] + padding),
            min(img.height, missing_boxes_bound[3] + padding),
        )

        # Ensure minimum height
        if crop[3] - crop[1] < img.height * 0.1:
            diff = img.height * 0.1 - (crop[3] - crop[1])
            crop = (
                crop[0],
                max(0, crop[1] - diff / 2),
                crop[2],
                min(img.height, crop[3] + diff / 2),
            )

        img = img.crop(crop)

    return get_encoded_image(img), img


async def save_visualization_image(
    image: Image.Image, output_path: str, page_num: int
) -> str:
    """Save visualization image to disk and return the file path."""
    # Create directory if it doesn't exist
    os.makedirs(output_path, exist_ok=True)

    # Generate filename
    filename = f"page_{page_num+1}_visualization.png"
    filepath = os.path.join(output_path, filename)

    # Save image
    image.save(filepath)
    return filepath


async def process_pages_with_ocr(
    extracted_data: List[Dict[str, Any]],
    visualize: bool = False,
    viz_output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Process extracted pages through OCR asynchronously."""
    results = []
    visualization_paths = []

    for page_idx, page_data in enumerate(extracted_data):

        # Visualize bounding boxes if requested
        if visualize:
            _, pil_img = visualize_bboxes(page_data)

            # Always save visualization as separate file
            output_dir = viz_output_dir or os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "visualizations"
            )
            filepath = await save_visualization_image(pil_img, output_dir, page_idx)
            visualization_paths.append(filepath)
            # Count lines in dictionary format
            num_lines = sum(
                len(block.get("lines", [])) for block in page_data.get("blocks", [])
            )
            print(
                f"Page {page_idx+1}: Found {num_lines} lines, saved visualization to {filepath}"
            )

    output = {"pages": results}
    if visualize and visualization_paths:
        output["visualization_paths"] = visualization_paths

    return output


class BboxEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Bbox):
            return obj.bbox
        return super().default(obj)


async def save_output(
    output_data: Dict[str, Any], out_path: Optional[str] = None
) -> None:
    """Save output data to a file or print to stdout."""
    if out_path:
        async with aiofiles.open(out_path, "w") as f:
            await f.write(json.dumps(output_data, cls=BboxEncoder))
    else:
        print(json.dumps(output_data, cls=BboxEncoder))


async def main():
    parser = argparse.ArgumentParser(
        description="Extract plain text or JSON from PDF and process with OCR."
    )
    parser.add_argument("pdf_path", type=str, help="Path to the input PDF file")
    parser.add_argument(
        "--out_path", type=str, help="Path to the output file, defaults to stdout"
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output json instead of plain text",
    )
    parser.add_argument(
        "--sort", action="store_true", help="Attempt to sort the text by reading order"
    )
    parser.add_argument(
        "--keep_hyphens", action="store_true", help="Keep hyphens in words"
    )
    parser.add_argument(
        "--page_range",
        type=str,
        help="Page numbers or ranges to extract, comma separated like 1,2-4,10",
    )
    parser.add_argument(
        "--flatten_pdf",
        action="store_true",
        help="Flatten form fields and annotations into page contents",
    )
    parser.add_argument(
        "--keep_chars", action="store_true", help="Keep character level information"
    )
    parser.add_argument(
        "--workers", type=int, help="Number of workers to use for parallel processing"
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="Visualize bounding boxes on the page image",
    )
    parser.add_argument(
        "--viz_output_dir",
        type=str,
        help="Directory to save visualization images (defaults to ./visualizations)",
    )

    args = parser.parse_args()

    try:
        # Extract text synchronously
        extracted_data = extract_text_from_pdf(
            pdf_path=args.pdf_path,
            sort=args.sort,
            page_range=args.page_range,
            flatten_pdf=args.flatten_pdf,
            keep_chars=args.keep_chars,
            keep_hyphens=args.keep_hyphens,
            workers=args.workers,
        )

        # Process with OCR asynchronously
        ocr_results = await process_pages_with_ocr(
            extracted_data, visualize=args.visualize, viz_output_dir=args.viz_output_dir
        )

        # Save or print results
        if args.json_output:
            # If JSON output is requested, serialize extracted_data instead of ocr_results
            await save_output({"pages": extracted_data}, args.out_path)
        else:
            await save_output(ocr_results, args.out_path)
    except Exception as e:
        print(f"Error processing PDF: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

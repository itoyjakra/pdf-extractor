"""PDF processing utilities - convert PDF pages to images."""

import fitz  # PyMuPDF
from pathlib import Path
from PIL import Image
import io


class PDFProcessor:
    """Handles PDF to image conversion."""

    def __init__(self, dpi: int = 300):
        """Initialize PDF processor.

        Args:
            dpi: Resolution for rendering pages to images
        """
        self.dpi = dpi
        self.zoom = dpi / 72  # PDF default is 72 DPI

    def get_page_count(self, pdf_path: Path) -> int:
        """Get the total number of pages in a PDF.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Number of pages
        """
        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count

    def convert_page_to_image(
        self,
        pdf_path: Path,
        page_num: int
    ) -> Image.Image:
        """Convert a single PDF page to an image.

        Args:
            pdf_path: Path to the PDF file
            page_num: Page number (1-indexed)

        Returns:
            PIL Image of the page
        """
        doc = fitz.open(pdf_path)
        page = doc.load_page(page_num - 1)  # PyMuPDF is 0-indexed

        # Render page to pixmap
        mat = fitz.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=mat)

        # Convert to PIL Image
        img_data = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_data))

        doc.close()
        return image

    def save_page_image(
        self,
        pdf_path: Path,
        page_num: int,
        output_path: Path
    ) -> None:
        """Convert and save a PDF page as an image.

        Args:
            pdf_path: Path to the PDF file
            page_num: Page number (1-indexed)
            output_path: Where to save the image
        """
        image = self.convert_page_to_image(pdf_path, page_num)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, "PNG")

    def convert_all_pages(
        self,
        pdf_path: Path,
        output_dir: Path
    ) -> list[Path]:
        """Convert all PDF pages to images.

        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save images

        Returns:
            List of paths to saved images
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        page_count = self.get_page_count(pdf_path)
        image_paths = []

        for page_num in range(1, page_count + 1):
            output_path = output_dir / f"page_{page_num:03d}.png"
            self.save_page_image(pdf_path, page_num, output_path)
            image_paths.append(output_path)

        return image_paths

    def extract_figures(
        self,
        pdf_path: Path,
        page_num: int,
        output_dir: Path,
        min_size: int = 50
    ) -> list[dict]:
        """Extract figures/images from a PDF page.

        Args:
            pdf_path: Path to the PDF file
            page_num: Page number (1-indexed)
            output_dir: Directory to save extracted figures
            min_size: Minimum dimension (width or height) to consider as a figure

        Returns:
            List of dicts with figure info: {figure_id, path, bbox, width, height}
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        figures = []

        doc = fitz.open(pdf_path)
        page = doc.load_page(page_num - 1)

        # Get all images on the page
        image_list = page.get_images(full=True)

        for img_idx, img_info in enumerate(image_list):
            xref = img_info[0]  # Image xref number

            try:
                # Extract the image
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]

                # Load with PIL to check dimensions
                pil_image = Image.open(io.BytesIO(image_bytes))
                width, height = pil_image.size

                # Skip small images (likely icons, bullets, etc.)
                if width < min_size and height < min_size:
                    continue

                # Generate figure ID and path
                figure_id = f"p{page_num}_fig{img_idx + 1}"
                figure_path = output_dir / f"{figure_id}.{image_ext}"

                # Save the image
                with open(figure_path, "wb") as f:
                    f.write(image_bytes)

                # Try to get bbox (bounding box) for the image on the page
                bbox = None
                for img_rect in page.get_image_rects(xref):
                    bbox = (img_rect.x0, img_rect.y0, img_rect.x1, img_rect.y1)
                    break  # Take first occurrence

                figures.append({
                    "figure_id": figure_id,
                    "path": str(figure_path),
                    "bbox": bbox,
                    "width": width,
                    "height": height,
                })

            except Exception as e:
                # Skip problematic images
                print(f"Warning: Could not extract image {xref}: {e}")
                continue

        doc.close()
        return figures

    def extract_all_figures(
        self,
        pdf_path: Path,
        output_dir: Path,
        min_size: int = 50
    ) -> dict[int, list[dict]]:
        """Extract all figures from all pages.

        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save extracted figures
            min_size: Minimum dimension to consider as a figure

        Returns:
            Dict mapping page numbers to list of figure info dicts
        """
        figures_dir = output_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)

        page_count = self.get_page_count(pdf_path)
        all_figures = {}

        for page_num in range(1, page_count + 1):
            page_figures = self.extract_figures(pdf_path, page_num, figures_dir, min_size)
            if page_figures:
                all_figures[page_num] = page_figures

        return all_figures

    def extract_region_as_image(
        self,
        pdf_path: Path,
        page_num: int,
        bbox: tuple[float, float, float, float],
        output_path: Path,
        padding: int = 10
    ) -> Path:
        """Extract a region of a PDF page as an image.

        Useful for extracting vector drawings/figures by rendering the region.

        Args:
            pdf_path: Path to the PDF file
            page_num: Page number (1-indexed)
            bbox: Bounding box (x0, y0, x1, y1) in PDF coordinates
            output_path: Where to save the image
            padding: Padding around the bbox in pixels

        Returns:
            Path to the saved image
        """
        doc = fitz.open(pdf_path)
        page = doc.load_page(page_num - 1)

        # Create clip rectangle with padding
        x0, y0, x1, y1 = bbox
        clip = fitz.Rect(x0 - padding, y0 - padding, x1 + padding, y1 + padding)

        # Render the clipped region
        mat = fitz.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=mat, clip=clip)

        # Save as PNG
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(output_path))

        doc.close()
        return output_path

    def detect_drawing_regions(
        self,
        pdf_path: Path,
        page_num: int,
        min_drawings: int = 3,
        merge_distance: float = 20
    ) -> list[tuple[float, float, float, float]]:
        """Detect regions containing vector drawings (potential figures).

        Groups nearby drawings into figure regions.

        Args:
            pdf_path: Path to the PDF file
            page_num: Page number (1-indexed)
            min_drawings: Minimum number of drawings to consider as a figure
            merge_distance: Distance threshold for merging nearby drawings

        Returns:
            List of bounding boxes (x0, y0, x1, y1) for detected figure regions
        """
        doc = fitz.open(pdf_path)
        page = doc.load_page(page_num - 1)

        drawings = page.get_drawings()
        if len(drawings) < min_drawings:
            doc.close()
            return []

        # Get bounding boxes of all drawings
        bboxes = []
        for d in drawings:
            if d.get("rect"):
                rect = d["rect"]
                bboxes.append((rect.x0, rect.y0, rect.x1, rect.y1))

        if not bboxes:
            doc.close()
            return []

        # Simple clustering: merge overlapping/nearby bboxes
        def boxes_overlap(b1, b2, distance=merge_distance):
            return not (b1[2] + distance < b2[0] or
                       b2[2] + distance < b1[0] or
                       b1[3] + distance < b2[1] or
                       b2[3] + distance < b1[1])

        def merge_boxes(b1, b2):
            return (min(b1[0], b2[0]), min(b1[1], b2[1]),
                   max(b1[2], b2[2]), max(b1[3], b2[3]))

        # Iteratively merge overlapping boxes
        merged = list(bboxes)
        changed = True
        while changed:
            changed = False
            new_merged = []
            used = set()
            for i, b1 in enumerate(merged):
                if i in used:
                    continue
                current = b1
                for j, b2 in enumerate(merged[i+1:], i+1):
                    if j in used:
                        continue
                    if boxes_overlap(current, b2):
                        current = merge_boxes(current, b2)
                        used.add(j)
                        changed = True
                new_merged.append(current)
                used.add(i)
            merged = new_merged

        # Filter out very small regions
        min_size = 30
        regions = [b for b in merged if (b[2] - b[0]) > min_size and (b[3] - b[1]) > min_size]

        doc.close()
        return regions

    def extract_vector_figures(
        self,
        pdf_path: Path,
        output_dir: Path,
        min_drawings: int = 3
    ) -> dict[int, list[dict]]:
        """Extract vector figures from all pages.

        Detects drawing regions and renders them as images.

        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save extracted figures
            min_drawings: Minimum drawings to consider as a figure

        Returns:
            Dict mapping page numbers to list of figure info dicts
        """
        figures_dir = output_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)

        page_count = self.get_page_count(pdf_path)
        all_figures = {}

        for page_num in range(1, page_count + 1):
            regions = self.detect_drawing_regions(pdf_path, page_num, min_drawings)

            if regions:
                page_figures = []
                for idx, bbox in enumerate(regions):
                    figure_id = f"p{page_num}_fig{idx + 1}"
                    figure_path = figures_dir / f"{figure_id}.png"

                    self.extract_region_as_image(
                        pdf_path, page_num, bbox, figure_path
                    )

                    page_figures.append({
                        "figure_id": figure_id,
                        "path": str(figure_path),
                        "bbox": bbox,
                        "width": int(bbox[2] - bbox[0]),
                        "height": int(bbox[3] - bbox[1]),
                    })

                all_figures[page_num] = page_figures

        return all_figures

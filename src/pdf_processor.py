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

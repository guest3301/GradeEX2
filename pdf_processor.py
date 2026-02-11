"""
=============================================================================
PDF Processor for Mumbai University Grade Records
=============================================================================

Handles PDF cropping operations using fixed coordinates for student records.

Coordinate System (from image):
- P1: (26, 59)    Top-left of first student
- P2: (765, 59)   Top-right of first student
- P3: (25, 206)   Bottom-left of first student
- P4: (769, 206)  Bottom-right of first student
- P5: (768, 347)  Bottom-right of second student
- P6: (26, 349)   Bottom-left of second student

Author: GitHub Copilot
Date: 2026-02-09
Version: 2.0
=============================================================================
"""

import fitz  # PyMuPDF
import os
from typing import List, Tuple, Optional


class PdfProcessor:
    """PDF processing class with fixed coordinates for student record cropping"""
    
    # Fixed coordinates for student record cropping based on standard PDF layout
    STUDENT_BLOCK_COORDS = {
        'x_left': 25,      # Left margin
        'x_right': 769,    # Right margin
        'student_heights': [
            (59, 206),     # First student on page
            (206, 349),    # Second student on page
            (349, 490),    # Third student (estimated from pattern)
            (490, 631),    # Fourth student (estimated from pattern)
            (631, 772),    # Fifth student (estimated from pattern)
        ]
    }
    
    def __init__(self, input_path=None, output_path=None, rect_coords=None):
        """
        Initialize PDF processor.
        
        Args:
            input_path: Path to input PDF (optional, for legacy compatibility)
            output_path: Path to output PDF (optional, for legacy compatibility)
            rect_coords: Rectangle coordinates (optional, for legacy compatibility)
        """
        self.input_path = input_path
        self.output_path = output_path
        self.rect_coords = rect_coords

    def crop_pdf(self, page):
        """
        Legacy method - crop a single page to specified rectangle.
        
        Args:
            page: Page number (0-indexed)
        """
        # rect_coords: (x0, y0, x1, y1)
        doc = fitz.open(self.input_path)
        page = doc[page]    
        page.set_cropbox(fitz.Rect(self.rect_coords))
        doc.save(self.output_path)
        doc.close()
    
    @staticmethod
    def crop_single_student(input_pdf_path: str, page_num: int, 
                           student_index: int, output_path: str) -> bool:
        """
        Crop a single student record from a page using fixed coordinates.
        
        Args:
            input_pdf_path: Source PDF file path
            page_num: Page number (0-indexed)
            student_index: Student position on page (0-indexed, 0=first student)
            output_path: Output PDF file path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate student index
            if student_index >= len(PdfProcessor.STUDENT_BLOCK_COORDS['student_heights']):
                print(f"Warning: Student index {student_index} exceeds known coordinates")
                return False
            
            # Get coordinates for this student position
            x_left = PdfProcessor.STUDENT_BLOCK_COORDS['x_left']
            x_right = PdfProcessor.STUDENT_BLOCK_COORDS['x_right']
            y_top, y_bottom = PdfProcessor.STUDENT_BLOCK_COORDS['student_heights'][student_index]
            
            # Open source PDF
            doc = fitz.open(input_pdf_path)
            
            # Validate page number
            if page_num >= len(doc):
                print(f"Error: Page {page_num} does not exist in PDF")
                doc.close()
                return False
            
            # Get the page
            page = doc[page_num]
            
            # Create cropping rectangle
            crop_rect = fitz.Rect(x_left, y_top, x_right, y_bottom)
            
            # Set crop box
            page.set_cropbox(crop_rect)
            
            # Create new document with just this page
            output_doc = fitz.open()
            output_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save cropped page
            output_doc.save(output_path)
            output_doc.close()
            doc.close()
            
            return True
            
        except Exception as e:
            print(f"Error cropping student {student_index} from page {page_num}: {e}")
            return False
    
    @staticmethod
    def crop_multiple_students(input_pdf_path: str, 
                               page_crops: List[dict]) -> List[str]:
        """
        Crop multiple student records from various pages.
        
        Args:
            input_pdf_path: Source PDF file path
            page_crops: List of dicts with format:
                        [{'page': 2, 'student_index': 0, 'output_path': 'path/to/output.pdf'}, ...]
            
        Returns:
            List of successfully created file paths
        """
        successful_crops = []
        
        for crop_info in page_crops:
            page_num = crop_info['page']
            student_index = crop_info['student_index']
            output_path = crop_info['output_path']
            
            if PdfProcessor.crop_single_student(input_pdf_path, page_num, 
                                               student_index, output_path):
                successful_crops.append(output_path)
        
        return successful_crops
    
    @staticmethod
    def get_student_coordinates(student_index: int) -> Optional[Tuple[int, int, int, int]]:
        """
        Get the fixed coordinates for a student at a given position.
        
        Args:
            student_index: Student position on page (0-indexed)
            
        Returns:
            Tuple of (x_left, y_top, x_right, y_bottom) or None if invalid index
        """
        if student_index >= len(PdfProcessor.STUDENT_BLOCK_COORDS['student_heights']):
            return None
        
        x_left = PdfProcessor.STUDENT_BLOCK_COORDS['x_left']
        x_right = PdfProcessor.STUDENT_BLOCK_COORDS['x_right']
        y_top, y_bottom = PdfProcessor.STUDENT_BLOCK_COORDS['student_heights'][student_index]
        
        return (x_left, y_top, x_right, y_bottom)

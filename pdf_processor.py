"""
=============================================================================
PDF Processor for Mumbai University Grade Records
=============================================================================

Handles PDF cropping operations using dynamic detection of separator lines.

FEATURES:
---------
Dynamic Cropping (DEFAULT): Automatically detects horizontal separator lines to 
determine student record boundaries. Works with varying layouts.

DYNAMIC DETECTION:
------------------
The processor detects horizontal dashed separator lines that divide
student records. It looks for:
- 2 lines for pages with 1 student (top and bottom separators)
- 3 lines for pages with 2 students (top, middle, and bottom separators)

The detection process:
1. Scans page for horizontal vector graphics (lines/thin rectangles)
2. Filters lines longer than threshold (default 200 points)
3. Groups nearby lines together (within 5 points)
4. Interprets results to identify student boundaries

DEBUG OUTPUT:
-------------
All methods provide comprehensive debug output showing:
- Line detection progress
- Detected coordinates
- Student boundary calculations
- Success/failure status

MAIN METHODS (Dynamic Detection):
----------------------------------
# Crop single student (most common use case):
PdfProcessor.crop_single_student(pdf_path, page, student_idx, output)

# Auto-detect and crop all students on a page:
PdfProcessor.crop_all_students_on_page(pdf_path, page, output_dir, basename)

# Batch crop multiple students:
page_crops = [
    {'page': 0, 'student_index': 0, 'output_path': 'out1.pdf'},
    {'page': 0, 'student_index': 1, 'output_path': 'out2.pdf'},
]
PdfProcessor.crop_multiple_students(pdf_path, page_crops)

LEGACY METHODS (Fixed Coordinates):
------------------------------------
For backward compatibility, fixed-coordinate methods are available:
- crop_single_student_fixed()
- crop_multiple_students_fixed()

These use predefined Y-coordinates and are less flexible.

Author: GitHub Copilot
Date: 2026-02-12
Version: 5.0 - Dynamic detection as default
=============================================================================
"""

import fitz  # PyMuPDF
import os
from typing import List, Tuple, Optional, Dict


class PdfProcessor:
    """PDF processing class with fixed coordinates for student record cropping"""
    
    # Fixed coordinates for student record cropping based on actual PDF layout analysis
    # Coordinates determined from visual analysis of sample grade cards
    STUDENT_BLOCK_COORDS = {
        'x_left': 0,       # Left margin - starting from very beginning
        'x_right': None,   # Right margin - will use full page width dynamically
        # Y-coordinates for different student positions
        # When 1 student on page: (91, 326)
        # When 2 students on page: Student 1 (91, 294), Student 2 (294, 497)
        'student_heights': [
            (91, 294),     # First student (top)
            (294, 497),    # Second student (bottom)
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
    def detect_horizontal_lines(page, min_line_length: float = 100, debug: bool = True) -> List[float]:
        """
        Detect horizontal separator lines on a PDF page using vector paths.
        
        Args:
            page: PyMuPDF page object
            min_line_length: Minimum length for a line to be considered (default 100 points)
            debug: If True, print debug information
            
        Returns:
            List of Y-coordinates of detected horizontal lines, sorted top to bottom
        """
        horizontal_lines = []
        line_count = 0
        rect_count = 0
        
        if debug:
            print(f"\n[DEBUG] Starting line detection...")
            print(f"[DEBUG] Page dimensions: {page.rect.width:.2f} x {page.rect.height:.2f}")
            print(f"[DEBUG] Min line length threshold: {min_line_length}")
        
        try:
            # Get all vector drawings on the page
            paths = page.get_drawings()
            if debug:
                print(f"[DEBUG] Found {len(paths)} drawing paths on page")
            
            for path_idx, path in enumerate(paths):
                # Each path has items which are drawing commands
                for item in path.get("items", []):
                    # item[0] is the drawing command type
                    # 'l' = line, 're' = rectangle, etc.
                    if item[0] == "l":  # Line command
                        line_count += 1
                        # item[1] and item[2] are start and end points
                        p1 = item[1]  # Start point (x, y)
                        p2 = item[2]  # End point (x, y)
                        
                        # Check if line is horizontal (y-coordinates are similar)
                        y_diff = abs(p1.y - p2.y)
                        x_length = abs(p2.x - p1.x)
                        
                        # Consider it horizontal if y difference is small and line is long enough
                        if y_diff < 3 and x_length >= min_line_length:
                            y_coord = (p1.y + p2.y) / 2
                            horizontal_lines.append(y_coord)
                            if debug:
                                print(f"[DEBUG]   ✓ Line: Y={y_coord:.2f}, X=[{p1.x:.2f} to {p2.x:.2f}], Length={x_length:.2f}")
                        elif debug and y_diff < 3:
                            print(f"[DEBUG]   ✗ Line too short: Y={p1.y:.2f}, Length={x_length:.2f} < {min_line_length}")
                    
                    elif item[0] == "re":  # Rectangle (might be used for lines)
                        rect_count += 1
                        # item[1] is the rectangle
                        rect = item[1]
                        # Check if it's a thin horizontal rectangle (acts as a line)
                        if rect.height < 3 and rect.width >= min_line_length:
                            y_coord = (rect.y0 + rect.y1) / 2
                            horizontal_lines.append(y_coord)
                            if debug:
                                print(f"[DEBUG]   ✓ Rect: Y={y_coord:.2f}, Width={rect.width:.2f}, Height={rect.height:.2f}")
                        elif debug and rect.height < 3:
                            print(f"[DEBUG]   ✗ Rect too short: Y={rect.y0:.2f}, Width={rect.width:.2f} < {min_line_length}")
        
        except Exception as e:
            print(f"[ERROR] Error detecting lines: {e}")
            import traceback
            traceback.print_exc()
            return []
        
        if debug:
            print(f"\n[DEBUG] Processed {line_count} lines and {rect_count} rectangles")
            print(f"[DEBUG] Found {len(horizontal_lines)} horizontal lines before deduplication")
        
        # Sort lines from top to bottom
        horizontal_lines.sort()
        
        # Deduplicate nearby lines (group lines within 5 points of each other)
        deduplicated = PdfProcessor._deduplicate_lines(horizontal_lines, threshold=5, debug=debug)
        
        if debug:
            print(f"[DEBUG] After deduplication: {len(deduplicated)} lines")
            for i, y in enumerate(deduplicated):
                print(f"[DEBUG]   Line {i+1}: Y = {y:.2f}")
        
        return deduplicated
    
    @staticmethod
    def _deduplicate_lines(lines: List[float], threshold: float = 5, debug: bool = False) -> List[float]:
        """
        Group nearby horizontal lines and return their average positions.
        
        Args:
            lines: List of Y-coordinates
            threshold: Maximum distance to group lines together
            debug: If True, print debug information
            
        Returns:
            Deduplicated list of Y-coordinates
        """
        if not lines:
            return []
        
        if debug:
            print(f"\n[DEBUG] Deduplicating {len(lines)} lines with threshold={threshold}")
        
        deduplicated = []
        current_group = [lines[0]]
        
        for i in range(1, len(lines)):
            if lines[i] - lines[i-1] <= threshold:
                # Add to current group
                current_group.append(lines[i])
                if debug:
                    print(f"[DEBUG]   Grouping line at Y={lines[i]:.2f} with previous (distance={lines[i] - lines[i-1]:.2f})")
            else:
                # Save average of current group and start new group
                avg = sum(current_group) / len(current_group)
                deduplicated.append(avg)
                if debug:
                    print(f"[DEBUG]   Group complete: {len(current_group)} lines averaged to Y={avg:.2f}")
                current_group = [lines[i]]
        
        # Don't forget the last group
        if current_group:
            avg = sum(current_group) / len(current_group)
            deduplicated.append(avg)
            if debug:
                print(f"[DEBUG]   Final group: {len(current_group)} lines averaged to Y={avg:.2f}")
        
        return deduplicated
    
    @staticmethod
    def detect_student_boundaries(page, min_line_length: float = 200, debug: bool = True) -> Dict:
        """
        Detect student record boundaries on a page based on horizontal separator lines.
        
        Args:
            page: PyMuPDF page object
            min_line_length: Minimum length for separator lines
            debug: If True, print debug information
            
        Returns:
            Dictionary with student boundaries:
            {
                'num_students': int (1 or 2),
                'students': [
                    {'y_top': float, 'y_bottom': float},
                    ...
                ]
            }
        """
        if debug:
            print(f"\n{'='*70}")
            print(f"DETECTING STUDENT BOUNDARIES")
            print(f"{'='*70}")
        
        # Detect horizontal lines
        lines = PdfProcessor.detect_horizontal_lines(page, min_line_length=min_line_length, debug=debug)
        
        # Filter lines that are likely separator lines (spanning most of page width)
        # We expect 2 lines for 1 student, 3 lines for 2 students
        
        result = {
            'num_students': 0,
            'students': [],
            'detected_lines': lines
        }
        
        if debug:
            print(f"\n[DEBUG] Analyzing {len(lines)} detected lines...")
        
        if len(lines) >= 3:
            # Two students case: 3 or more lines detected
            # Use first 3 lines: top separator, middle separator, bottom separator
            result['num_students'] = 2
            result['students'] = [
                {'y_top': lines[0], 'y_bottom': lines[1]},  # First student
                {'y_top': lines[1], 'y_bottom': lines[2]}   # Second student
            ]
            if debug:
                print(f"[DEBUG] ✓ TWO STUDENTS detected (3+ lines found)")
                print(f"[DEBUG]   Student 1: Y {lines[0]:.2f} to {lines[1]:.2f} (height: {lines[1]-lines[0]:.2f})")
                print(f"[DEBUG]   Student 2: Y {lines[1]:.2f} to {lines[2]:.2f} (height: {lines[2]-lines[1]:.2f})")
        elif len(lines) >= 2:
            # One student case: 2 lines detected
            # Use first 2 lines: top separator and bottom separator
            result['num_students'] = 1
            result['students'] = [
                {'y_top': lines[0], 'y_bottom': lines[1]}  # Single student
            ]
            if debug:
                print(f"[DEBUG] ✓ ONE STUDENT detected (2 lines found)")
                print(f"[DEBUG]   Student 1: Y {lines[0]:.2f} to {lines[1]:.2f} (height: {lines[1]-lines[0]:.2f})")
        else:
            # Not enough lines detected
            result['num_students'] = 0
            if debug:
                print(f"[DEBUG] ✗ DETECTION FAILED: Only {len(lines)} line(s) found, need at least 2")
        
        if debug:
            print(f"{'='*70}\n")
        
        return result
    
    @staticmethod
    def crop_single_student(input_pdf_path: str, page_num: int, 
                           student_index: int, output_path: str,
                           total_students_on_page: int = None) -> bool:
        """
        Crop a single student record from a page using DYNAMIC detection of separator lines.
        
        Args:
            input_pdf_path: Source PDF file path
            page_num: Page number (0-indexed)
            student_index: Student position on page (0-indexed, 0=first/top student, 1=second/bottom)
            output_path: Output PDF file path
            total_students_on_page: IGNORED - kept for backward compatibility
            
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"\n{'='*70}")
            print(f"CROPPING STUDENT RECORD")
            print(f"{'='*70}")
            print(f"Input PDF: {input_pdf_path}")
            print(f"Page: {page_num}")
            print(f"Student Index: {student_index}")
            print(f"Output: {output_path}")
            
            # Open source PDF
            doc = fitz.open(input_pdf_path)
            
            # Validate page number
            if page_num >= len(doc):
                print(f"\n[ERROR] Page {page_num} does not exist in PDF (total pages: {len(doc)})")
                doc.close()
                return False
            
            # Get the page
            page = doc[page_num]
            page_width = page.rect.width
            page_height = page.rect.height
            
            print(f"\n[INFO] Page dimensions: {page_width:.2f} x {page_height:.2f}")
            
            # Detect student boundaries dynamically
            boundaries = PdfProcessor.detect_student_boundaries(page, debug=True)
            
            # Check if we detected enough boundaries
            if boundaries['num_students'] == 0:
                print(f"\n[ERROR] Could not detect separator lines!")
                print(f"[ERROR] No students detected on this page.")
                doc.close()
                return False
            
            # Validate student index
            if student_index >= len(boundaries['students']):
                print(f"\n[ERROR] Student index {student_index} exceeds detected students "
                      f"({len(boundaries['students'])})")
                doc.close()
                return False
            
            # Get the boundaries for this specific student
            student_bounds = boundaries['students'][student_index]
            x_left = 0
            x_right = page_width
            y_top = student_bounds['y_top']
            y_bottom = student_bounds['y_bottom']
            
            print(f"\n[INFO] Cropping coordinates for student {student_index}:")
            print(f"[INFO]   X: {x_left:.2f} to {x_right:.2f}")
            print(f"[INFO]   Y: {y_top:.2f} to {y_bottom:.2f}")
            print(f"[INFO]   Crop dimensions: {x_right - x_left:.2f} x {y_bottom - y_top:.2f}")
            
            # Create cropping rectangle
            crop_rect = fitz.Rect(x_left, y_top, x_right, y_bottom)
            
            # Set crop box
            page.set_cropbox(crop_rect)
            
            # Create new document with just this page
            output_doc = fitz.open()
            output_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            
            # Ensure output directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            # Save cropped page
            output_doc.save(output_path)
            output_doc.close()
            doc.close()
            
            print(f"\n[SUCCESS] ✓ Cropped student record saved to: {output_path}")
            print(f"{'='*70}\n")
            
            return True
            
        except Exception as e:
            print(f"\n[ERROR] Error in dynamic cropping for student {student_index} from page {page_num}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    @staticmethod
    def crop_single_student_fixed(input_pdf_path: str, page_num: int, 
                                 student_index: int, output_path: str,
                                 total_students_on_page: int = 2) -> bool:
        """
        LEGACY: Crop a single student record from a page using FIXED coordinates.
        Use crop_single_student() instead for dynamic detection.
        
        Args:
            input_pdf_path: Source PDF file path
            page_num: Page number (0-indexed)
            student_index: Student position on page (0-indexed, 0=first/top student, 1=second/bottom)
            output_path: Output PDF file path
            total_students_on_page: Total number of students on this page (1 or 2)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate student index
            if student_index >= len(PdfProcessor.STUDENT_BLOCK_COORDS['student_heights']):
                print(f"Warning: Student index {student_index} exceeds known coordinates (max 1)")
                return False
            
            # Validate total students
            if total_students_on_page not in [1, 2]:
                print(f"Warning: Expected 1 or 2 students per page, got {total_students_on_page}")
                # Default to 2 for safety
                total_students_on_page = 2
            
            # Open source PDF first to get page dimensions
            doc = fitz.open(input_pdf_path)
            
            # Validate page number
            if page_num >= len(doc):
                print(f"Error: Page {page_num} does not exist in PDF")
                doc.close()
                return False
            
            # Get the page
            page = doc[page_num]
            
            # Get coordinates for this student position
            x_left = PdfProcessor.STUDENT_BLOCK_COORDS['x_left']
            x_right = page.rect.width  # Use full page width dynamically
            y_top, y_bottom = PdfProcessor.STUDENT_BLOCK_COORDS['student_heights'][student_index]
            
            # If only 1 student on page and it's the first one, use extended bottom
            # to capture full record
            if total_students_on_page == 1 and student_index == 0:
                y_bottom = 326  # Extended for single student page
            
            # Create cropping rectangle
            crop_rect = fitz.Rect(x_left, y_top, x_right, y_bottom)
            
            # Set crop box
            page.set_cropbox(crop_rect)
            
            # Create new document with just this page
            output_doc = fitz.open()
            output_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            
            # Ensure output directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir:  # Only create if there's a directory path
                os.makedirs(output_dir, exist_ok=True)
            
            # Save cropped page
            output_doc.save(output_path)
            output_doc.close()
            doc.close()
            
            return True
            
        except Exception as e:
            print(f"Error cropping student {student_index} from page {page_num}: {e}")
            return False
    
    @staticmethod
    def crop_multiple_students_fixed(input_pdf_path: str, 
                                    page_crops: List[dict]) -> List[str]:
        """
        LEGACY: Crop multiple student records using FIXED coordinates.
        Use crop_multiple_students() instead for dynamic detection.
        
        Args:
            input_pdf_path: Source PDF file path
            page_crops: List of dicts with format:
                        [{'page': 2, 'student_index': 0, 'output_path': 'path/to/output.pdf', 
                          'total_students_on_page': 2}, ...]
                        'total_students_on_page' is optional, defaults to 2
            
        Returns:
            List of successfully created file paths
        """
        successful_crops = []
        
        for crop_info in page_crops:
            page_num = crop_info['page']
            student_index = crop_info['student_index']
            output_path = crop_info['output_path']
            total_students = crop_info.get('total_students_on_page', 2)
            
            if PdfProcessor.crop_single_student_fixed(input_pdf_path, page_num, 
                                                     student_index, output_path,
                                                     total_students_on_page=total_students):
                successful_crops.append(output_path)
        
        return successful_crops
    
    @staticmethod
    def crop_multiple_students(input_pdf_path: str, 
                              page_crops: List[dict]) -> List[str]:
        """
        Crop multiple student records from various pages using DYNAMIC line detection.
        
        Args:
            input_pdf_path: Source PDF file path
            page_crops: List of dicts with format:
                        [{'page': 2, 'student_index': 0, 'output_path': 'path/to/output.pdf'}, ...]
            
        Returns:
            List of successfully created file paths
        """
        successful_crops = []
        
        print(f"\n{'#'*70}")
        print(f"BATCH CROPPING: {len(page_crops)} student(s)")
        print(f"{'#'*70}\n")
        
        for i, crop_info in enumerate(page_crops, 1):
            page_num = crop_info['page']
            student_index = crop_info['student_index']
            output_path = crop_info['output_path']
            
            print(f"\n[BATCH {i}/{len(page_crops)}] Processing...")
            
            if PdfProcessor.crop_single_student(input_pdf_path, page_num, 
                                               student_index, output_path):
                successful_crops.append(output_path)
                print(f"[BATCH {i}/{len(page_crops)}] ✓ Success")
            else:
                print(f"[BATCH {i}/{len(page_crops)}] ✗ Failed")
        
        print(f"\n{'#'*70}")
        print(f"BATCH COMPLETE: {len(successful_crops)}/{len(page_crops)} successful")
        print(f"{'#'*70}\n")
        
        return successful_crops
    
    @staticmethod
    def crop_all_students_on_page(input_pdf_path: str, page_num: int,
                                  output_dir: str, base_filename: str) -> List[str]:
        """
        Automatically detect and crop ALL student records on a single page.
        
        Args:
            input_pdf_path: Source PDF file path
            page_num: Page number (0-indexed)
            output_dir: Directory to save cropped PDFs
            base_filename: Base name for output files (will append _student_0, _student_1, etc.)
            
        Returns:
            List of successfully created file paths
        """
        try:
            print(f"\n{'#'*70}")
            print(f"AUTO-CROP ALL STUDENTS ON PAGE")
            print(f"{'#'*70}")
            print(f"Input: {input_pdf_path}")
            print(f"Page: {page_num}")
            print(f"Output directory: {output_dir}")
            print(f"Base filename: {base_filename}")
            
            doc = fitz.open(input_pdf_path)
            if page_num >= len(doc):
                print(f"\n[ERROR] Page {page_num} does not exist in PDF (total pages: {len(doc)})")
                doc.close()
                return []
            
            page = doc[page_num]
            boundaries = PdfProcessor.detect_student_boundaries(page, debug=True)
            doc.close()
            
            num_students = boundaries['num_students']
            
            if num_students == 0:
                print(f"\n[ERROR] No students detected on page {page_num}")
                return []
            
            print(f"\n[INFO] Will crop {num_students} student(s)")
            
            # Crop each detected student
            successful_crops = []
            for student_idx in range(num_students):
                output_path = os.path.join(output_dir, f"{base_filename}_student_{student_idx}.pdf")
                if PdfProcessor.crop_single_student_dynamic(input_pdf_path, page_num,
                                                           student_idx, output_path):
                    successful_crops.append(output_path)
            
            print(f"\n{'#'*70}")
            print(f"AUTO-CROP COMPLETE: {len(successful_crops)}/{num_students} successful")
            print(f"{'#'*70}\n")
            
            return successful_crops
            
        except Exception as e:
            print(f"\n[ERROR] Error cropping all students on page {page_num}: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    @staticmethod
    def get_student_coordinates(student_index: int, total_students_on_page: int = 2, page_width: float = 770) -> Optional[Tuple[int, int, int, int]]:
        """
        Get the fixed coordinates for a student at a given position.
        
        Args:
            student_index: Student position on page (0-indexed, 0=top, 1=bottom)
            total_students_on_page: Total number of students on this page (1 or 2)
            page_width: Width of the page (default 770, or pass actual page width)
            
        Returns:
            Tuple of (x_left, y_top, x_right, y_bottom) or None if invalid index
        """
        if student_index >= len(PdfProcessor.STUDENT_BLOCK_COORDS['student_heights']):
            return None
        
        x_left = PdfProcessor.STUDENT_BLOCK_COORDS['x_left']
        x_right = page_width  # Use provided or default page width
        y_top, y_bottom = PdfProcessor.STUDENT_BLOCK_COORDS['student_heights'][student_index]
        
        # If single student on page, extend bottom
        if total_students_on_page == 1 and student_index == 0:
            y_bottom = 326
        
        return (x_left, y_top, x_right, y_bottom)

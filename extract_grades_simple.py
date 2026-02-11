"""
=============================================================================
Mumbai University Grade Sheet Extractor (Simplified)
=============================================================================

Extracts basic student information from Mumbai University result PDFs.
Focuses on identification data only - no grade parsing.

Extracted Data:
- Student: ERN, name, first_name, seat_no, gender, college
- Exam: title, month, year, declaration date
- Result: PASS/FAIL status

Author: GitHub Copilot
Date: 2026-02-09
Version: 2.0
=============================================================================
"""

import os
import re
import sys
import pdfplumber
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional


class MumbaiUniversityGradeExtractor:
    """
    Simplified extractor for Mumbai University grade sheets.
    
    Focuses on:
    - Student identification (ERN, name, seat number)
    - Page classification (index vs student record pages)
    - Basic status extraction (PASS/FAIL)
    - Exam metadata (title, date, declaration date)
    """
    
    def __init__(self, pdf_path: str, output_dir: str = '.'):
        """
        Initialize the extractor.
        
        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory for logs
        """
        self.pdf_path = pdf_path
        self.output_dir = output_dir
        self.exam_metadata = {}

        self._setup_logging()
        
    def _setup_logging(self):
        """Configure logging to file and console"""
        log_file = os.path.join(self.output_dir, 'extraction_log.txt')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def is_index_page(self, page_text: str) -> bool:
        """
        Check if page is an index page (no student records).
        
        Index pages don't have "SEAT NO" text.
        
        Args:
            page_text: Full text of the page
            
        Returns:
            True if index page, False if student record page
        """
        return 'SEAT NO' not in page_text
    
    def extract_exam_metadata(self, first_page) -> Dict[str, Any]:
        """
        Extract exam information from first page.
        
        Args:
            first_page: pdfplumber first page object
            
        Returns:
            Dictionary with exam_title, exam_month, exam_year, declaration_date
        """
        text = first_page.extract_text()
        if not text:
            return {}
        
        lines = text.split('\n')
        
        exam_title = None
        exam_month = None
        exam_year = None
        declaration_date = None
        
        # Extract exam title (line with "OFFICE REGISTER FOR THE")
        for line in lines:
            if 'OFFICE REGISTER FOR THE' in line:
                exam_title = line.strip()
                
                # Extract month and year from title
                # Pattern: "HELD IN MONTH YEAR"
                month_year_match = re.search(r'HELD IN (\w+)\s+(\d{4})', exam_title)
                if month_year_match:
                    exam_month = month_year_match.group(1)
                    exam_year = int(month_year_match.group(2))
                
                break
        
        # Extract declaration date if present
        # Pattern: "Declaration Date:Jan 27, 2026" or "Declaration Date: Jan 27, 2026"
        for line in lines:
            if 'Declaration Date' in line:
                date_match = re.search(r'Declaration Date:\s*(\w+\s+\d+,\s+\d{4})', line)
                if date_match:
                    date_str = date_match.group(1)
                    try:
                        # Parse "Jan 27, 2026" format
                        parsed_date = datetime.strptime(date_str, '%b %d, %Y')
                        declaration_date = parsed_date.strftime('%Y-%m-%d')
                    except ValueError:
                        # Try alternative formats
                        try:
                            parsed_date = datetime.strptime(date_str, '%B %d, %Y')
                            declaration_date = parsed_date.strftime('%Y-%m-%d')
                        except ValueError:
                            declaration_date = date_str
                break
        
        return {
            'exam_title': exam_title,
            'exam_month': exam_month,
            'exam_year': exam_year,
            'declaration_date': declaration_date
        }
    
    def count_students_on_page(self, page_text: str) -> int:
        """
        Count number of student records on a page.
        
        Args:
            page_text: Full text of the page
            
        Returns:
            Number of students (count of 9-digit seat numbers)
        """
        # Find all lines starting with 9-digit seat number followed by uppercase letters
        matches = re.findall(r'^\d{9}\s+[A-Z]', page_text, re.MULTILINE)
        return len(matches)
    
    def find_student_blocks(self, page_text: str) -> List[str]:
        """
        Split page text into individual student record blocks.
        
        Args:
            page_text: Full text of the page
            
        Returns:
            List of text blocks, one per student
        """
        lines = page_text.split('\n')
        
        # Find lines that start with seat numbers (9 digits)
        student_start_indices = []
        for i, line in enumerate(lines):
            # Seat number pattern: 9 digits followed by uppercase letters
            if re.match(r'^\d{9}\s+[A-Z]', line.strip()):
                # Check if previous line has ERN (edge case handling)
                if i > 0 and re.match(r'^\(MU\d+', lines[i-1].strip()):
                    student_start_indices.append(i - 1)  # Include ERN line
                else:
                    student_start_indices.append(i)
                
        # Extract blocks between start indices
        blocks = []
        for i in range(len(student_start_indices)):
            start = student_start_indices[i]
            end = student_start_indices[i + 1] if i + 1 < len(student_start_indices) else len(lines)
            
            block_lines = lines[start:end]
            # Only include blocks that have E1, I1, TOT (complete records)
            block_text = '\n'.join(block_lines)
            if 'E1' in block_text and 'I1' in block_text and 'TOT' in block_text:
                blocks.append(block_text)
        
        return blocks
    
    def parse_student_basic_info(self, block_text: str, page_number: int) -> Dict[str, Any]:
        """
        Extract only basic student information (no grades).
        
        Args:
            block_text: Text block containing one student's record
            page_number: PDF page number where this record appears
            
        Returns:
            Dictionary with seat_no, name, first_name, ern, gender, college, status, result
        """
        lines = [l.strip() for l in block_text.split('\n') if l.strip()]
        
        student = {
            'seat_no': None,
            'name': None,
            'first_name': None,
            'status': None,
            'gender': None,
            'ern': None,
            'college': None,
            'college_code': None,
            'result': None,
            'page_number': page_number
        }
        
        # === PARSE HEADER SECTION ===
        # Join header lines (before E1) and normalize
        header_lines = []
        for line in lines:
            if line.startswith('E1'):
                break
            header_lines.append(line)
        
        # Join all header content and normalize whitespace
        header = ' '.join(header_lines)
        header = re.sub(r'\s+', ' ', header).strip()
        
        # Find the seat number line
        seat_line = None
        for line in header_lines:
            if re.match(r'^\d{9}\s+[A-Z]', line.strip()):
                seat_line = line
                break
        
        if seat_line:
            tokens = seat_line.split()
            
            # Extract seat number (first token, must be 9 digits)
            if tokens and re.match(r'^\d{9}$', tokens[0]):
                student['seat_no'] = tokens[0]
                
                # Extract name (uppercase tokens after seat number, before status keywords)
                name_tokens = []
                for token in tokens[1:]:
                    # Stop at status keywords or parentheses
                    if token.upper() in ['REGULAR', 'ATKT', 'EX-STUDENT', 'FEMALE', 'MALE'] or token.startswith('('):
                        break
                    # Only include uppercase words
                    if token.isupper() and token.isalpha():
                        name_tokens.append(token)
                
                if name_tokens:
                    student['name'] = ' '.join(name_tokens)
                    student['first_name'] = name_tokens[0]
            
            # Extract status (Regular, ATKT, etc.)
            if 'REGULAR' in seat_line.upper():
                student['status'] = 'Regular'
            elif 'ATKT' in seat_line.upper():
                student['status'] = 'ATKT'
            elif 'EX-STUDENT' in seat_line.upper():
                student['status'] = 'Ex-Student'
            
            # Extract gender
            if 'FEMALE' in seat_line.upper():
                student['gender'] = 'F'
            elif 'MALE' in seat_line.upper():
                student['gender'] = 'M'
        
        # ERN - search in full header (MU followed by digits)
        ern_match = re.search(r'\(MU(\d+)', header)
        if ern_match:
            student['ern'] = 'MU' + ern_match.group(1)
        
        # College code and name (after MU-XXXX:)
        college_match = re.search(r'(MU-\d+):\s*(.+?)(?:\s+\d{7}|$)', header)
        if college_match:
            student['college_code'] = college_match.group(1)
            student['college'] = college_match.group(2).strip()
        
        # === EXTRACT RESULT (PASS/FAIL) ===
        # Look for I1 row which contains result
        for line in lines:
            if line.startswith('I1'):
                # Result appears as "PASS" or "FAIL" after the marks
                if 'PASS' in line.upper():
                    student['result'] = 'PASS'
                elif 'FAIL' in line.upper():
                    student['result'] = 'FAIL'
                break
        
        return student
    
    def validate_student_record(self, student: Dict[str, Any]) -> bool:
        """
        Validate that a student record has minimum required fields.
        
        Args:
            student: Student data dictionary
            
        Returns:
            True if record is valid, False otherwise
        """
        required_fields = ['seat_no', 'name', 'result']
        
        for field in required_fields:
            if not student.get(field):
                self.logger.warning(f"Invalid record - missing {field}: {student.get('seat_no', 'unknown')}")
                return False
        
        return True
    
    def process_pdf(self) -> Dict[str, Any]:
        """
        Main processing method - extracts basic student info from PDF.
        
        Returns:
            Dictionary containing exam_metadata and student records
        """
        self.logger.info(f"Starting extraction from: {self.pdf_path}")
        
        all_students = []
        
        with pdfplumber.open(self.pdf_path) as pdf:
            self.logger.info(f"PDF has {len(pdf.pages)} pages")
            
            # Extract exam metadata from first page
            self.logger.info("Extracting exam metadata...")
            self.exam_metadata = self.extract_exam_metadata(pdf.pages[0])
            self.logger.info(f"Exam: {self.exam_metadata.get('exam_title', 'Unknown')}")
            
            if self.exam_metadata.get('exam_month') and self.exam_metadata.get('exam_year'):
                self.logger.info(f"Month: {self.exam_metadata['exam_month']} {self.exam_metadata['exam_year']}")
            
            if self.exam_metadata.get('declaration_date'):
                self.logger.info(f"Declaration Date: {self.exam_metadata['declaration_date']}")
            
            # Process each page
            for page_num, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if not page_text:
                    continue
                
                # Skip index pages
                if self.is_index_page(page_text):
                    self.logger.info(f"Page {page_num + 1}: Index page (skipping)")
                    continue
                
                # Count students on this page
                student_count = self.count_students_on_page(page_text)
                self.logger.info(f"Page {page_num + 1}: Found {student_count} student(s)")
                
                # Extract student blocks
                blocks = self.find_student_blocks(page_text)
                self.logger.info(f"Page {page_num + 1}: Extracted {len(blocks)} complete record(s)")
                
                # Parse each student block
                for block_idx, block in enumerate(blocks):
                    student = self.parse_student_basic_info(block, page_num)
                    
                    if self.validate_student_record(student):
                        all_students.append(student)
                        self.logger.debug(
                            f"  Student {block_idx + 1}: {student['seat_no']} - "
                            f"{student['name']} ({student['result']})"
                        )
                    else:
                        self.logger.warning(f"  Student {block_idx + 1}: Invalid record - skipping")
        
        self.logger.info(f"\nTotal valid records extracted: {len(all_students)}")
        
        return {
            'exam_metadata': self.exam_metadata,
            'students': all_students
        }


def main():
    """
    Main execution function with command-line argument handling.
    """
    print("="*70)
    print("Mumbai University Grade Sheet Extractor v2.0 (Simplified)")
    print("="*70)
    print()

    if len(sys.argv) < 2:
        print("Usage: python extract_grades_simple.py <pdf_file> [output_directory]")
        print()
        print("Example:")
        print("  python extract_grades_simple.py results.pdf")
        print("  python extract_grades_simple.py results.pdf ./output/")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else '.'

    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found: {pdf_path}")
        sys.exit(1)
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")

    try:
        extractor = MumbaiUniversityGradeExtractor(pdf_path, output_dir)
        extracted_data = extractor.process_pdf()
        
        if extracted_data['students']:
            print()
            print("="*70)
            print("EXTRACTION COMPLETED SUCCESSFULLY")
            print("="*70)
            print(f"\nTotal students extracted: {len(extracted_data['students'])}")
            print(f"Exam: {extracted_data['exam_metadata'].get('exam_title', 'Unknown')}")
            
            # Show sample students
            print("\nSample students:")
            for student in extracted_data['students'][:5]:
                print(f"  {student['seat_no']} - {student['name']} - {student['result']}")
            
            if len(extracted_data['students']) > 5:
                print(f"  ... and {len(extracted_data['students']) - 5} more")
            
        else:
            print("\nWarning: No valid student records found")
            
    except Exception as e:
        print(f"\nError during extraction: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

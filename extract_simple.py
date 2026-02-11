"""
=============================================================================
Simplified Student Record Extractor
=============================================================================
Lightweight extraction of student basic info (no detailed grades).
Extracts: ERN, name, seat number, status, result for PDF cropping.
=============================================================================
"""

import pdfplumber
import re
import logging
from typing import List, Dict, Optional


class SimpleStudentExtractor:
    """Simplified extractor for student basic information"""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.logger = logging.getLogger(__name__)
    
    def is_index_page(self, page_text: str) -> bool:
        """Check if page is an index page (no student records)"""
        return 'SEAT NO' not in page_text
    
    def extract_exam_metadata(self, pages: List) -> Dict:
        """
        Extract exam metadata from first page.
        
        Returns:
            Dict with: exam_title, exam_month, exam_year, declaration_date
        """
        metadata = {
            'exam_title': None,
            'exam_month': None,
            'exam_year': None,
            'declaration_date': None
        }
        
        if not pages:
            return metadata
        
        first_page_text = pages[0].extract_text()
        if not first_page_text:
            return metadata
        
        lines = first_page_text.split('\n')
        
        # Extract exam title (line starting with "OFFICE REGISTER FOR")
        for line in lines:
            if 'OFFICE REGISTER FOR' in line:
                # Extract full title
                title_match = re.search(r'OFFICE REGISTER FOR THE (.+)', line)
                if title_match:
                    metadata['exam_title'] = title_match.group(1).strip()
                
                # Extract month and year from title
                month_year = re.search(r'HELD IN (\w+)\s+(\d{4})', line)
                if month_year:
                    metadata['exam_month'] = month_year.group(1)
                    metadata['exam_year'] = int(month_year.group(2))
                break
        
        # Extract declaration date
        for line in lines[:20]:  # Check first 20 lines
            decl_match = re.search(r'Declaration Date:\s*(\w+\s+\d+,\s+\d{4})', line)
            if decl_match:
                metadata['declaration_date'] = decl_match.group(1)
                break
        
        return metadata
    
    def count_students_on_page(self, page_text: str) -> int:
        """Count number of student records on a page"""
        # Count lines starting with 9-digit seat numbers
        seat_numbers = re.findall(r'^\d{9}\s+[A-Z]', page_text, re.MULTILINE)
        return len(seat_numbers)
    
    def find_student_blocks(self, page_text: str) -> List[str]:
        """
        Identify and extract individual student record blocks.
        
        Returns:
            List of text blocks, one per student
        """
        lines = page_text.split('\n')
        
        # Find lines that start with seat numbers (9 digits)
        student_start_indices = []
        for i, line in enumerate(lines):
            # Check if previous line has ERN (edge case)
            if i > 0 and re.match(r'^\(MU\d+', lines[i-1].strip()):
                if re.match(r'^\d{9}\s+[A-Z]', line.strip()):
                    student_start_indices.append(i - 1)
                    continue
            
            # Standard case: seat number at start of line
            if re.match(r'^\d{9}\s+[A-Z]', line.strip()):
                student_start_indices.append(i)
        
        # Extract blocks between start indices
        blocks = []
        for i in range(len(student_start_indices)):
            start = student_start_indices[i]
            end = student_start_indices[i + 1] if i + 1 < len(student_start_indices) else len(lines)
            
            block_lines = lines[start:end]
            block_text = '\n'.join(block_lines)
            
            # Only include complete blocks with required rows
            if 'I1' in block_text and 'TOT' in block_text:
                blocks.append(block_text)
        
        return blocks
    
    def extract_student_basic_info(self, block_text: str, page_number: int, 
                                   student_index: int) -> Optional[Dict]:
        """
        Extract only essential student information.
        
        Args:
            block_text: Text block containing one student's record
            page_number: PDF page number
            student_index: Student position on page (0-indexed)
            
        Returns:
            Dict with: ern, name, first_name, seat_no, status, gender, result
        """
        lines = [l.strip() for l in block_text.split('\n') if l.strip()]
        
        student = {
            'ern': None,
            'name': None,
            'first_name': None,
            'seat_no': None,
            'status': None,
            'gender': None,
            'result': None,
            'page_number': page_number,
            'student_index': student_index,
            'college_code': None,
            'college_name': None
        }
        
        # Join all lines into single text for easier parsing
        full_text = ' '.join(lines)
        
        # Extract seat number (9 digits at start of a line)
        seat_match = re.search(r'\b(\d{9})\s+([A-Z][A-Z\s]+?)(?:\s+(?:Regular|Repeater|ATKT|Ex-Student)|(?:\s+(?:MALE|FEMALE)))', full_text)
        if seat_match:
            student['seat_no'] = seat_match.group(1)
            # Extract name (everything after seat number until status/gender keyword)
            name_part = seat_match.group(2).strip()
            student['name'] = ' '.join(name_part.split())  # Normalize whitespace
            
            # Extract first name
            name_parts = student['name'].split()
            if name_parts:
                student['first_name'] = name_parts[0]
        
        # Extract ERN
        ern_match = re.search(r'\(MU(\d+)\)', full_text)
        if ern_match:
            student['ern'] = 'MU' + ern_match.group(1)
        
        # Extract status
        status_match = re.search(r'\b(Regular|Repeater|ATKT|Ex-Student)\b', full_text)
        if status_match:
            student['status'] = status_match.group(1)
        
        # Extract gender
        gender_match = re.search(r'\b(MALE|FEMALE)\b', full_text)
        if gender_match:
            student['gender'] = gender_match.group(1)[0]  # M or F
        
        # Extract college code and name
        college_match = re.search(r'(MU-\d+):\s*(.+?)(?:\s+E1|\s+MAR|\s*$)', full_text)
        if college_match:
            student['college_code'] = college_match.group(1)
            student['college_name'] = college_match.group(2).strip()
        
        # Extract result (PASS/FAIL) - look for keywords in full text
        if 'PASS' in full_text or 'PAS' in full_text:
            student['result'] = 'PASS'
        elif 'FAIL' in full_text or 'FAI' in full_text:
            student['result'] = 'FAIL'
        
        # Validation - require essential fields
        if not student['seat_no'] or not student['name'] or not student['result']:
            self.logger.warning(
                f"Incomplete student record on page {page_number}, index {student_index}: "
                f"seat={student['seat_no']}, name={student['name']}, result={student['result']}"
            )
            return None
        
        return student
    
    def process_pdf(self) -> Dict:
        """
        Process PDF and extract all student basic information.
        
        Returns:
            Dict with: exam_metadata, students (list)
        """
        self.logger.info(f"Processing PDF: {self.pdf_path}")
        
        all_students = []
        exam_metadata = {}
        
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                self.logger.info(f"PDF has {len(pdf.pages)} pages")
                
                # Extract exam metadata from first page
                exam_metadata = self.extract_exam_metadata(pdf.pages)
                self.logger.info(f"Exam: {exam_metadata.get('exam_title', 'Unknown')}")
                
                # Process each page
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if not page_text:
                        continue
                    
                    # Skip index pages
                    if self.is_index_page(page_text):
                        self.logger.debug(f"Page {page_num + 1} is an index page, skipping")
                        continue
                    
                    # Count students on page
                    student_count = self.count_students_on_page(page_text)
                    self.logger.info(f"Page {page_num + 1}: Found {student_count} students")
                    
                    # Extract student blocks
                    blocks = self.find_student_blocks(page_text)
                    
                    # Process each student block
                    for student_index, block in enumerate(blocks):
                        student = self.extract_student_basic_info(block, page_num, student_index)
                        if student:
                            all_students.append(student)
                            self.logger.debug(f"  Student {student_index + 1}: {student['seat_no']} - {student['name']}")
                
                self.logger.info(f"Total students extracted: {len(all_students)}")
        
        except Exception as e:
            self.logger.error(f"Error processing PDF: {e}")
            raise
        
        return {
            'exam_metadata': exam_metadata,
            'students': all_students
        }

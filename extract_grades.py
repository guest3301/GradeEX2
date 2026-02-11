"""
=============================================================================
University of Mumbai Grade Sheet Extractor
=============================================================================

This script extracts student grade data from University of Mumbai result PDFs.
It uses position-based parsing instead of regex for robustness with 
variable-length text fields.

Author: Claude
Date: 2026-02-03
Version: 1.0

Usage:
    python extract_grades.py <pdf_file_path> [output_directory]

Example:
    python extract_grades.py results.pdf ./output/
    
Output:
    - student_grades.csv: CSV file with all student data
    - student_grades.xlsx: Excel file with all student data
    - extraction_log.txt: Detailed extraction log
=============================================================================
"""

import pdfplumber
import pandas as pd
import re
import sys
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging


class MumbaiUniversityGradeExtractor:
    """
    Robust extractor for Mumbai University grade sheets.
    
    Key Features:
    - Position-based text extraction (not dependent on exact text length)
    - Handles variable-length subject names
    - Multiple validation checks
    - Detailed logging
    - Database storage support with page tracking
    - Subject code mapping from index pages
    """
    
    def __init__(self, pdf_path: str, output_dir: str = '.', db_session=None):
        """
        Initialize the extractor.
        
        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save output files
            db_session: Optional SQLAlchemy database session
        """
        self.pdf_path = pdf_path
        self.output_dir = output_dir
        self.db_session = db_session
        self.students = []
        self.subject_mapping = {}  # {code: name}
        self.subject_order = []  # Ordered list of subject codes
        self.exam_metadata = {}  # Exam title, footer, etc.

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
        
    def extract_index_data(self, pages: List) -> Dict[str, Any]:
        """
        Extract subject codes, exam metadata, and footer from index pages.
        
        Args:
            pages: List of pdfplumber page objects (scan first 20 pages)
            
        Returns:
            Dictionary with exam_metadata, subject_mapping, subject_order
        """
        subject_mapping = {}
        subject_order = []
        exam_title = None
        exam_month = None
        exam_year = None
        parsed_program_name = None
        parsed_semester = None
        parsed_exam_type = None
        footer_metadata = None
        
        for page_num, page in enumerate(pages[:20]):  # Scan up to 20 pages
            text = page.extract_text()
            if not text:
                continue
            
            lines = text.split('\n')
            
            # Extract exam title from first page (line with "Bachelor")
            if page_num == 0 and not exam_title:
                for line in lines:
                    if 'Bachelor' in line or 'OFFICE REGISTER' in line:
                        exam_title = line.strip()
                        
                        # Parse structured metadata from title
                        # Format: "OFFICE REGISTER FOR THE Bachelor of ... (Semester - III) (NEP 2020) REGULAR EXAMINATION HELD IN DECEMBER 2025"
                        
                        # Extract exam month and year (e.g., "HELD IN DECEMBER 2025")
                        month_year_match = re.search(r'HELD IN (\w+)\s+(\d{4})', line)
                        if month_year_match:
                            exam_month = month_year_match.group(1)  # "DECEMBER"
                            exam_year = int(month_year_match.group(2))  # 2025
                        
                        # Extract exam type (REGULAR or SUPPLEMENTARY)
                        if 'SUPPLEMENTARY' in line:
                            parsed_exam_type = 'SUPPLEMENTARY'
                        elif 'REGULAR' in line:
                            parsed_exam_type = 'REGULAR'
                        
                        # Extract semester (e.g., "Semester - III")
                        semester_match = re.search(r'\(\s*Semester\s*-\s*([IVX]+)\s*\)', line)
                        if semester_match:
                            parsed_semester = f"Semester - {semester_match.group(1)}"
                        
                        # Extract program name (between "FOR THE" and first parenthesis)
                        program_match = re.search(r'FOR THE\s+(.+?)\s*\(', line)
                        if program_match:
                            parsed_program_name = program_match.group(1).strip()
                        
                        break
            
            # Extract footer metadata (lines with special markers)
            if page_num == 0 and not footer_metadata:
                footer_lines = []
                for line in lines:
                    if any(marker in line for marker in ['#:', '@:', 'ADC:', 'AA/ABS:']):
                        footer_lines.append(line.strip())
                if footer_lines:
                    footer_metadata = '\n'.join(footer_lines)
            
            # Extract ALL subjects from course table (format: "1234567 Subject Name 2.00 8.00 20.00...")
            # This is on index pages before student records start
            if 'SEAT NO' not in text:  # Index page, not student record page
                # First try table extraction (more robust)
                tables = page.extract_tables()
                for table in tables:
                    if table and len(table) > 0:
                        # Look for table with "Course Code" header
                        for row in table:
                            if row and len(row) >= 2:
                                # Check if first cell is a 7-digit code
                                first_cell = str(row[0]).strip()
                                if re.match(r'^\d{7}$', first_cell):
                                    code = first_cell
                                    # Second cell is the subject name
                                    full_name = str(row[1]).strip()
                                    # Clean up the name
                                    full_name = re.sub(r'\s+', ' ', full_name)
                                    
                                    if code and code not in subject_mapping:
                                        subject_mapping[code] = full_name
                                        subject_order.append(code)
                
                # Fallback: Extract from text lines
                for line in lines:
                    # Match lines with subject code at start followed by name and credit info
                    match = re.match(r'^(\d{7})\s+(.+?)\s+2\.00\s+8\.00', line)
                    if match:
                        code = match.group(1)
                        full_name = match.group(2).strip()
                        # Clean up the name
                        full_name = re.sub(r'\s+', ' ', full_name)
                        
                        if code not in subject_mapping:
                            subject_mapping[code] = full_name
                            subject_order.append(code)
        return {
            'exam_title': exam_title,
            'exam_month': exam_month,
            'exam_year': exam_year,
            'parsed_program_name': parsed_program_name,
            'parsed_semester': parsed_semester,
            'parsed_exam_type': parsed_exam_type,
            'footer_metadata': footer_metadata,
            'subject_mapping': subject_mapping,
            'subject_order': subject_order
        }
    
    def find_student_blocks(self, page_text: str) -> List[str]:
        """
        Identify and extract individual student record blocks.
        
        Student records are identified by:
        1. Starting with a 9-digit seat number
        2. Followed by name in capital letters
        3. Contains E1, I1, and TOT rows
        
        Handles edge case where ERN is on a separate line before the seat number.
        
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
                # Check if previous line has ERN (starts with (MU) - edge case for multi-line ERN
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
    
    def parse_student_record(self, block_text: str, page_number: int, page_subject_codes: List[str] = None) -> Dict[str, Any]:
        """
        Parse a complete student record from text block.
        
        This method uses structural parsing instead of regex to handle
        variable-length fields robustly.
        
        Args:
            block_text: Text block containing one student's complete record
            page_number: PDF page number where this record appears
            page_subject_codes: Subject codes from page-level header (optional)
            
        Returns:
            Dictionary with student information and marks
        """
        lines = [l.strip() for l in block_text.split('\n') if l.strip()]
        
        # Initialize with empty list
        if page_subject_codes is None:
            page_subject_codes = []

        student = {
            'seat_no': None,
            'name': None,
            'status': None,
            'gender': None,
            'ern': None,
            'college': None,
            'college_code': None,
            'subject_codes': [],  # NEW: Track which subjects this student has
            'external_marks': [],
            'internal_marks': [],
            'total_marks_list': [],
            'grade_points': [],
            'grades': [],
            'credits': [],
            'grade_credits': [],
            'total_marks': None,
            'result': None,
            'sgpa': None,
            'total_credits': None,
            'page_number': page_number
        }
        
        # === PARSE HEADER SECTION ===
        # Handle edge case where ERN might be on separate line before seat number
        # Join header lines (before E1) and normalize for parsing
        header_lines = []
        for line in lines:
            if line.startswith('E1'):
                break
            header_lines.append(line)
        
        # Join all header content and normalize whitespace
        header = ' '.join(header_lines)
        header = re.sub(r'\s+', ' ', header).strip()
        
        # Extract subject codes for this student from the ENTIRE block text
        # (codes appear in column headers which may be before E1 or after TOT)
        # De-duplicate preserving order since codes repeat per student on the page
        all_block_codes = re.findall(r'(\d{7})\s*:', block_text)
        seen = set()
        subject_codes = []
        for code in all_block_codes:
            if code not in seen:
                seen.add(code)
                subject_codes.append(code)
        
        # Fallback to page-level codes (already de-duplicated by caller)
        if not subject_codes and page_subject_codes:
            subject_codes = page_subject_codes
        
        student['subject_codes'] = subject_codes
        
        # Find the seat number line for name/status parsing
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
                
                # Find status keyword (Regular, ATKT, etc.)
                status_keywords = ['Regular', 'ATKT', 'Ex-Student']
                status_idx = None
                for i, token in enumerate(tokens):
                    if token in status_keywords:
                        status_idx = i
                        student['status'] = token
                        break
                
                # Name is between seat number and status
                if status_idx and status_idx > 1:
                    student['name'] = ' '.join(tokens[1:status_idx])
                
                # Gender follows status
                gender_keywords = ['MALE', 'FEMALE', 'OTHER']
                if status_idx and status_idx + 1 < len(tokens):
                    if tokens[status_idx + 1] in gender_keywords:
                        student['gender'] = tokens[status_idx + 1]
        
        # ERN - search in full header (handles multi-line case)
        # Pattern: (MU followed by digits, may have ) on same or different line
        ern_match = re.search(r'\(MU(\d+)', header)
        if ern_match:
            student['ern'] = 'MU' + ern_match.group(1)
        
        # College code and name (after MU-XXXX:)
        college_match = re.search(r'(MU-\d+):\s*(.+?)(?:\s*$|$)', header)
        if college_match:
            student['college_code'] = college_match.group(1)
            student['college'] = college_match.group(2).strip()
        
        # === PARSE MARKS ROWS ===
        num_subject_codes = len(subject_codes)
        
        for line in lines:
            # External marks row (E1)
            if line.startswith('E1'):
                # Handle both passing marks (XX P) and failing marks (XX 0 F 0.0)
                # Get content between E1 and MARKS
                content = re.sub(r'^E1\s+', '', line)
                content = re.sub(r'\s*MARKS.*$', '', content)
                
                marks = []
                # Match: digit(s) followed by P (pass), or digit(s) followed by grade info 0 F (fail)
                for m in re.finditer(r'(\d+)\s*(?:P|0\s+F\s+\d+\.\d+)', content):
                    marks.append(int(m.group(1)))
                
                # Only take as many marks as we have subject codes
                if num_subject_codes > 0 and len(marks) > num_subject_codes:
                    marks = marks[:num_subject_codes]
                
                student['external_marks'] = marks
                
            # Internal marks row (I1)
            elif line.startswith('I1'):
                # Split at ( to get only the actual marks (before total marks)
                marks_portion = line.split('(')[0] if '(' in line else line
                # Match digits followed by P (all internal marks have P since they're pass/present)
                marks = re.findall(r'(\d+)\s*P', marks_portion)
                
                # Only take as many marks as we have subject codes
                if num_subject_codes > 0 and len(marks) > num_subject_codes:
                    marks = marks[:num_subject_codes]
                
                student['internal_marks'] = [int(m) for m in marks]  # All matches are marks
                
                # Total marks in parentheses - handle both (XXX) PASS and (XXX) FAILED
                total_match = re.search(r'\((\d+)\)\s*(?:PASS|FAIL)', line)
                if total_match:
                    student['total_marks'] = int(total_match.group(1))
                
                # Result after total marks (handle both PASS and FAILED)
                if 'PASS' in line:
                    student['result'] = 'PASS'
                elif 'FAIL' in line:
                    student['result'] = 'FAIL'
                    
            # Total marks row (TOT)
            elif line.startswith('TOT'):
                # Structure: TOT [subject data...] total_credits sum_of_g*c sgpa
                # Extract from right to left
                
                # 1. Extract SGPA (rightmost decimal)
                sgpa_match = re.search(r'(\d+\.\d+)\s*$', line)
                if sgpa_match:
                    student['sgpa'] = float(sgpa_match.group(1))
                    line = line[:sgpa_match.start()].strip()
                
                # 2. Extract Sum of G*C (next decimal from right)
                sum_gc_match = re.search(r'(\d+\.\d+)\s*$', line)
                if sum_gc_match:
                    line = line[:sum_gc_match.start()].strip()
                
                # 3. Extract total credits (rightmost integer)
                credits_match = re.search(r'(\d+)\s*$', line)
                if credits_match:
                    student['total_credits'] = int(credits_match.group(1))
                    line = line[:credits_match.start()].strip()
                
                # 4. Now parse subject data
                # Pattern per subject: total grade_point grade credit g*c
                parts = line.split()
                
                i = 1  # Start after 'TOT'
                while i < len(parts) and len(student['total_marks_list']) < num_subject_codes:
                    try:
                        # Each subject has 5 fields: total grade_point grade credit g*c
                        if parts[i].isdigit():
                            total = int(parts[i])
                            if 0 <= total <= 50 and i + 4 < len(parts):
                                # Verify: grade_point (digit), grade (letter), credit, g*c
                                grade_point_str = parts[i + 1]
                                grade = parts[i + 2]
                                credit_str = parts[i + 3]
                                gc_str = parts[i + 4]
                                
                                if grade_point_str.isdigit() and not grade.replace('+', '').replace('-', '').isdigit():
                                    student['total_marks_list'].append(total)
                                    student['grade_points'].append(int(grade_point_str))
                                    student['grades'].append(grade)
                                    try:
                                        student['credits'].append(float(credit_str))
                                    except ValueError:
                                        student['credits'].append(2.0)
                                    try:
                                        student['grade_credits'].append(float(gc_str))
                                    except ValueError:
                                        student['grade_credits'].append(None)
                                    i += 5  # Move to next subject (5 fields per subject)
                                else:
                                    i += 1
                            else:
                                i += 1
                        else:
                            i += 1
                    except (IndexError, ValueError):
                        break
        
        return student
    
    def validate_student_record(self, student: Dict[str, Any]) -> bool:
        """
        Validate that a student record has required fields.
        
        Args:
            student: Student data dictionary
            
        Returns:
            True if record is valid, False otherwise
        """
        required_fields = ['seat_no', 'name', 'status', 'result']
        
        for field in required_fields:
            if not student.get(field):
                self.logger.warning(f"Invalid record - missing {field}")
                return False
        
        # Validate marks consistency
        num_subjects = len(student['external_marks'])
        if num_subjects == 0:
            self.logger.warning(f"Invalid record - no marks found for {student['seat_no']}")
            return False
        
        # All mark lists should have same length (allow grade_points to be optional)
        if not (len(student['internal_marks']) == num_subjects and
                len(student['total_marks_list']) == num_subjects and
                len(student['grades']) == num_subjects):
            self.logger.warning(
                f"Inconsistent marks for {student['seat_no']}: "
                f"E={len(student['external_marks'])}, "
                f"I={len(student['internal_marks'])}, "
                f"T={len(student['total_marks_list'])}, "
                f"G={len(student['grades'])}"
            )
            return False
        
        return True
    
    def process_pdf(self) -> Dict[str, Any]:
        """
        Main processing method - extracts all student records from PDF.
        
        Returns:
            Dictionary containing exam_metadata, subject info, and student records
        """
        self.logger.info(f"Starting extraction from: {self.pdf_path}")
        
        all_students = []
        
        with pdfplumber.open(self.pdf_path) as pdf:
            self.logger.info(f"PDF has {len(pdf.pages)} pages")
            
            # Extract index data (subjects, exam metadata)
            self.logger.info("Extracting index data...")
            index_data = self.extract_index_data(pdf.pages)
            self.subject_mapping = index_data['subject_mapping']
            self.subject_order = index_data['subject_order']
            self.exam_metadata = {
                'exam_title': index_data['exam_title'],
                'exam_month': index_data['exam_month'],
                'exam_year': index_data['exam_year'],
                'parsed_program_name': index_data['parsed_program_name'],
                'parsed_semester': index_data['parsed_semester'],
                'parsed_exam_type': index_data['parsed_exam_type'],
                'footer_metadata': index_data['footer_metadata']
            }
            
            self.logger.info(f"Found {len(self.subject_mapping)} subject codes from index pages")
            if self.subject_mapping:
                self.logger.info("Subject codes extracted:")
                for code in self.subject_order[:5]:  # Show first 5 as sample
                    self.logger.info(f"  {code}: {self.subject_mapping[code][:50]}...")
                if len(self.subject_order) > 5:
                    self.logger.info(f"  ... and {len(self.subject_order) - 5} more subjects")
            self.logger.info(f"Exam title: {self.exam_metadata.get('exam_title', 'N/A')}")
            if index_data['exam_month'] and index_data['exam_year']:
                self.logger.info(f"Exam held: {index_data['exam_month']} {index_data['exam_year']}")
            if index_data['parsed_exam_type']:
                self.logger.info(f"Exam type: {index_data['parsed_exam_type']}")
            
            # Process each page for student records
            for page_num, page in enumerate(pdf.pages):
                self.logger.info(f"Processing page {page_num + 1}/{len(pdf.pages)}")
                
                # Skip header pages (usually first 1-2 pages)
                if page_num < 1:
                    continue
                
                # Extract text and find student blocks
                page_text = page.extract_text()
                if not page_text:
                    self.logger.warning(f"Page {page_num + 1} has no extractable text")
                    continue
                
                # Extract page-level subject codes (appears as column header per student)
                # De-duplicate since codes repeat for each student on the page
                page_subject_codes_raw = re.findall(r'(\d{7})\s*:', page_text)
                seen_codes = set()
                page_subject_codes = []
                for code in page_subject_codes_raw:
                    if code not in seen_codes:
                        seen_codes.add(code)
                        page_subject_codes.append(code)
                if page_subject_codes:
                    self.logger.debug(f"  Page {page_num + 1} has {len(page_subject_codes)} unique subject codes in header")
                
                student_blocks = self.find_student_blocks(page_text)
                self.logger.info(f"  Found {len(student_blocks)} student record(s)")
                
                # Parse each student block
                for block in student_blocks:
                    # Pass page-level subject codes to parser
                    student = self.parse_student_record(block, page_num + 1, page_subject_codes)  # 1-indexed
                    
                    if self.validate_student_record(student):
                        all_students.append(student)
                        num_marks = len(student['external_marks'])
                        num_codes = len(student.get('subject_codes', []))
                        self.logger.info(
                            f"  ✓ {student['seat_no']}: {student['name']} - "
                            f"{student['result']} (SGPA: {student['sgpa']}, {num_marks} subjects, {num_codes} codes) [Page {page_num + 1}]"
                        )
                    else:
                        self.logger.error(f"  ✗ Invalid record skipped on page {page_num + 1}")
        
        self.logger.info(f"\nTotal valid records extracted: {len(all_students)}")
        
        return {
            'exam_metadata': self.exam_metadata,
            'subject_mapping': self.subject_mapping,
            'subject_order': self.subject_order,
            'students': all_students
        }
    
    def save_to_database(self, extracted_data: Dict[str, Any], exam_info: Dict[str, str]) -> bool:
        """
        Save extracted data to database.
        
        Args:
            extracted_data: Dict from process_pdf() with students and metadata
            exam_info: Dict with program_code, semester, exam_type, result_date, pdf_url
            
        Returns:
            True if successful, False otherwise
        """
        if not self.db_session:
            self.logger.error("No database session provided")
            return False
        
        try:
            from models import Program, Examination, Student, StudentExamRecord, Subject, Grade
            from datetime import datetime
            
            # 1. Ensure program exists
            program = self.db_session.query(Program).filter_by(
                program_code=exam_info['program_code']
            ).first()
            
            if not program:
                program = Program(
                    program_code=exam_info['program_code'],
                    program_name=exam_info.get('program_name', 'Unknown Program')
                )
                self.db_session.add(program)
                self.logger.info(f"Created program: {program.program_code}")
            
            # 2. Create or get examination record
            exam = self.db_session.query(Examination).filter_by(
                program_code=exam_info['program_code'],
                semester=exam_info['semester'],
                exam_type=exam_info['exam_type'],
                result_date=exam_info['result_date']
            ).first()
            
            if not exam:
                exam = Examination(
                    program_code=exam_info['program_code'],
                    semester=exam_info['semester'],
                    exam_type=exam_info['exam_type'],
                    result_date=exam_info['result_date'],
                    exam_title=extracted_data['exam_metadata'].get('exam_title'),
                    exam_month=extracted_data['exam_metadata'].get('exam_month'),
                    exam_year=extracted_data['exam_metadata'].get('exam_year'),
                    footer_metadata=extracted_data['exam_metadata'].get('footer_metadata'),
                    pdf_filename=os.path.basename(self.pdf_path),
                    pdf_url=exam_info.get('pdf_url')
                )
                self.db_session.add(exam)
                self.db_session.flush()  # Get exam.id
                self.logger.info(f"Created examination record: {exam.id}")
            else:
                self.logger.info(f"Using existing examination record: {exam.id}")
            
            # 3. Create/update subjects
            for code, name in extracted_data['subject_mapping'].items():
                subject = self.db_session.query(Subject).filter_by(subject_code=code).first()
                if not subject:
                    subject = Subject(
                        subject_code=code,
                        subject_name=name,
                        credits=2.0  # Default, will be overridden per exam
                    )
                    self.db_session.add(subject)
            
            self.db_session.flush()
            self.logger.info(f"Processed {len(extracted_data['subject_mapping'])} subjects")
            
            # 4. Process each student
            students_processed = 0
            grades_created = 0
            
            for student_data in extracted_data['students']:
                ern = student_data.get('ern')
                if not ern:
                    self.logger.warning(f"Skipping student {student_data['seat_no']} - no ERN")
                    continue
                
                # Create or update student
                student = self.db_session.query(Student).filter_by(ern=ern).first()
                if not student:
                    student = Student(
                        ern=ern,
                        current_name=student_data['name'],
                        gender=student_data.get('gender'),
                        first_seen_exam_id=exam.id
                    )
                    self.db_session.add(student)
                else:
                    # Update name and gender if changed
                    student.current_name = student_data['name']
                    if student_data.get('gender'):
                        student.gender = student_data['gender']
                
                # Create/update student exam record
                record = self.db_session.query(StudentExamRecord).filter_by(
                    student_ern=ern,
                    exam_id=exam.id
                ).first()
                
                if not record:
                    record = StudentExamRecord(
                        student_ern=ern,
                        exam_id=exam.id,
                        seat_no=student_data['seat_no'],
                        name=student_data['name'],
                        college_code=student_data.get('college_code'),
                        college_name=student_data.get('college'),
                        student_status=student_data.get('status'),
                        total_marks=student_data.get('total_marks'),
                        result=student_data.get('result'),
                        sgpa=student_data.get('sgpa'),
                        total_credits=student_data.get('total_credits'),
                        page_number=student_data['page_number']
                    )
                    self.db_session.add(record)
                    students_processed += 1
                
                # Create grades for each subject using student's subject_codes
                student_subject_codes = student_data.get('subject_codes', [])
                num_subjects_in_data = len(student_data['external_marks'])
                num_subject_codes = len(student_subject_codes)
                num_subjects = min(num_subjects_in_data, num_subject_codes)
                
                # Log warning if mismatch
                if num_subjects_in_data != num_subject_codes:
                    self.logger.warning(
                        f"Student {ern} has {num_subjects_in_data} grades but "
                        f"{num_subject_codes} subject codes - processing first {num_subjects}"
                    )
                
                for i in range(num_subjects):
                    subject_code = student_subject_codes[i]
                    
                    # Verify subject exists in mapping (should always be true)
                    if subject_code not in extracted_data['subject_mapping']:
                        self.logger.warning(
                            f"Subject {subject_code} for student {ern} not found in index - "
                            f"using code as name"
                        )
                        extracted_data['subject_mapping'][subject_code] = f"Subject_{subject_code}"
                    
                    # Check if grade already exists
                    grade = self.db_session.query(Grade).filter_by(
                        student_ern=ern,
                        exam_id=exam.id,
                        subject_code=subject_code
                    ).first()
                    
                    if not grade:
                        grade = Grade(
                            student_ern=ern,
                            exam_id=exam.id,
                            subject_code=subject_code,
                            external_marks=student_data['external_marks'][i],
                            internal_marks=student_data['internal_marks'][i],
                            total_marks=student_data['total_marks_list'][i],
                            grade=student_data['grades'][i],
                            grade_point=student_data['grade_points'][i] if i < len(student_data['grade_points']) else None,
                            credits=student_data['credits'][i] if i < len(student_data['credits']) else 2.0,
                            grade_credits=student_data['grade_credits'][i] if i < len(student_data['grade_credits']) else None,
                            page_number=student_data['page_number']
                        )
                        self.db_session.add(grade)
                        grades_created += 1
            
            # Commit all changes
            self.db_session.commit()
            
            self.logger.info(f"Successfully saved to database:")
            self.logger.info(f"  - Students: {students_processed}")
            self.logger.info(f"  - Grades: {grades_created}")
            
            return True
            
        except Exception as e:
            self.db_session.rollback()
            self.logger.error(f"Database error: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def _create_dataframe(self, extracted_data: Dict[str, Any]) -> pd.DataFrame:
        """
        Convert extracted data to pandas DataFrame (for CSV/Excel export).
        
        Args:
            extracted_data: Dict from process_pdf() with students and metadata
            
        Returns:
            Pandas DataFrame with flattened student data
        """
        students = extracted_data['students']
        subject_order = extracted_data['subject_order']
        subject_mapping = extracted_data['subject_mapping']
        
        if not students:
            return pd.DataFrame()
        
        records = []
        
        for student in students:
            # Base record
            record = {
                'Seat_No': student['seat_no'],
                'Name': student['name'],
                'ERN': student['ern'],
                'Status': student['status'],
                'Gender': student['gender'],
                'College_Code': student.get('college_code'),
                'College': student.get('college'),
                'Total_Marks': student['total_marks'],
                'Result': student['result'],
                'SGPA': student['sgpa'],
                'Total_Credits': student['total_credits'],
                'Page_Number': student['page_number']
            }
            
            # Add subject-wise marks with actual subject names
            student_subject_codes = student.get('subject_codes', [])
            num_subjects = len(student['external_marks'])
            
            for i in range(num_subjects):
                # Use student's specific subject codes
                if i < len(student_subject_codes):
                    subject_code = student_subject_codes[i]
                    subject_name = subject_mapping.get(subject_code, f'Subject_{subject_code}')
                    
                    # Warn if subject not found in mapping
                    if subject_code not in subject_mapping:
                        self.logger.warning(f"Subject code {subject_code} not found in index mapping for student {student.get('seat_no')}")
                    
                    # Sanitize subject name for column headers
                    safe_name = re.sub(r'[^a-zA-Z0-9]+', '_', subject_name).strip('_')
                    
                    record[f'{safe_name}_Code'] = subject_code
                    record[f'{safe_name}_External'] = student['external_marks'][i]
                    record[f'{safe_name}_Internal'] = student['internal_marks'][i]
                    record[f'{safe_name}_Total'] = student['total_marks_list'][i]
                    record[f'{safe_name}_Grade'] = student['grades'][i]
                else:
                    # Fallback if subject codes missing
                    subject_num = i + 1
                    record[f'Subject_{subject_num}_External'] = student['external_marks'][i]
                    record[f'Subject_{subject_num}_Internal'] = student['internal_marks'][i]
                    record[f'Subject_{subject_num}_Total'] = student['total_marks_list'][i]
                    record[f'Subject_{subject_num}_Grade'] = student['grades'][i]
            
            records.append(record)
        
        return pd.DataFrame(records)
    
    def save_outputs(self, extracted_data: Dict[str, Any]) -> tuple:
        """
        Save extracted data to CSV and Excel files.
        
        Args:
            extracted_data: Dict from process_pdf()
            
        Returns:
            Tuple of (csv_file, excel_file) paths
        """
        df = self._create_dataframe(extracted_data)
        
        if df.empty:
            self.logger.error("Cannot save empty DataFrame")
            return None, None
        
        # Generate timestamped filenames
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_file = os.path.join(self.output_dir, f'student_grades_{timestamp}.csv')
        excel_file = os.path.join(self.output_dir, f'student_grades_{timestamp}.xlsx')
        
        # Save CSV
        df.to_csv(csv_file, index=False)
        self.logger.info(f"Saved CSV: {csv_file}")
        
        # Save Excel with formatting
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Student Grades')
            
            # Auto-adjust column widths
            worksheet = writer.sheets['Student Grades']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        self.logger.info(f"Saved Excel: {excel_file}")
        
        return csv_file, excel_file


def main():
    """
    Main execution function with command-line argument handling.
    """
    print("="*70)
    print("University of Mumbai Grade Sheet Extractor v1.0")
    print("="*70)
    print()

    if len(sys.argv) < 2:
        print("Usage: python extract_grades.py <pdf_file> [output_directory]")
        print()
        print("Example:")
        print("  python extract_grades.py results.pdf")
        print("  python extract_grades.py results.pdf ./output/")
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
            csv_file, excel_file = extractor.save_outputs(extracted_data)
            
            print()
            print("="*70)
            print("EXTRACTION COMPLETED SUCCESSFULLY")
            print("="*70)
            print(f"\nTotal students extracted: {len(extracted_data['students'])}")
            print(f"Total subjects found: {len(extracted_data['subject_order'])}")
            print()
            print("Output files:")
            print(f"  - {csv_file}")
            print(f"  - {excel_file}")
            print()
            print("Sample data (first 3 records):")
            for i, student in enumerate(extracted_data['students'][:3], 1):
                print(f"{i}. {student['seat_no']} - {student['name']} - {student['result']} (SGPA: {student['sgpa']})")
            print()
        else:
            print("\nError: No student records could be extracted.")
            print("Please check the extraction log for details.")
            
    except Exception as e:
        print(f"\nError during extraction: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

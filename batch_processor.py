"""
=============================================================================
Batch Processor for Mumbai University Grade Records
=============================================================================

Orchestrates the complete workflow:
1. Scans downloads/ for PDFs and metadata/
2. Extracts student info from each PDF
3. Crops individual student records using DYNAMIC line detection
4. Stores records in database with PDF file paths
5. Generates students.json for development

Author: GitHub Copilot
Date: 2026-02-12
Version: 2.0 - Dynamic cropping
=============================================================================
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models import Program, Examination, Student, StudentExamRecord
from pdf_processor import PdfProcessor
from extract_simple import SimpleStudentExtractor


class BatchGradeProcessor:
    """
    Batch processor for extracting and cropping student records from multiple PDFs.
    """
    
    def __init__(self, downloads_dir: str, metadata_dir: str, 
                 output_dir: str, db_session: Session):
        """
        Initialize batch processor.
        
        Args:
            downloads_dir: Directory containing PDF files
            metadata_dir: Directory containing metadata JSON files
            output_dir: Output directory for cropped student PDFs
            db_session: SQLAlchemy database session
        """
        self.downloads_dir = downloads_dir
        self.metadata_dir = metadata_dir
        self.output_dir = output_dir
        self.db_session = db_session
        
        # Create output directory structure
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, 'logs'), exist_ok=True)
        
        self._setup_logging()
        
        # Statistics tracking
        self.stats = {
            'pdfs_processed': 0,
            'pdfs_failed': 0,
            'students_extracted': 0,
            'students_cropped': 0,
            'students_failed': 0,
            'db_records_created': 0
        }
    
    def _setup_logging(self):
        """Configure logging"""
        log_file = os.path.join(self.output_dir, 'logs', 'batch_process.log')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger = logging.getLogger('BatchProcessor')
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def find_pdf_files(self) -> List[str]:
        """
        Find all PDF files in downloads directory.
        
        Returns:
            List of PDF file paths
        """
        pdf_files = []
        
        if not os.path.exists(self.downloads_dir):
            self.logger.error(f"Downloads directory not found: {self.downloads_dir}")
            return pdf_files
        
        for filename in os.listdir(self.downloads_dir):
            if filename.lower().endswith('.pdf'):
                pdf_path = os.path.join(self.downloads_dir, filename)
                pdf_files.append(pdf_path)
        
        self.logger.info(f"Found {len(pdf_files)} PDF files in {self.downloads_dir}")
        return pdf_files
    
    def load_metadata(self, pdf_path: str) -> Optional[Dict]:
        """
        Load metadata JSON for a PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Metadata dictionary or None if not found
        """
        pdf_basename = os.path.basename(pdf_path)
        json_basename = pdf_basename.replace('.pdf', '.json')
        json_path = os.path.join(self.metadata_dir, json_basename)
        
        if not os.path.exists(json_path):
            self.logger.warning(f"Metadata not found for {pdf_basename}")
            return None
        
        try:
            with open(json_path, 'r') as f:
                metadata = json.load(f)
            return metadata
        except Exception as e:
            self.logger.error(f"Error loading metadata {json_basename}: {e}")
            return None
    
    def get_or_create_program(self, program_code: str, program_name: str) -> Program:
        """
        Get existing program or create new one.
        
        Args:
            program_code: Program code (e.g., "1150561")
            program_name: Program name
            
        Returns:
            Program object
        """
        program = self.db_session.query(Program).filter_by(program_code=program_code).first()
        
        if not program:
            program = Program(program_code=program_code, program_name=program_name)
            self.db_session.add(program)
            self.db_session.commit()
            self.logger.info(f"Created new program: {program_code} - {program_name}")
        
        return program
    
    def get_or_create_examination(self, metadata: Dict, exam_data: Dict) -> Examination:
        """
        Get existing examination or create new one.
        
        Args:
            metadata: Metadata from JSON file
            exam_data: Exam data extracted from PDF
            
        Returns:
            Examination object
        """
        program_code = metadata.get('program_code')
        semester = metadata.get('semester')
        exam_type = metadata.get('exam_type')
        
        # Try to find existing examination
        exam = self.db_session.query(Examination).filter_by(
            program_code=program_code,
            semester=semester,
            exam_type=exam_type
        ).first()
        
        if not exam:
            # Create new examination
            exam = Examination(
                program_code=program_code,
                semester=semester,
                exam_type=exam_type,
                exam_title=exam_data.get('exam_title'),
                exam_month=exam_data.get('exam_month'),
                exam_year=exam_data.get('exam_year'),
                result_date=metadata.get('result_date'),
                declaration_date=exam_data.get('declaration_date'),
                pdf_filename=os.path.basename(metadata.get('pdf_file', '')),
                pdf_url=metadata.get('pdf_url')
            )
            self.db_session.add(exam)
            self.db_session.commit()
            self.logger.info(f"Created new examination: ID={exam.id}, {semester} {exam_type}")
        
        return exam
    
    def generate_student_filename(self, student: Dict, semester: str, 
                                  existing_files: set) -> str:
        """
        Generate unique filename for student PDF.
        
        Format: ERN_SEATNO_semester_status_collegecode.pdf
        
        Args:
            student: Student data dictionary
            semester: Semester identifier from metadata
            existing_files: Set of already used filenames
            
        Returns:
            Unique filename
        """
        ern = student.get('ern', 'UNKNOWN')
        seat_no = student.get('seat_no', 'UNKNOWN')
        status = student.get('status', 'UNKNOWN')
        college_code = student.get('college_code', 'UNKNOWN')
        
        # Clean filename components (remove special chars, keep alphanumeric and hyphens)
        ern_clean = ern.replace('MU', 'MU')  # Keep MU prefix
        seat_clean = ''.join(c for c in seat_no if c.isalnum())
        semester_clean = ''.join(c for c in semester if c.isalnum() or c == '-')
        status_clean = ''.join(c for c in status if c.isalnum())
        college_clean = college_code.replace('MU-', 'MU')  # Keep format
        
        base_filename = f"{ern_clean}_{seat_clean}_{semester_clean}_{status_clean}_{college_clean}.pdf"
        
        # If already exists, add counter
        if base_filename in existing_files:
            counter = 2
            while f"{ern_clean}_{seat_clean}_{semester_clean}_{status_clean}_{college_clean}_{counter}.pdf" in existing_files:
                counter += 1
            base_filename = f"{ern_clean}_{seat_clean}_{semester_clean}_{status_clean}_{college_clean}_{counter}.pdf"
        
        existing_files.add(base_filename)
        return base_filename
    
    def process_single_pdf(self, pdf_path: str) -> bool:
        """
        Process a single PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            True if successful, False otherwise
        """
        pdf_basename = os.path.basename(pdf_path)
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Processing: {pdf_basename}")
        self.logger.info(f"{'='*70}")
        
        try:
            metadata = self.load_metadata(pdf_path)
            if not metadata:
                self.logger.error(f"Skipping {pdf_basename} - no metadata")
                return False

            program = self.get_or_create_program(
                metadata['program_code'],
                metadata['program_name']
            )
            
            # Extract data from PDF
            extractor = SimpleStudentExtractor(pdf_path)
            extracted_data = extractor.process_pdf()
            
            if not extracted_data['students']:
                self.logger.warning(f"No students found in {pdf_basename}")
                return False
            
            # Create or get examination record
            exam = self.get_or_create_examination(metadata, extracted_data['exam_metadata'])
            
            # Track filenames for this PDF
            existing_files = set()
            
            # Process each student
            students_in_pdf = extracted_data['students']
            self.logger.info(f"Processing {len(students_in_pdf)} students...")
            
            for idx, student_data in enumerate(students_in_pdf, 1):
                try:
                    # Validate required fields
                    if not student_data.get('ern') or not student_data.get('seat_no'):
                        self.logger.warning(f"{student_data}")
                        self.logger.warning(f"  Student {idx}: Missing ERN or seat number - skipping")
                        self.stats['students_failed'] += 1
                        continue
                    if not student_data.get('college_code') or not student_data.get('college_name'):
                        self.logger.warning(f"{student_data}")
                        self.logger.warning(f"  Student {idx}: Missing college code or college name - skipping")
                        self.stats['students_failed'] += 1
                        continue
                    
                    
                    # Generate filename
                    student_filename = self.generate_student_filename(
                        student_data, metadata.get('semester', 'Unknown'), existing_files
                    )
                    student_pdf_path = os.path.join(self.output_dir, student_filename)
                    
                    # Crop student record using dynamic line detection
                    page_num = student_data['page_number']
                    
                    # Determine student position on this page (0-indexed)
                    student_index = sum(
                        1 for s in students_in_pdf[:idx-1] 
                        if s['page_number'] == page_num
                    )
                    
                    # Crop the PDF (uses dynamic detection, ignores total_students_on_page)
                    success = PdfProcessor.crop_single_student(
                        pdf_path, page_num, student_index, student_pdf_path
                    )
                    
                    if not success:
                        self.logger.warning(
                            f"  Student {idx}: Failed to crop PDF (page={page_num}, index={student_index})"
                        )
                        self.stats['students_failed'] += 1
                        continue
                    
                    self.stats['students_cropped'] += 1
                    
                    # Create or update Student record
                    student = self.db_session.query(Student).filter_by(
                        ern=student_data['ern']
                    ).first()
                    
                    if not student:
                        student = Student(
                            ern=student_data['ern'],
                            full_name=student_data.get('full_name', ''),
                            gender=student_data.get('gender')
                        )
                        self.db_session.add(student)
                    
                    # Create StudentExamRecord
                    exam_record = StudentExamRecord(
                        student_ern=student_data['ern'],
                        exam_id=exam.id,
                        seat_no=student_data['seat_no'],
                        college_code=student_data.get('college_code'),
                        college_name=student_data.get('college_name'),
                        status=student_data.get('status'),
                        result=student_data.get('result'),
                        page_number=student_data['page_number'],
                        pdf_file=student_pdf_path
                    )
                    
                    self.db_session.add(exam_record)
                    self.db_session.commit()
                    
                    self.stats['db_records_created'] += 1
                    
                    self.logger.debug(
                        f"  Student {idx}: {student_data['ern']} - "
                        f"{student_data['full_name']} - {student_data['result']} ✓"
                    )
                    
                except IntegrityError as e:
                    self.db_session.rollback()
                    self.logger.warning(
                        f"  Student {idx}: Duplicate record (ERN={student_data.get('ern')}) - skipping"
                    )
                    self.stats['students_failed'] += 1
                    
                except Exception as e:
                    self.db_session.rollback()
                    self.logger.error(f"  Student {idx}: Error - {e}")
                    self.stats['students_failed'] += 1
            
            self.stats['students_extracted'] += len(students_in_pdf)
            self.stats['pdfs_processed'] += 1
            
            self.logger.info(f"✓ Successfully processed {pdf_basename}")
            return True
            
        except Exception as e:
            self.logger.error(f"✗ Failed to process {pdf_basename}: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            self.stats['pdfs_failed'] += 1
            return False
    
    def process_all_pdfs(self) -> Dict[str, int]:
        """
        Process all PDFs in downloads directory.
        
        Returns:
            Statistics dictionary
        """
        self.logger.info("="*70)
        self.logger.info("BATCH PROCESSING STARTED")
        self.logger.info("="*70)
        self.logger.info(f"Downloads directory: {self.downloads_dir}")
        self.logger.info(f"Metadata directory: {self.metadata_dir}")
        self.logger.info(f"Output directory: {self.output_dir}")
        self.logger.info("="*70)
        
        # Find all PDF files
        pdf_files = self.find_pdf_files()
        
        if not pdf_files:
            self.logger.error("No PDF files found!")
            return self.stats
        
        # Process each PDF
        for idx, pdf_path in enumerate(pdf_files, 1):
            self.logger.info(f"\n[{idx}/{len(pdf_files)}] Processing PDF...")
            self.process_single_pdf(pdf_path)
        
        # Print final statistics
        self.logger.info("\n" + "="*70)
        self.logger.info("BATCH PROCESSING COMPLETED")
        self.logger.info("="*70)
        self.logger.info(f"PDFs processed successfully: {self.stats['pdfs_processed']}")
        self.logger.info(f"PDFs failed: {self.stats['pdfs_failed']}")
        self.logger.info(f"Students extracted: {self.stats['students_extracted']}")
        self.logger.info(f"Student PDFs created: {self.stats['students_cropped']}")
        self.logger.info(f"Database records created: {self.stats['db_records_created']}")
        self.logger.info(f"Students failed: {self.stats['students_failed']}")
        self.logger.info("="*70)
        
        return self.stats

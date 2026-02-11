"""
=============================================================================
Database Models for Mumbai University Grade Records
=============================================================================

Simplified SQLAlchemy models for storing student examination records.

Tables:
- Program: Academic programs (BSc, BCom, etc.)
- Examination: Exam sessions with metadata
- Student: Student basic information
- StudentExamRecord: Student performance in specific exam (with PDF path)

Author: GitHub Copilot
Date: 2026-02-09
Version: 1.0
=============================================================================
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, UniqueConstraint, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Program(Base):
    """Academic program information"""
    __tablename__ = 'programs'
    
    program_code = Column(String(10), primary_key=True)
    program_name = Column(String(200), nullable=False)
    
    # Relationships
    examinations = relationship('Examination', back_populates='program')
    
    def __repr__(self):
        return f"<Program(code={self.program_code}, name={self.program_name})>"


class Examination(Base):
    """Examination session information"""
    __tablename__ = 'examinations'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    program_code = Column(String(10), ForeignKey('programs.program_code'), nullable=False)
    semester = Column(String(50))  # "Semester - I", "Semester - II", etc.
    exam_type = Column(String(20))  # "REGULAR", "SUPPLEMENTARY"
    exam_title = Column(String(500))  # Full title from PDF
    exam_month = Column(String(20))  # "DECEMBER", "MAY", etc.
    exam_year = Column(Integer)  # 2025, 2026, etc.
    result_date = Column(String(20))  # ISO format date string
    declaration_date = Column(String(20))  # ISO format date string (if available)
    pdf_filename = Column(String(300))  # Original PDF filename
    pdf_url = Column(String(500))  # Original download URL
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    program = relationship('Program', back_populates='examinations')
    student_records = relationship('StudentExamRecord', back_populates='examination')
    
    def __repr__(self):
        return f"<Examination(id={self.id}, program={self.program_code}, semester={self.semester}, type={self.exam_type})>"


class Student(Base):
    """Student basic information"""
    __tablename__ = 'students'
    
    ern = Column(String(20), primary_key=True)  # MU enrollment number (e.g., MU1234567)
    name = Column(String(200), nullable=False)  # Full name
    first_name = Column(String(100))  # First name for filename generation
    gender = Column(String(10))  # M, F
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    exam_records = relationship('StudentExamRecord', back_populates='student')
    
    def __repr__(self):
        return f"<Student(ern={self.ern}, name={self.name})>"


class StudentExamRecord(Base):
    """Student performance record in a specific examination"""
    __tablename__ = 'student_exam_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_ern = Column(String(20), ForeignKey('students.ern'), nullable=False)
    exam_id = Column(Integer, ForeignKey('examinations.id'), nullable=False)
    seat_no = Column(String(20), nullable=False)  # 9-digit seat number
    college_code = Column(String(20))  # MU-XXXX
    college_name = Column(String(300))
    status = Column(String(50))  # "Regular", "ATKT", "Ex-Student", etc.
    result = Column(String(10))  # "PASS", "FAIL"
    page_number = Column(Integer)  # Page number in source PDF
    pdf_file = Column(String(500))  # Path to cropped student PDF
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    student = relationship('Student', back_populates='exam_records')
    examination = relationship('Examination', back_populates='student_records')
    
    # Unique constraint: one record per student per exam
    __table_args__ = (
        UniqueConstraint('student_ern', 'exam_id', name='unique_student_exam'),
    )
    
    def __repr__(self):
        return f"<StudentExamRecord(ern={self.student_ern}, exam_id={self.exam_id}, seat={self.seat_no}, result={self.result})>"

"""
=============================================================================
Export Utilities for Mumbai University Grade Records
=============================================================================

Utilities to export database records to JSON and other formats.

Author: GitHub Copilot
Date: 2026-02-09
Version: 1.0
=============================================================================
"""

import json
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from models import Student, StudentExamRecord, Examination


def export_students_json(db_session: Session, output_file: str = 'students.json') -> int:
    """
    Export all student exam records to JSON file.
    
    Creates a flat JSON array with student information for easy development access.
    
    Args:
        db_session: SQLAlchemy session
        output_file: Output JSON file path
        
    Returns:
        Number of records exported
    """
    # Query all student exam records with joins
    records = db_session.query(
        StudentExamRecord, Student, Examination
    ).join(
        Student, StudentExamRecord.student_ern == Student.ern
    ).join(
        Examination, StudentExamRecord.exam_id == Examination.id
    ).all()
    
    # Format as list of dictionaries
    export_data = []
    
    for record, student, exam in records:
        export_data.append({
            'ern': student.ern,
            'full_name': student.full_name,
            'gender': student.gender,
            'seat_no': record.seat_no,
            'college_code': record.college_code,
            'college_name': record.college_name,
            'status': record.status,
            'result': record.result,
            'exam_id': exam.id,
            'exam_title': exam.exam_title,
            'semester': exam.semester,
            'exam_type': exam.exam_type,
            'exam_month': exam.exam_month,
            'exam_year': exam.exam_year,
            'result_date': exam.result_date,
            'declaration_date': exam.declaration_date,
            'page_number': record.page_number,
            'pdf_file': record.pdf_file
        })
    
    # Sort by ERN and exam date
    export_data.sort(key=lambda x: (x['ern'], x.get('result_date', ''), x['exam_id']))
    
    # Write to JSON file
    with open(output_file, 'w') as f:
        json.dump(export_data, f, indent=2)
    
    print(f"Exported {len(export_data)} student records to {output_file}")
    return len(export_data)


def get_student_by_ern(db_session: Session, ern: str) -> List[Dict[str, Any]]:
    """
    Get all exam records for a specific student by ERN.
    
    Args:
        db_session: SQLAlchemy session
        ern: Student ERN (e.g., "MU1234567")
        
    Returns:
        List of exam record dictionaries
    """
    records = db_session.query(
        StudentExamRecord, Examination
    ).join(
        Examination, StudentExamRecord.exam_id == Examination.id
    ).filter(
        StudentExamRecord.student_ern == ern
    ).all()
    
    result = []
    for record, exam in records:
        result.append({
            'exam_id': exam.id,
            'exam_title': exam.exam_title,
            'semester': exam.semester,
            'exam_type': exam.exam_type,
            'result_date': exam.result_date,
            'seat_no': record.seat_no,
            'result': record.result,
            'college': record.college_name,
            'pdf_file': record.pdf_file
        })
    
    return result


def get_failed_students(db_session: Session) -> List[Dict[str, Any]]:
    """
    Get all students with FAIL result.
    
    Args:
        db_session: SQLAlchemy session
        
    Returns:
        List of failed student records
    """
    records = db_session.query(
        StudentExamRecord, Student, Examination
    ).join(
        Student, StudentExamRecord.student_ern == Student.ern
    ).join(
        Examination, StudentExamRecord.exam_id == Examination.id
    ).filter(
        StudentExamRecord.result == 'FAIL'
    ).all()
    
    result = []
    for record, student, exam in records:
        result.append({
            'ern': student.ern,
            'full_name': student.full_name,
            'seat_no': record.seat_no,
            'exam_title': exam.exam_title,
            'semester': exam.semester,
            'result_date': exam.result_date,
            'college': record.college_name,
            'pdf_file': record.pdf_file
        })
    
    return result


def get_exam_statistics(db_session: Session) -> List[Dict[str, Any]]:
    """
    Get statistics for all examinations.
    
    Args:
        db_session: SQLAlchemy session
        
    Returns:
        List of exam statistics
    """
    exams = db_session.query(Examination).all()
    
    stats = []
    for exam in exams:
        total = db_session.query(StudentExamRecord).filter_by(exam_id=exam.id).count()
        passed = db_session.query(StudentExamRecord).filter_by(
            exam_id=exam.id, result='PASS'
        ).count()
        failed = db_session.query(StudentExamRecord).filter_by(
            exam_id=exam.id, result='FAIL'
        ).count()
        
        stats.append({
            'exam_id': exam.id,
            'exam_title': exam.exam_title,
            'semester': exam.semester,
            'exam_type': exam.exam_type,
            'result_date': exam.result_date,
            'total_students': total,
            'passed': passed,
            'failed': failed,
            'pass_percentage': round((passed / total * 100) if total > 0 else 0, 2)
        })
    
    return stats


if __name__ == '__main__':
    """Export students.json when run as script"""
    from init_db import get_database_session
    
    print("="*70)
    print("Exporting Student Records to JSON")
    print("="*70)
    print()
    
    session = get_database_session('grade_records.db')
    count = export_students_json(session, 'students.json')
    
    print()
    print(f"✓ Exported {count} records to students.json")
    print()

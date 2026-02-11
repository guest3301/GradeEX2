"""
=============================================================================
Database Initialization for Mumbai University Grade Records
=============================================================================

Creates SQLite database and tables if they don't exist.

Usage:
    from init_db import init_database
    session = init_database('grade_records.db')

Author: GitHub Copilot
Date: 2026-02-09
Version: 1.0
=============================================================================
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models import Base, Program, Examination, Student, StudentExamRecord


def init_database(db_path: str = 'grade_records.db') -> Session:
    """
    Initialize database and create tables if they don't exist.
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        SQLAlchemy session object
    """
    # Create engine
    engine = create_engine(f'sqlite:///{db_path}', echo=False)
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    print(f"Database initialized: {os.path.abspath(db_path)}")
    print("Tables created:")
    print("  - programs")
    print("  - examinations")
    print("  - students")
    print("  - student_exam_records")
    
    # Create session factory
    Session = sessionmaker(bind=engine)
    session = Session()
    
    return session


def get_database_session(db_path: str = 'grade_records.db') -> Session:
    """
    Get database session (without recreating tables).
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        SQLAlchemy session object
    """
    engine = create_engine(f'sqlite:///{db_path}', echo=False)
    Session = sessionmaker(bind=engine)
    return Session()


if __name__ == '__main__':
    """Initialize database when run as script"""
    import sys
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'grade_records.db'
    
    print("="*70)
    print("Database Initialization")
    print("="*70)
    print()
    
    session = init_database(db_path)
    
    print()
    print("✓ Database ready for use")
    print()

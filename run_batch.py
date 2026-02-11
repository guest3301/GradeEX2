"""
=============================================================================
Batch Processing Entry Point for Mumbai University Grade Records
=============================================================================

Main script to orchestrate the complete workflow:
1. Initialize database
2. Process all PDFs in downloads/
3. Crop student records
4. Store in database
5. Export students.json

Usage:
    python run_batch.py [--downloads DIR] [--metadata DIR] [--output DIR] [--db FILE]

Examples:
    python run_batch.py
    python run_batch.py --downloads downloads/ --metadata metadata/ --output student_records/
    python run_batch.py --db my_grades.db

Author: GitHub Copilot
Date: 2026-02-09
Version: 1.0
=============================================================================
"""

import os
import sys
import argparse
from datetime import datetime

from init_db import init_database
from batch_processor import BatchGradeProcessor
from export_utils import export_students_json, get_exam_statistics


def main():
    """Main entry point for batch processing"""
    parser = argparse.ArgumentParser(
        description='Batch process Mumbai University grade PDFs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all PDFs with default settings
  python run_batch.py

  # Specify custom directories
  python run_batch.py --downloads pdfs/ --metadata meta/ --output records/

  # Use custom database file
  python run_batch.py --db custom_grades.db
        """
    )
    
    parser.add_argument(
        '--downloads',
        default='downloads',
        help='Directory containing PDF files (default: downloads)'
    )
    
    parser.add_argument(
        '--metadata',
        default='metadata',
        help='Directory containing metadata JSON files (default: metadata)'
    )
    
    parser.add_argument(
        '--output',
        default='student_records',
        help='Output directory for cropped student PDFs (default: student_records)'
    )
    
    parser.add_argument(
        '--db',
        default='grade_records.db',
        help='SQLite database file path (default: grade_records.db)'
    )
    
    parser.add_argument(
        '--skip-export',
        action='store_true',
        help='Skip JSON export step'
    )
    
    args = parser.parse_args()
    
    # Print header
    print()
    print("=" * 80)
    print(" " * 20 + "Mumbai University Grade Records")
    print(" " * 20 + "Batch Processing System v1.0")
    print("=" * 80)
    print()
    
    # Print configuration
    print("Configuration:")
    print(f"  Downloads directory: {args.downloads}")
    print(f"  Metadata directory:  {args.metadata}")
    print(f"  Output directory:    {args.output}")
    print(f"  Database file:       {args.db}")
    print()
    
    # Validate directories
    if not os.path.exists(args.downloads):
        print(f"Error: Downloads directory not found: {args.downloads}")
        sys.exit(1)
    
    if not os.path.exists(args.metadata):
        print(f"Error: Metadata directory not found: {args.metadata}")
        sys.exit(1)
    
    # Create output directory if needed
    if not os.path.exists(args.output):
        os.makedirs(args.output)
        print(f"Created output directory: {args.output}")
    
    try:
        # Step 1: Initialize database
        print()
        print("-" * 80)
        print("Step 1: Initializing Database")
        print("-" * 80)
        session = init_database(args.db)
        print()
        
        # Step 2: Process PDFs
        print()
        print("-" * 80)
        print("Step 2: Processing PDFs and Cropping Student Records")
        print("-" * 80)
        print()
        
        processor = BatchGradeProcessor(
            downloads_dir=args.downloads,
            metadata_dir=args.metadata,
            output_dir=args.output,
            db_session=session
        )
        
        stats = processor.process_all_pdfs()
        
        # Step 3: Export JSON
        if not args.skip_export:
            print()
            print("-" * 80)
            print("Step 3: Exporting students.json")
            print("-" * 80)
            print()
            
            json_file = 'students.json'
            count = export_students_json(session, json_file)
            print(f"✓ Exported {count} records to {json_file}")
        
        # Step 4: Display statistics
        print()
        print("-" * 80)
        print("Step 4: Examination Statistics")
        print("-" * 80)
        print()
        
        exam_stats = get_exam_statistics(session)
        
        if exam_stats:
            print(f"Total examinations: {len(exam_stats)}")
            print()
            print("Top 10 examinations by student count:")
            print()
            
            # Sort by total students
            exam_stats.sort(key=lambda x: x['total_students'], reverse=True)
            
            for i, stat in enumerate(exam_stats[:10], 1):
                print(f"{i}. {stat['exam_title']}")
                print(f"   Semester: {stat['semester']}, Type: {stat['exam_type']}")
                print(f"   Students: {stat['total_students']} (Pass: {stat['passed']}, "
                      f"Fail: {stat['failed']}, Pass%: {stat['pass_percentage']}%)")
                print()
        
        # Final summary
        print()
        print("=" * 80)
        print("BATCH PROCESSING COMPLETE")
        print("=" * 80)
        print()
        print(f"✓ PDFs processed:        {stats['pdfs_processed']}")
        print(f"✓ Students extracted:    {stats['students_extracted']}")
        print(f"✓ Student PDFs created:  {stats['students_cropped']}")
        print(f"✓ Database records:      {stats['db_records_created']}")
        print()
        
        if stats['pdfs_failed'] > 0 or stats['students_failed'] > 0:
            print("⚠ Warnings:")
            if stats['pdfs_failed'] > 0:
                print(f"  - {stats['pdfs_failed']} PDF(s) failed to process")
            if stats['students_failed'] > 0:
                print(f"  - {stats['students_failed']} student(s) failed to process")
            print()
            print(f"Check logs in: {os.path.join(args.output, 'logs', 'batch_process.log')}")
            print()
        
        print("=" * 80)
        print()
        print("Output files:")
        print(f"  - Database:      {os.path.abspath(args.db)}")
        print(f"  - Student PDFs:  {os.path.abspath(args.output)}/")
        if not args.skip_export:
            print(f"  - JSON export:   {os.path.abspath('students.json')}")
        print(f"  - Log file:      {os.path.join(args.output, 'logs', 'batch_process.log')}")
        print()
        
        # Close database session
        session.close()
        
        print("✓ All done!")
        print()
        
    except KeyboardInterrupt:
        print()
        print()
        print("=" * 80)
        print("INTERRUPTED BY USER")
        print("=" * 80)
        print()
        print("Batch processing was interrupted. Some records may have been processed.")
        print("It's safe to run the script again - duplicate records will be skipped.")
        print()
        sys.exit(0)
        
    except Exception as e:
        print()
        print()
        print("=" * 80)
        print("ERROR")
        print("=" * 80)
        print()
        print(f"An error occurred: {e}")
        print()
        
        import traceback
        print("Traceback:")
        traceback.print_exc()
        print()
        
        sys.exit(1)


if __name__ == '__main__':
    main()

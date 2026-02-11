# Mumbai University Grade Records - Batch Processing System

Automated system to extract, crop, and organize student grade records from Mumbai University PDF result sheets.

## Features

- **Batch PDF Processing**: Process 80+ PDFs automatically
- **Student Record Cropping**: Extract individual student records using fixed coordinates
- **Database Storage**: SQLite database with organized exam and student data
- **File Organization**: Each student gets a uniquely named PDF: `ERN_FirstName_ExamID.pdf`
- **JSON Export**: Quick-access JSON file with all student records
- **Progress Tracking**: Detailed logging and statistics

## System Architecture

```
downloads/              → Source PDFs
metadata/               → Metadata JSON files (from scraper)
student_records/        → Cropped student PDFs (output)
grade_records.db        → SQLite database
students.json           → JSON export for development
```

## Installation

1. **Clone/Navigate to the project directory**
   ```bash
   cd GradeEx2
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Quick Start - Process All PDFs

```bash
python run_batch.py
```

This will:
1. Initialize the database
2. Process all PDFs in `downloads/`
3. Crop individual student records to `student_records/`
4. Store metadata in `grade_records.db`
5. Export `students.json`

### Custom Directories

```bash
python run_batch.py --downloads pdfs/ --metadata meta/ --output records/
```

### Custom Database

```bash
python run_batch.py --db my_grades.db
```

### All Options

```bash
python run_batch.py --help
```

## Database Schema

### Tables

1. **programs**
   - `program_code` (PK): e.g., "1150561"
   - `program_name`: e.g., "Bachelor of Science(Maritime Hospitality Studies)"

2. **examinations**
   - `id` (PK): Auto-increment
   - `program_code` (FK)
   - `semester`: "Semester - I", etc.
   - `exam_type`: "REGULAR", "SUPPLEMENTARY"
   - `exam_title`: Full title from PDF
   - `exam_month`: "DECEMBER", "MAY", etc.
   - `exam_year`: 2025, 2026, etc.
   - `result_date`: ISO date from metadata
   - `declaration_date`: ISO date from PDF (if available)
   - `pdf_filename`, `pdf_url`

3. **students**
   - `ern` (PK): Mumbai University enrollment number (e.g., "MU1234567")
   - `name`: Full name
   - `first_name`: First name for filename generation
   - `gender`: M/F

4. **student_exam_records**
   - `id` (PK)
   - `student_ern` (FK)
   - `exam_id` (FK)
   - `seat_no`: 9-digit seat number
   - `college_code`: MU-XXXX
   - `college_name`
   - `status`: "Regular", "ATKT", "Ex-Student"
   - `result`: "PASS", "FAIL"
   - `page_number`: Source PDF page
   - `pdf_file`: **Path to cropped student PDF**

## Querying the Database

### Python Examples

```python
from init_db import get_database_session
from export_utils import get_student_by_ern, get_failed_students

# Get session
session = get_database_session()

# Find all records for a student
records = get_student_by_ern(session, 'MU1234567')

# Get all failed students
failed = get_failed_students(session)

# Query directly
from models import Student, StudentExamRecord
student = session.query(Student).filter_by(ern='MU1234567').first()
```

### SQL Examples

```bash
sqlite3 grade_records.db
```

```sql
-- Count students per exam
SELECT e.exam_title, COUNT(*) as student_count
FROM student_exam_records ser
JOIN examinations e ON ser.exam_id = e.id
GROUP BY e.id
ORDER BY student_count DESC;

-- Find student PDFs by ERN
SELECT ern, seat_no, result, pdf_file 
FROM student_exam_records 
WHERE ern = 'MU1234567';

-- All FAIL results with PDF paths
SELECT s.name, ser.seat_no, ser.result, ser.pdf_file, e.exam_title
FROM student_exam_records ser
JOIN students s ON ser.student_ern = s.ern
JOIN examinations e ON ser.exam_id = e.id
WHERE ser.result = 'FAIL';

-- Pass percentage by exam
SELECT 
    e.exam_title,
    COUNT(*) as total,
    SUM(CASE WHEN ser.result = 'PASS' THEN 1 ELSE 0 END) as passed,
    ROUND(SUM(CASE WHEN ser.result = 'PASS' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as pass_pct
FROM student_exam_records ser
JOIN examinations e ON ser.exam_id = e.id
GROUP BY e.id;
```

## File Structure

### Core System Files

- `run_batch.py` - Main entry point
- `batch_processor.py` - Orchestrator for PDF processing
- `extract_grades_simple.py` - Simplified PDF data extraction
- `pdf_processor.py` - PDF cropping with fixed coordinates
- `models.py` - Database schema
- `init_db.py` - Database initialization
- `export_utils.py` - Export and query utilities

### Legacy Files

- `extract_grades.py` - Original full extraction (includes grade parsing)
- `scaper.py` - Web scraper for downloading PDFs from Mumbai University

## Fixed Coordinates

Student records are cropped using pre-defined coordinates:

```
Position 1: (25, 59, 769, 206)    - First student on page
Position 2: (25, 206, 769, 349)   - Second student on page
Position 3: (25, 349, 769, 490)   - Third student (estimated)
```

These coordinates are based on standard Mumbai University PDF layout.

## Error Handling

- **Duplicate records**: Automatically skipped (based on ERN + exam_id)
- **Missing metadata**: PDFs without matching JSON are skipped
- **Individual failures**: Don't stop batch processing
- **Detailed logging**: Check `student_records/logs/batch_process.log`

## Output

### Directory Structure

```
student_records/
├── MU1234567_JOHN_1.pdf
├── MU1234567_JOHN_2.pdf
├── MU2345678_JANE_1.pdf
├── ...
└── logs/
    └── batch_process.log
```

### students.json Format

```json
[
  {
    "ern": "MU1234567",
    "first_name": "JOHN",
    "full_name": "JOHN SMITH",
    "gender": "M",
    "seat_no": "123456789",
    "college_code": "MU-1234",
    "college_name": "Example College",
    "status": "Regular",
    "result": "PASS",
    "exam_id": 1,
    "exam_title": "OFFICE REGISTER FOR THE Bachelor of Science...",
    "semester": "Semester - I",
    "exam_type": "REGULAR",
    "exam_month": "DECEMBER",
    "exam_year": 2025,
    "result_date": "2026-01-27",
    "declaration_date": "2026-01-27",
    "page_number": 2,
    "pdf_file": "student_records/MU1234567_JOHN_1.pdf"
  }
]
```

## Performance

- **Processing Speed**: ~2-5 seconds per PDF (depending on student count)
- **Expected Output**: ~80 PDFs → ~5000-10000 student records
- **Database Size**: ~5-10 MB (without embedded PDFs)
- **Student PDF Size**: ~10-50 KB each

## Troubleshooting

### No students found in PDF

- Check if PDF has "SEAT NO" text (not an index page)
- Verify PDF is not corrupted
- Check logs for parsing errors

### Cropping produces blank/partial PDFs

- Verify coordinate system matches your PDF layout
- Check if PDF has non-standard formatting
- Adjust coordinates in `pdf_processor.py` if needed

### Database errors

- Ensure `grade_records.db` is not locked by another process
- Delete and recreate database: `rm grade_records.db && python run_batch.py`

### Missing metadata

- Ensure metadata JSON files exist in `metadata/` directory
- Filenames must match: `exam.pdf` → `exam.json`
- Re-run scraper if needed: `python scaper.py`

## Development

### Testing Single PDF

```python
from extract_grades_simple import MumbaiUniversityGradeExtractor

extractor = MumbaiUniversityGradeExtractor('downloads/test.pdf', '.')
data = extractor.process_pdf()

print(f"Found {len(data['students'])} students")
```

### Testing Cropping

```python
from pdf_processor import PdfProcessor

# Crop first student from page 2
PdfProcessor.crop_single_student(
    'downloads/test.pdf',
    page_num=2,
    student_index=0,
    output_path='test_crop.pdf'
)
```

## License

Internal project for Mumbai University grade processing.

## Version History

- **v2.0** (2026-02-09): Simplified system with fixed coordinates and minimal database
- **v1.0** (2026-02-03): Original full extraction system with grade parsing

## Authors

- System Design: GitHub Copilot
- Date: February 9, 2026

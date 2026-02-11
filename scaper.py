"""
=============================================================================
Mumbai University Result PDF Scraper
=============================================================================

Scrapes PDF links from Mumbai University results website and downloads them.

Website: https://www.mumresults.in/ugnepresults.html

Features:
- Parses HTML table to extract program information
- Downloads PDFs with organized folder structure
- Skips already downloaded files
- Saves metadata JSON for each PDF
- Progress tracking

Usage:
    python scraper.py [--output-dir downloads] [--limit N]
    
Examples:
    python scraper.py
    python scraper.py --output-dir ./pdfs --limit 10
    
Output Structure:
    downloads/
        {pdf_filename}.pdf
        {pdf_filename}.json  # Metadata

Author: Claude
Date: 2026-02-05
Version: 1.0
=============================================================================
"""

import os
import sys
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Optional
import argparse
import logging
from urllib.parse import urljoin
import re


class MumbaiUniversityResultScraper:
    """Scraper for Mumbai University result PDFs"""
    
    BASE_URL = "https://www.mumresults.in"
    RESULTS_PAGE = "https://www.mumresults.in/ugnepresults.html"
    
    def __init__(self, output_dir: str = 'downloads'):
        """
        Initialize scraper.
        
        Args:
            output_dir: Base directory for downloads
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        self._setup_logging()
        
        # Setup requests session with headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
    
    def _setup_logging(self):
        """Configure logging"""
        log_file = os.path.join(self.output_dir, 'scraper_log.txt')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def parse_table_row(self, row) -> Optional[Dict[str, str]]:
        """
        Parse a table row to extract exam information.
        
        Args:
            row: BeautifulSoup row element
            
        Returns:
            Dictionary with exam info or None if invalid
        """
        cols = row.find_all('td')
        if len(cols) < 4:
            return None
        
        try:
            # Column 1: Program Code
            program_code = cols[1].text.strip()
            
            # Column 2: Name of Examination (with PDF link)
            link_tag = cols[2].find('a')
            if not link_tag:
                return None
            
            pdf_url = urljoin(self.BASE_URL, link_tag.get('href', ''))
            exam_name = link_tag.text.strip()
            
            # Column 3: Result Date
            result_date_str = cols[3].text.strip()
            
            # Parse exam name to extract details
            # Format: "Bachelor of XYZ ( Semester - N) ( NEP 2020 ) [SUPPLEMENTARY]"
            semester_match = re.search(r'Semester - ([IVX]+)', exam_name)
            semester = f"Semester - {semester_match.group(1)}" if semester_match else "Unknown"
            
            # Determine exam type
            exam_type = "SUPPLEMENTARY" if "SUPPLEMENTARY" in exam_name.upper() else "REGULAR"
            
            # Extract program name (before semester)
            program_name_match = re.match(r'(.+?)\s*\(\s*Semester', exam_name)
            program_name = program_name_match.group(1).strip() if program_name_match else exam_name
            
            # Parse result date
            try:
                result_date = datetime.strptime(result_date_str, '%d/%m/%Y').date()
            except ValueError:
                result_date = None
            
            return {
                'program_code': program_code,
                'program_name': program_name,
                'semester': semester,
                'exam_type': exam_type,
                'result_date': result_date.isoformat() if result_date else result_date_str,
                'pdf_url': pdf_url,
                'exam_full_name': exam_name
            }
        except Exception as e:
            self.logger.warning(f"Error parsing row: {e}")
            return None
    
    def scrape_exam_list(self) -> List[Dict[str, str]]:
        """
        Scrape the list of available exams from the results page.
        
        Returns:
            List of exam information dictionaries
        """
        self.logger.info(f"Fetching exam list from: {self.RESULTS_PAGE}")
        
        try:
            response = self.session.get(self.RESULTS_PAGE, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch results page: {e}")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all tables with class "counterone"
        tables = soup.find_all('table', class_='counterone')
        if not tables:
            self.logger.error("Could not find any results tables on page")
            return []
        
        self.logger.info(f"Found {len(tables)} table(s) on page")
        
        exams = []
        for table_num, table in enumerate(tables, 1):
            self.logger.info(f"Processing table {table_num}/{len(tables)}")
            rows = table.find('tbody').find_all('tr') if table.find('tbody') else table.find_all('tr')
            
            for row in rows[1:]:  # Skip header row
                exam_info = self.parse_table_row(row)
                if exam_info:
                    exams.append(exam_info)
        
        self.logger.info(f"Found {len(exams)} exam records across all tables")
        return exams
    
    def generate_pdf_path(self, exam_info: Dict[str, str]) -> tuple:
        """
        Generate file path for PDF and metadata.
        
        Args:
            exam_info: Exam information dictionary
            
        Returns:
            Tuple of (pdf_path, json_path, directory)
        """
        # Generate filename from URL
        pdf_filename = os.path.basename(exam_info['pdf_url'])
        
        # If filename doesn't end with .pdf, create one from metadata
        if not pdf_filename.endswith('.pdf'):
            program_code = exam_info['program_code']
            result_date = exam_info['result_date'].replace('-', '')  # YYYYMMDD
            pdf_filename = f"{program_code}_{result_date}.pdf"
        
        # All files go directly into output directory
        pdf_path = os.path.join(self.output_dir, pdf_filename)
        json_path = os.path.join(self.output_dir, pdf_filename.replace('.pdf', '.json'))
        
        return pdf_path, json_path, self.output_dir
    
    def download_pdf(self, exam_info: Dict[str, str], skip_existing: bool = True) -> bool:
        """
        Download a PDF file.
        
        Args:
            exam_info: Exam information dictionary
            skip_existing: Skip if PDF already exists
            
        Returns:
            True if downloaded or skipped, False if failed
        """
        pdf_path, json_path, _ = self.generate_pdf_path(exam_info)
        
        # Check if already exists
        if skip_existing and os.path.exists(pdf_path):
            self.logger.info(f"Skipping existing: {os.path.basename(pdf_path)}")
            return True
        
        # Download PDF
        try:
            self.logger.info(f"Downloading: {exam_info['pdf_url']}")
            response = self.session.get(exam_info['pdf_url'], timeout=60, stream=True)
            response.raise_for_status()
            
            # Save PDF
            with open(pdf_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = os.path.getsize(pdf_path) / (1024 * 1024)  # MB
            self.logger.info(f"Downloaded: {os.path.basename(pdf_path)} ({file_size:.2f} MB)")
            
            # Save metadata JSON
            metadata = {
                **exam_info,
                'downloaded_at': datetime.now().isoformat(),
                'pdf_file': pdf_path,
                'file_size_mb': round(file_size, 2)
            }
            
            with open(json_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return True
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to download {exam_info['pdf_url']}: {e}")
            return False
        except IOError as e:
            self.logger.error(f"Failed to save PDF: {e}")
            return False
    
    def scrape_and_download(self, limit: Optional[int] = None) -> Dict[str, int]:
        """
        Scrape exam list and download all PDFs.
        
        Args:
            limit: Optional limit on number of PDFs to download
            
        Returns:
            Dictionary with download statistics
        """
        exams = self.scrape_exam_list()
        
        if not exams:
            self.logger.warning("No exams found to download")
            return {'total': 0, 'downloaded': 0, 'skipped': 0, 'failed': 0}
        
        # Apply limit if specified
        if limit:
            exams = exams[:limit]
            self.logger.info(f"Limiting to first {limit} exams")
        
        stats = {'total': len(exams), 'downloaded': 0, 'skipped': 0, 'failed': 0}
        
        for i, exam in enumerate(exams, 1):
            self.logger.info(f"\n[{i}/{len(exams)}] Processing: {exam['program_code']} - {exam['semester']}")
            
            pdf_path, _, _ = self.generate_pdf_path(exam)
            
            if os.path.exists(pdf_path):
                self.logger.info("  Status: Already exists (skipping)")
                stats['skipped'] += 1
            else:
                if self.download_pdf(exam, skip_existing=True):
                    stats['downloaded'] += 1
                else:
                    stats['failed'] += 1
        
        return stats


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='Scrape and download Mumbai University result PDFs'
    )
    parser.add_argument(
        '--output-dir',
        default='downloads',
        help='Output directory for downloads (default: downloads)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of PDFs to download'
    )
    
    args = parser.parse_args()
    
    print("="*70)
    print("Mumbai University Result PDF Scraper v1.0")
    print("="*70)
    print()
    
    scraper = MumbaiUniversityResultScraper(output_dir=args.output_dir)
    
    try:
        stats = scraper.scrape_and_download(limit=args.limit)
        
        print()
        print("="*70)
        print("SCRAPING COMPLETED")
        print("="*70)
        print(f"\nTotal exams found: {stats['total']}")
        print(f"Downloaded: {stats['downloaded']}")
        print(f"Skipped (already exists): {stats['skipped']}")
        print(f"Failed: {stats['failed']}")
        print()
        print(f"Files saved to: {os.path.abspath(args.output_dir)}/")
        print()
        
    except KeyboardInterrupt:
        print("\n\nDownload interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

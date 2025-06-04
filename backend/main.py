from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import datetime
import hashlib
import sqlite3
import json
import threading
import time
from pathlib import Path
import logging
import pwd
import mimetypes
import chardet
import asyncio
import uuid
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.base import JobLookupError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('o2filesearch.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Scheduler
scheduler = BackgroundScheduler(timezone="UTC") # Using UTC for consistency

# Pydantic models
class SearchRequest(BaseModel):
    extensions: Optional[List[str]] = None
    min_size: int = 0
    max_size: Optional[int] = None
    min_date: Optional[str] = None
    max_date: Optional[str] = None
    partial_names: Optional[List[str]] = None
    match_logic: str = 'or'
    search_terms: Optional[List[str]] = None
    case_sensitive: bool = False
    owner_filter: Optional[str] = None
    duplicates_only: bool = False
    limit: int = 1000

class IndexRequest(BaseModel):
    root_path: str
    force_reindex: Optional[bool] = False

class DeleteRequest(BaseModel):
    file_path: str

# Pydantic models for Schedules
class ScheduleBase(BaseModel):
    root_path: str
    cron_expression: str
    force_reindex: Optional[bool] = False
    description: Optional[str] = None

class ScheduleCreate(ScheduleBase):
    pass

class ScheduleResponse(ScheduleBase):
    id: int
    job_id: str
    created_at: datetime.datetime

class ScheduleInDB(ScheduleResponse):
    pass

class FileIndexer:
    """Handles file system indexing and database operations"""
    
    def __init__(self, db_path: str = "file_index.db"):
        self.db_path = db_path
        self.init_database()

    def delete_path_entries(self, root_path_to_delete: str):
        """Deletes all entries from files_metadata where file_path starts with the given root_path."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Ensure trailing slash for directory matching if not present, though LIKE pattern should handle it
        # path_pattern = os.path.join(root_path_to_delete, "") + "%"
        path_pattern = f"{os.path.normpath(root_path_to_delete)}%"
        try:
            logger.info(f"Attempting to delete entries for path pattern: {path_pattern}")
            cursor.execute("DELETE FROM files_metadata WHERE file_path LIKE ?", (path_pattern,))
            deleted_count = cursor.rowcount
            conn.commit()
            logger.info(f"Deleted {deleted_count} entries for path pattern '{path_pattern}' due to force re-index.")
        except sqlite3.Error as e:
            logger.error(f"SQLite error deleting entries for path {root_path_to_delete}: {e}")
            # Optionally re-raise or handle if needed for API response
        finally:
            conn.close()
        
    def init_database(self):
        """Initialize SQLite database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Files metadata table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS files_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_extension TEXT,
                file_size INTEGER,
                creation_date TIMESTAMP,
                modified_date TIMESTAMP,
                owner TEXT,
                content_hash TEXT,
                text_content TEXT,
                is_text_file BOOLEAN DEFAULT 0,
                indexed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(file_path)
            )
        ''')
        
        # Search history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_query TEXT,
                search_params TEXT,
                result_count INTEGER,
                search_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Indexing status table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS indexing_status (
                id INTEGER PRIMARY KEY,
                last_index_date TIMESTAMP,
                total_files_indexed INTEGER DEFAULT 0,
                indexing_in_progress BOOLEAN DEFAULT 0,
                current_directory TEXT,
                progress_percentage REAL DEFAULT 0
            )
        ''')
        
        # Create FTS virtual table for text search
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
                file_path, file_name, text_content,
                content='files_metadata',
                content_rowid='id'
            )
        ''')
        
        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_extension ON files_metadata(file_extension)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_size ON files_metadata(file_size)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_modified_date ON files_metadata(modified_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_content_hash ON files_metadata(content_hash)')

        # Indexing schedules table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS indexing_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT UNIQUE NOT NULL, -- APScheduler job ID
                root_path TEXT NOT NULL,
                cron_expression TEXT NOT NULL,
                force_reindex BOOLEAN DEFAULT 0,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def get_file_hash(self, file_path: str) -> Optional[str]:
        """Calculate MD5 hash of file content"""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return None
    
    def is_binary_file(self, file_path: str) -> bool:
        """Check if file is binary (to avoid searching binary/compiled files)"""
        try:
            # Check common binary extensions first
            binary_extensions = {
                '.exe', '.dll', '.so', '.dylib', '.bin', '.obj', '.o', '.a', '.lib',
                '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar',
                '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.ico',
                '.mp3', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv',
                '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
                '.sqlite', '.db', '.mdb', '.accdb',
                '.class', '.jar', '.war', '.ear',
                '.pyc', '.pyo', '.pyd'
            }
            
            file_ext = Path(file_path).suffix.lower()
            if file_ext in binary_extensions:
                return True
            
            # Check file content for null bytes (binary indicator)
            try:
                with open(file_path, 'rb') as f:
                    chunk = f.read(1024)  # Read first 1KB
                    if b'\x00' in chunk:
                        return True
            except Exception:
                return True  # If we can't read it, assume it's binary
                
            return False
            
        except Exception as e:
            logger.error(f"Error checking if {file_path} is binary: {e}")
            return True  # Assume binary if we can't determine
    
    def is_text_file(self, file_path: str) -> bool:
        """Determine if a file is text-based and safe to read"""
        try:
            # First check if it's binary
            if self.is_binary_file(file_path):
                return False
            
            # Check MIME type
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type and mime_type.startswith('text/'):
                return True
            
            # Check common text extensions
            text_extensions = {
                '.txt', '.md', '.rst', '.py', '.js', '.ts', '.jsx', '.tsx',
                '.html', '.htm', '.css', '.scss', '.sass', '.less',
                '.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
                '.csv', '.tsv', '.log', '.sh', '.bash', '.zsh', '.fish',
                '.sql', '.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx',
                '.java', '.kt', '.scala', '.go', '.rs', '.swift', '.php',
                '.rb', '.pl', '.r', '.m', '.mm', '.swift', '.dart',
                '.vue', '.svelte', '.astro', '.ejs', '.hbs', '.mustache',
                '.dockerfile', '.gitignore', '.gitattributes', '.editorconfig',
                '.env', '.example', '.sample', '.template'
            }
            
            file_ext = Path(file_path).suffix.lower()
            if file_ext in text_extensions:
                return True
            
            # For files without extension or unknown types, try encoding detection
            try:
                with open(file_path, 'rb') as f:
                    raw_data = f.read(2048)  # Read first 2KB
                    if not raw_data:
                        return False
                    
                    # Try to detect encoding
                    result = chardet.detect(raw_data)
                    if result['encoding'] and result['confidence'] > 0.8:
                        # Try to decode a sample to verify
                        try:
                            raw_data.decode(result['encoding'])
                            return True
                        except UnicodeDecodeError:
                            return False
                            
            except Exception:
                pass
                
            return False
            
        except Exception as e:
            logger.error(f"Error checking if {file_path} is text file: {e}")
            return False
    
    def extract_text_content(self, file_path: str) -> Optional[str]:
        """Extract text content from file"""
        try:
            if not self.is_text_file(file_path):
                return None
                
            # Try different encodings
            encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252', 'iso-8859-1']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                        content = f.read(50000)  # Limit to first 50KB for indexing
                        return content
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    logger.error(f"Error reading {file_path} with {encoding}: {e}")
                    continue
                    
            return None
            
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            return None
    
    def should_skip_directory(self, dir_path: str) -> bool:
        """Check if directory should be skipped during indexing"""
        skip_dirs = {
            '__pycache__', '.git', '.svn', '.hg', 'node_modules',
            'venv', 'env', '.venv', '.env', 'anaconda3', 'miniconda3',
            '.conda', 'conda-meta', 'site-packages', 'dist-packages',
            '.cache', '.tmp', 'tmp', 'temp', '.temp',
            'build', 'dist', 'target', 'out', '.build', '.next',
            '.vscode', '.idea', '.settings', '.eclipse',
            'Music', 'Pictures', 'Videos', 'Movies', 'Downloads',
            'Trash', '.Trash', '.local/share/Trash',
            'Library', 'System', 'Applications', 'usr', 'var', 'proc', 'sys'
        }
        
        dir_name = os.path.basename(dir_path).lower()
        return dir_name in skip_dirs or dir_name.startswith('.')
    
    def index_file(self, file_path: str) -> bool:
        """Index a single file"""
        try:
            if os.path.islink(file_path):
                return False
                
            stat_info = os.stat(file_path)
            file_name = os.path.basename(file_path)
            file_extension = Path(file_path).suffix.lower()
            
            # Get file owner
            try:
                owner = pwd.getpwuid(stat_info.st_uid).pw_name
            except (KeyError, AttributeError):
                owner = "unknown"
            
            # Calculate content hash
            content_hash = self.get_file_hash(file_path)
            
            # Extract text content if it's a text file
            text_content = self.extract_text_content(file_path)
            is_text = text_content is not None
            
            # Store in database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO files_metadata 
                (file_path, file_name, file_extension, file_size, creation_date, 
                 modified_date, owner, content_hash, text_content, is_text_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                file_path, file_name, file_extension, stat_info.st_size,
                datetime.datetime.fromtimestamp(stat_info.st_ctime),
                datetime.datetime.fromtimestamp(stat_info.st_mtime),
                owner, content_hash, text_content, is_text
            ))
            
            # Update FTS table if it's a text file
            if is_text and text_content:
                cursor.execute('''
                    INSERT OR REPLACE INTO files_fts (rowid, file_path, file_name, text_content)
                    SELECT id, file_path, file_name, text_content 
                    FROM files_metadata WHERE file_path = ?
                ''', (file_path,))
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Error indexing file {file_path}: {e}")
            return False
    
    def update_indexing_progress(self, current: int, total: int, current_file: str = ""):
        """Update indexing progress in database"""
        try:
            progress = (current / total * 100) if total > 0 else 0
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE indexing_status
                SET progress_percentage = ?, current_directory = ?
                WHERE id = 1
            ''', (progress, current_file))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error updating progress: {e}")
    
    def index_directory(self, root_path: str):
        """Index all files in a directory recursively"""
        try:
            # Mark indexing as in progress
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO indexing_status 
                (id, indexing_in_progress, current_directory, progress_percentage) 
                VALUES (1, 1, ?, 0)
            ''', (root_path,))
            conn.commit()
            conn.close()
            
            total_files = 0
            indexed_files = 0
            
            # Count total files first
            logger.info("Counting files...")
            for root, dirs, files in os.walk(root_path):
                # Filter out directories to skip
                dirs[:] = [d for d in dirs if not self.should_skip_directory(os.path.join(root, d))]
                total_files += len(files)
            
            logger.info(f"Found {total_files} files to index")
            
            # Index files
            for root, dirs, files in os.walk(root_path):
                # Filter out directories to skip
                dirs[:] = [d for d in dirs if not self.should_skip_directory(os.path.join(root, d))]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    if self.index_file(file_path):
                        indexed_files += 1
                    
                    # Update progress every 100 files
                    if indexed_files % 100 == 0:
                        self.update_indexing_progress(indexed_files, total_files, file_path)
            
            # Update final indexing status
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO indexing_status 
                (id, last_index_date, total_files_indexed, indexing_in_progress, 
                 current_directory, progress_percentage) 
                VALUES (1, ?, ?, 0, ?, 100)
            ''', (datetime.datetime.now(), indexed_files, root_path))
            conn.commit()
            conn.close()
            
            logger.info(f"Indexing completed: {indexed_files}/{total_files} files indexed")
            
        except Exception as e:
            logger.error(f"Error during directory indexing: {e}")
            # Mark indexing as not in progress
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('UPDATE indexing_status SET indexing_in_progress = 0 WHERE id = 1')
            conn.commit()
            conn.close()
    
    def delete_file(self, file_path: str) -> bool:
        """Delete a file from the system and database"""
        try:
            # Delete from filesystem
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Delete from database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM files_metadata WHERE file_path = ?", (file_path,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            return False

class SearchEngine:
    """Handles search operations on the indexed data"""
    
    def __init__(self, db_path: str = "file_index.db"):
        self.db_path = db_path
    
    def search_files(self, request: SearchRequest) -> List[Dict]:
        """Search files based on various criteria"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Build the query
        # Start with an alias so later conditions referencing "fm" work
        query_parts = ["SELECT fm.* FROM files_metadata fm WHERE 1=1"]
        params = []
        
        # Extension filter
        if request.extensions and any(ext.strip() for ext in request.extensions):
            ext_conditions = []
            for ext in request.extensions:
                if ext.strip():
                    ext_clean = ext.strip().lower()
                    if not ext_clean.startswith('.'):
                        ext_clean = '.' + ext_clean
                    ext_conditions.append("fm.file_extension = ?")
                    params.append(ext_clean)
            if ext_conditions:
                query_parts.append(f"AND ({' OR '.join(ext_conditions)})")
        
        # Size filter
        if request.min_size > 0:
            query_parts.append("AND fm.file_size >= ?")
            params.append(request.min_size)
        if request.max_size:
            query_parts.append("AND fm.file_size <= ?")
            params.append(request.max_size)
        
        # Date filter
        if request.min_date:
            query_parts.append("AND date(fm.modified_date) >= ?")
            params.append(request.min_date)
        if request.max_date:
            query_parts.append("AND date(fm.modified_date) <= ?")
            params.append(request.max_date)
        
        # Partial name filter
        if request.partial_names and any(name.strip() for name in request.partial_names):
            name_conditions = []
            for name in request.partial_names:
                if name.strip():
                    if request.case_sensitive:
                        name_conditions.append("fm.file_name LIKE ?")
                        params.append(f"%{name.strip()}%")
                    else:
                        name_conditions.append("LOWER(fm.file_name) LIKE LOWER(?)")
                        params.append(f"%{name.strip()}%")
            
            if name_conditions:
                if request.match_logic == 'and':
                    query_parts.append(f"AND ({' AND '.join(name_conditions)})")
                else:
                    query_parts.append(f"AND ({' OR '.join(name_conditions)})")
        
        # Owner filter
        if request.owner_filter:
            query_parts.append("AND fm.owner = ?")
            params.append(request.owner_filter)
        
        # Duplicates filter
        if request.duplicates_only:
            query_parts.append("""
                AND fm.content_hash IN (
                    SELECT content_hash FROM files_metadata 
                    WHERE content_hash IS NOT NULL 
                    GROUP BY content_hash HAVING COUNT(*) > 1
                )
            """)
        
        # Content search using FTS
        if request.search_terms and any(term.strip() for term in request.search_terms):
            # Use FTS for text content search
            fts_query = ' OR '.join([f'"{term.strip()}"' for term in request.search_terms if term.strip()])
            query_parts[0] = """
                SELECT fm.* FROM files_metadata fm
                JOIN files_fts fts ON fm.id = fts.rowid
                WHERE files_fts MATCH ?
            """
            params.insert(0, fts_query)
            
            # Add other conditions
            for i, part in enumerate(query_parts[1:], 1):
                if part.startswith("AND"):
                    query_parts[i] = part  # Keep as is
        
        # Add limit
        query_parts.append("ORDER BY modified_date DESC LIMIT ?")
        params.append(request.limit)
        
        # Execute query
        query = " ".join(query_parts)
        cursor.execute(query, params)
        
        columns = [description[0] for description in cursor.description]
        results = []
        
        for row in cursor.fetchall():
            result = dict(zip(columns, row))
            results.append(result)
        
        conn.close()
        
        # Log search
        self.log_search(query, params, len(results))
        
        return results
    
    def log_search(self, query: str, params: List, result_count: int):
        """Log search query for history tracking"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            search_params = json.dumps({
                'query': query,
                'params': params
            })
            
            cursor.execute('''
                INSERT INTO search_history (search_query, search_params, result_count)
                VALUES (?, ?, ?)
            ''', (query[:200], search_params, result_count))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error logging search: {e}")
    
    def get_duplicate_files(self) -> List[Dict]:
        """Get all duplicate files grouped by content hash"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT content_hash, COUNT(*) as count, 
                   GROUP_CONCAT(file_path, '|') as file_paths,
                   SUM(file_size) as total_size
            FROM files_metadata 
            WHERE content_hash IS NOT NULL 
            GROUP BY content_hash 
            HAVING COUNT(*) > 1
            ORDER BY total_size DESC
        ''')
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'content_hash': row[0],
                'duplicate_count': row[1],
                'file_paths': row[2].split('|'),
                'total_size': row[3]
            })
        
        conn.close()
        return results
    
    def get_indexing_status(self) -> Dict:
        """Get current indexing status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM indexing_status WHERE id = 1')
        row = cursor.fetchone()
        
        if row:
            status = {
                'last_index_date': row[1],
                'total_files_indexed': row[2] if row[2] is not None else 0,
                'indexing_in_progress': bool(row[3]),
                'current_directory': row[4],
                'progress_percentage': row[5] if len(row) > 5 else 0
            }
        else:
            status = {
                'last_index_date': None,
                'total_files_indexed': 0,
                'indexing_in_progress': False,
                'current_directory': None,
                'progress_percentage': 0
            }
        
        conn.close()
        return status
    
    def get_statistics(self) -> Dict:
        """Get database statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM files_metadata")
        total_files = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM files_metadata WHERE is_text_file = 1")
        text_files = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(file_size) FROM files_metadata")
        total_size = cursor.fetchone()[0] or 0
        
        cursor.execute("""
            SELECT file_extension, COUNT(*) as count 
            FROM files_metadata 
            WHERE file_extension IS NOT NULL AND file_extension != ''
            GROUP BY file_extension 
            ORDER BY count DESC 
            LIMIT 10
        """)
        top_extensions = [{'extension': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            'total_files': total_files,
            'text_files': text_files,
            'total_size': total_size,
            'top_extensions': top_extensions
        }

# Initialize global objects
indexer = FileIndexer()
search_engine = SearchEngine()

# Pydantic models for Schedules (ensure datetime is imported if not already)
class ScheduleBase(BaseModel):
    root_path: str
    cron_expression: str
    force_reindex: Optional[bool] = False
    description: Optional[str] = None

class ScheduleCreate(ScheduleBase):
    pass

class ScheduleResponse(ScheduleBase):
    id: int
    job_id: str # APScheduler's job ID
    created_at: datetime.datetime

class ScheduleInDB(ScheduleResponse):
    pass

# --- Global Variables and Setup ---
# db_path is already defined where indexer is initialized, ensure it's accessible or re-define here if needed.
# For clarity, we can assume db_path is available via the indexer instance or defined globally before this block.

# Initialize Scheduler
scheduler = BackgroundScheduler(timezone="UTC")

# --- Scheduled Job Function ---
async def scheduled_index_job(root_path: str, force_reindex: bool = False):
    logger.info(f"Scheduler: Starting job for path: {root_path}, force_reindex: {force_reindex}")
    try:
        # Access global indexer and search_engine instances
        # These are assumed to be initialized before the scheduler starts any jobs.
        current_status = search_engine.get_indexing_status()
        if current_status.get('indexing_in_progress', False):
            logger.warning(f"Scheduler: Indexing for {root_path} skipped: another indexing process is already running.")
            return

        if force_reindex:
            logger.info(f"Scheduler: Force re-index for path: {root_path}. Deleting existing entries.")
            await asyncio.to_thread(indexer.delete_path_entries, root_path)
        
        logger.info(f"Scheduler: Starting indexing task for {root_path}")
        await asyncio.to_thread(indexer.index_directory, root_path)
        logger.info(f"Scheduler: Indexing finished for {root_path}")

    except Exception as e:
        logger.error(f"Scheduler: Error during scheduled indexing for {root_path}: {e}", exc_info=True)

# --- Lifespan Management ---
async def load_and_schedule_jobs_from_db(db_path_param: str):
    logger.info("Lifespan: Loading and scheduling jobs from DB...")
    conn = sqlite3.connect(db_path_param)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, job_id, root_path, cron_expression, force_reindex, description FROM indexing_schedules")
        schedules_data = cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Lifespan: Error reading schedules from DB: {e}")
        schedules_data = []
    finally:
        conn.close()

    for s_id, job_id, root_path, cron_expr, force_idx, desc in schedules_data:
        logger.info(f"Lifespan: Attempting to schedule job_id='{job_id}' for path='{root_path}', cron='{cron_expr}'")
        try:
            scheduler.add_job(
                func=scheduled_index_job,
                trigger=CronTrigger.from_crontab(cron_expr),
                args=[root_path, bool(force_idx)],
                id=job_id,
                name=desc or f"Scheduled index: {root_path} ({cron_expr})",
                replace_existing=True # Important for re-scheduling if app restarts
            )
            logger.info(f"Lifespan: Successfully scheduled job_id='{job_id}' for path='{root_path}'")
        except Exception as e:
            logger.error(f"Lifespan: Failed to schedule job_id='{job_id}' for '{root_path}': {e}", exc_info=True)

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    logger.info("Lifespan: Application startup...")
    # indexer and search_engine are global and initialized before app starts.
    # db_path is also global (or accessible via indexer.db_path)
    await load_and_schedule_jobs_from_db(indexer.db_path) # Pass db_path explicitly
    if not scheduler.running:
        scheduler.start()
        logger.info("Lifespan: Scheduler started.")
    else:
        logger.info("Lifespan: Scheduler already running.")
    yield
    logger.info("Lifespan: Application shutdown...")
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Lifespan: Scheduler shut down.")
    else:
        logger.info("Lifespan: Scheduler was not running.")

# FastAPI app
from fastapi import FastAPI # Corrected: removed lifespan from here
from fastapi.middleware.cors import CORSMiddleware

# Define the lifespan manager
@asynccontextmanager
async def app_lifespan_manager(app_instance: FastAPI):
    logger.info("Lifespan: Application startup...")
    # Initialize and start the scheduler
    # Ensure init_database() and load_schedules_from_db() are called if they are part of startup.
    # init_database() # Example: uncomment if needed
    # load_schedules_from_db() # Example: uncomment if needed

    try:
        if not scheduler.running: # Assuming 'scheduler' is globally accessible
             scheduler.start()
             logger.info("Lifespan: Scheduler started.")
        else:
            logger.info("Lifespan: Scheduler was already running.")
    except Exception as e:
        logger.error(f"Lifespan: Error starting scheduler: {e}", exc_info=True)
    
    yield # Application runs here
    
    logger.info("Lifespan: Application shutdown...")
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Lifespan: Scheduler shut down.")
    else:
        logger.info("Lifespan: Scheduler was not running.")

app = FastAPI(lifespan=app_lifespan_manager, title="O2FileSearchPlus API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "O2FileSearchPlus API"}

@app.post("/api/search")
async def search_files(request: SearchRequest):
    """Search files based on criteria"""
    try:
        results = search_engine.search_files(request)
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/index")
async def start_indexing(request: IndexRequest, background_tasks: BackgroundTasks):
    """Start indexing a directory"""
    try:
        if not os.path.exists(request.root_path):
            raise HTTPException(status_code=400, detail="Directory does not exist")
        
        status = search_engine.get_indexing_status()
        if status['indexing_in_progress']:
            raise HTTPException(status_code=400, detail="Indexing already in progress")
        
        if request.force_reindex:
            logger.info(f"Force re-index requested for path: {request.root_path}. Deleting existing entries.")
            indexer.delete_path_entries(request.root_path)
        
        # Start indexing in background
        background_tasks.add_task(indexer.index_directory, request.root_path)
        
        return {"message": "Indexing started", "root_path": request.root_path}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Indexing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status")
async def get_indexing_status():
    """Get current indexing status"""
    try:
        status = search_engine.get_indexing_status()
        return status
    except Exception as e:
        logger.error(f"Status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/duplicates")
async def get_duplicates():
    """Get duplicate files"""
    try:
        duplicates = search_engine.get_duplicate_files()
        return {"duplicates": duplicates, "count": len(duplicates)}
    except Exception as e:
        logger.error(f"Duplicates error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/statistics")
async def get_statistics():
    """Get database statistics"""
    try:
        stats = search_engine.get_statistics()
        return stats
    except Exception as e:
        logger.error(f"Statistics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/delete")
async def delete_file(request: DeleteRequest):
    """Delete a file from the system and database"""
    try:
        # Check if file exists in database
        conn = sqlite3.connect(indexer.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT file_path FROM files_metadata WHERE file_path = ?", (request.file_path,))
        exists = cursor.fetchone()
        conn.close()
        
        if not exists:
            raise HTTPException(status_code=404, detail="File not found in database")
            
        # Delete from filesystem
        if os.path.exists(request.file_path):
            os.remove(request.file_path)
            
        # Delete from database
        conn = sqlite3.connect(indexer.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM files_metadata WHERE file_path = ?", (request.file_path,))
        conn.commit()
        conn.close()
        
        return {"message": "File deleted successfully"}
    except Exception as e:
        logger.error(f"Deletion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/file-content")
async def get_file_content(file_path: str = Query(..., description="The absolute path to the file")):
    """
    Retrieves the indexed text content of a file.
    """
    if not file_path:
        raise HTTPException(status_code=400, detail="File path is required")

    try:
        conn = sqlite3.connect(search_engine.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT is_text_file, text_content FROM files_metadata WHERE file_path = ?", 
            (file_path,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            is_text_file, text_content = row
            if is_text_file:
                # Content is already limited to 50KB during indexing by extract_text_content
                return {"file_path": file_path, "content": text_content, "is_text_file": True}
            else:
                return {"file_path": file_path, "content": None, "is_text_file": False, "message": "File is not a text file or content not indexed."}
        else:
            raise HTTPException(status_code=404, detail="File not found in index")
            
    except HTTPException:
        raise 
    except Exception as e:
        logger.error(f"Error getting file content for {file_path}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving file content: {e}")

# API Endpoints for Schedules
@app.post("/api/schedules", response_model=ScheduleResponse, status_code=201)
async def create_schedule(schedule_data: ScheduleCreate):
    """
    Create a new indexing schedule.
    """
    job_id = uuid.uuid4().hex
    try:
        # Validate cron expression (APScheduler does this on add_job)
        trigger = CronTrigger.from_crontab(schedule_data.cron_expression)
    except ValueError as e:
        logger.error(f"Invalid cron expression: {schedule_data.cron_expression} - {e}")
        raise HTTPException(status_code=400, detail=f"Invalid cron expression: {e}")

    conn = sqlite3.connect(indexer.db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO indexing_schedules (job_id, root_path, cron_expression, force_reindex, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                job_id,
                schedule_data.root_path,
                schedule_data.cron_expression,
                schedule_data.force_reindex,
                schedule_data.description,
            ),
        )
        new_schedule_id = cursor.lastrowid
        conn.commit()

        scheduler.add_job(
            func=scheduled_index_job,
            trigger=trigger,
            args=[schedule_data.root_path, schedule_data.force_reindex],
            id=job_id,
            name=schedule_data.description or f"Scheduled index: {schedule_data.root_path}",
            replace_existing=True, # Should not happen for new jobs, but good practice
        )
        logger.info(f"Created and scheduled job_id='{job_id}' for path='{schedule_data.root_path}'")
        
        # Fetch the created schedule to return it
        cursor.execute("SELECT id, job_id, root_path, cron_expression, force_reindex, description, created_at FROM indexing_schedules WHERE id = ?", (new_schedule_id,))
        created_schedule_row = cursor.fetchone()
        
        if not created_schedule_row:
            # This case should ideally not happen if DB insert was successful
            logger.error(f"Failed to retrieve schedule (id: {new_schedule_id}) immediately after creation.")
            raise HTTPException(status_code=500, detail="Failed to retrieve schedule after creation.")

        return ScheduleResponse(
            id=created_schedule_row[0],
            job_id=created_schedule_row[1],
            root_path=created_schedule_row[2],
            cron_expression=created_schedule_row[3],
            force_reindex=bool(created_schedule_row[4]),
            description=created_schedule_row[5],
            created_at=datetime.datetime.fromisoformat(created_schedule_row[6]) # Ensure datetime conversion
        )

    except sqlite3.IntegrityError as e: # Handles unique constraint for job_id if somehow duplicated
        conn.rollback()
        logger.error(f"Error creating schedule (IntegrityError): {e}")
        raise HTTPException(status_code=409, detail=f"Schedule with this job_id may already exist or other integrity issue: {e}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating schedule: {e}", exc_info=True)
        # Attempt to remove from scheduler if DB insert failed after add_job (unlikely order, but safeguard)
        try:
            scheduler.remove_job(job_id)
        except JobLookupError:
            pass # Job wasn't added or already removed
        raise HTTPException(status_code=500, detail=f"Failed to create schedule: {e}")
    finally:
        conn.close()

@app.get("/api/schedules", response_model=List[ScheduleResponse])
async def list_schedules():
    """
    List all indexing schedules.
    """
    conn = sqlite3.connect(indexer.db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, job_id, root_path, cron_expression, force_reindex, description, created_at FROM indexing_schedules ORDER BY created_at DESC")
        schedules_data = cursor.fetchall()
        
        response = [
            ScheduleResponse(
                id=row[0],
                job_id=row[1],
                root_path=row[2],
                cron_expression=row[3],
                force_reindex=bool(row[4]),
                description=row[5],
                created_at=datetime.datetime.fromisoformat(row[6])
            ) for row in schedules_data
        ]
        return response
    except Exception as e:
        logger.error(f"Error listing schedules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list schedules: {e}")
    finally:
        conn.close()

@app.delete("/api/schedules/{job_id}", status_code=200)
async def delete_schedule(job_id: str):
    """
    Delete an indexing schedule by its job_id.
    """
    conn = sqlite3.connect(indexer.db_path)
    cursor = conn.cursor()
    try:
        # Check if schedule exists
        cursor.execute("SELECT id FROM indexing_schedules WHERE job_id = ?", (job_id,))
        schedule_exists = cursor.fetchone()
        if not schedule_exists:
            raise HTTPException(status_code=404, detail=f"Schedule with job_id '{job_id}' not found.")

        # Remove from APScheduler
        try:
            scheduler.remove_job(job_id)
            logger.info(f"Removed job_id='{job_id}' from scheduler.")
        except JobLookupError:
            logger.warning(f"Job_id='{job_id}' not found in scheduler, might have already been removed or never run.")
        
        # Delete from database
        cursor.execute("DELETE FROM indexing_schedules WHERE job_id = ?", (job_id,))
        conn.commit()
        logger.info(f"Deleted schedule job_id='{job_id}' from database.")
        
        return {"message": f"Schedule job_id='{job_id}' deleted successfully."}

    except HTTPException: # Re-raise HTTPExceptions directly
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting schedule job_id='{job_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete schedule: {e}")
    finally:
        conn.close()



if __name__ == "__main__":

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

import os
import pathlib # Corrected import to pathlib instead of Path
import logging
import mimetypes
import chardet
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_file_hash(file_path: str) -> str | None:
    """Calculate SHA256 hash of file content"""
    try:
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating SHA256 hash for {file_path}: {e}")
        return None

def is_binary_file(file_path: str) -> bool:
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

        file_ext = pathlib.Path(file_path).suffix.lower()
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

def is_text_file(file_path: str) -> bool:
    """Determine if a file is text-based and safe to read"""
    try:
        # First check if it's binary
        if is_binary_file(file_path): # Removed self.
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

        file_ext = pathlib.Path(file_path).suffix.lower()
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

def extract_text_content(file_path: str) -> str | None:
    """Extract text content from file"""
    try:
        if not is_text_file(file_path): # Removed self.
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

def should_skip_directory(dir_path: str) -> bool:
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

# Placeholder for pwd import if needed on non-Unix, or conditional import
try:
    import pwd
except ImportError:
    # Define a fallback for non-Unix systems or if pwd is not available
    class PwdFallback:
        def getpwuid(self, uid):
            # Return a mock object that mimics pwd.getpwuid(...).pw_name
            class PwuidMock:
                def __init__(self, name="unknown"):
                    self.pw_name = name
            return PwuidMock()

    pwd = PwdFallback()

def get_file_owner(stat_info) -> str:
    """Gets the file owner, with a fallback for non-Unix systems."""
    try:
        return pwd.getpwuid(stat_info.st_uid).pw_name
    except (KeyError, AttributeError): # Root user on some systems might not have a name
        return "unknown"
    except Exception as e: # Catch any other pwd related error
        logger.warning(f"Could not determine file owner: {e}")
        return "unknown"

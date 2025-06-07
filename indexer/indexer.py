import os
import pathlib
from datetime import datetime
import logging
import pwd # For get_owner_name

from sqlalchemy.orm import Session
from utils.file_ops import get_file_hash, is_text_file # SHA256 hash function and text file check
# Assuming database_session.py is in the database directory
from database.database_session import SessionLocal
# Assuming models.py is in the database directory
import database.models as db_models # Changed to import database.models as db_models
from database.models import Embedding # Explicitly import Embedding model
from openai_client.client import get_embedding_for_file # Import embedding generation function

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def get_owner_name(stat_info) -> str:
    """
    Retrieves the owner's username from stat_info.
    Returns "unknown" if the owner cannot be determined.
    """
    try:
        return pwd.getpwuid(stat_info.st_uid).pw_name
    except (KeyError, AttributeError, ImportError) as e: # Added ImportError
        logger.warning(f"Could not determine file owner UID {stat_info.st_uid}: {e}. Falling back to 'unknown'.")
        # On Windows, pwd module is not available, so this fallback is essential.
        return "unknown"
    except Exception as e: # Catch any other pwd related error
        logger.error(f"Unexpected error determining file owner for UID {stat_info.st_uid}: {e}")
        return "unknown"


def index_file_metadata(db_session: Session, file_path: str, build_id: int) -> db_models.File | None:
    """
    Indexes metadata for a single file and stores it in the database.
    For symlinks, hash is stored as None.
    """
    logger.info(f"Attempting to index metadata for file: {file_path} with build_id: {build_id}")

    try:
        # Get file stats, do not follow symlinks to get info about the link itself
        stat_info = os.stat(file_path, follow_symlinks=False)
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}. Skipping.")
        return None
    except Exception as e:
        logger.error(f"Error stating file {file_path}: {e}. Skipping.")
        return None

    is_symlink = os.path.islink(file_path)
    file_hash = None # Default for symlinks or if hashing fails

    if not is_symlink:
        # Calculate SHA256 hash only for regular files
        file_hash = get_file_hash(file_path)
        if file_hash is None:
            logger.warning(f"Could not calculate hash for {file_path}. Proceeding without hash.")
    else:
        logger.info(f"{file_path} is a symbolic link. Hash will not be calculated.")

    path = str(pathlib.Path(file_path).resolve()) # Store resolved absolute path
    filename = os.path.basename(file_path)
    size_bytes = stat_info.st_size # Size of the link file itself if symlink

    # Timestamps
    try:
        creation_date = datetime.fromtimestamp(stat_info.st_ctime)
        modified_date = datetime.fromtimestamp(stat_info.st_mtime)
    except Exception as e:
        logger.error(f"Error converting timestamps for {file_path}: {e}. Using current time as fallback.")
        creation_date = datetime.now()
        modified_date = datetime.now()

    owner = get_owner_name(stat_info)

    # Create File SQLAlchemy model instance
    db_file_data = {
        "path": path,
        "filename": filename,
        "hash": file_hash, # This will be None for symlinks
        "size_bytes": size_bytes,
        "is_symlink": is_symlink,
        "build_id": build_id,
        # Assuming your db_models.File does not have these directly but are good for logging
        # "creation_date_os": creation_date,
        # "modified_date_os": modified_date,
        # "owner_os": owner,
    }

    # Note: SQLAlchemy model for File should not have creation_date_os, modified_date_os etc.
    # It should have columns like `created_at`, `updated_at` if you want the DB to manage timestamps
    # The OS-level ctime/mtime are usually not stored directly unless specifically required.
    # For now, I am assuming the File model only takes fields defined in database/models.py
    # which are: path, filename, hash, size_bytes, is_symlink, build_id

    db_file_instance = None
    try:
        db_file_instance = db_models.File(**db_file_data)
        db_session.add(db_file_instance)
        db_session.commit()
        db_session.refresh(db_file_instance)
        logger.info(f"Successfully indexed metadata for file: {file_path} (ID: {db_file_instance.id})")
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error saving file metadata for {file_path} to database: {e}")
        return None # Return early if file metadata saving fails

    # If file metadata was saved successfully, and it's not a symlink, try to generate and save embedding
    if db_file_instance and not db_file_instance.is_symlink:
        if is_text_file(file_path): # Check if it's a text file before attempting embedding
            logger.info(f"Attempting to generate embedding for text file: {file_path}")
            embedding_vector = get_embedding_for_file(file_path) # This handles its own logging for success/failure

            if embedding_vector:
                try:
                    db_embedding = Embedding(file_id=db_file_instance.id, embedding=embedding_vector)
                    db_session.add(db_embedding)
                    db_session.commit()
                    logger.info(f"Successfully saved embedding for file: {file_path} (File ID: {db_file_instance.id})")
                except Exception as e:
                    db_session.rollback()
                    logger.error(f"Error saving embedding for file {file_path} to database: {e}")
                    # Do not return None here, as file metadata is already saved.
                    # The function will return the db_file_instance below.
            else:
                logger.info(f"No embedding vector generated for {file_path} (e.g. not text, empty, or API error).")
        else:
            logger.info(f"File {file_path} is not a text file. Skipping embedding generation.")

    return db_file_instance

if __name__ == '__main__':
    # Example Usage (requires a running database as configured in .env)
    logger.info("Running indexer.py directly for testing.")

    # Create a dummy Session for demonstration if DB is not available
    # In a real scenario, SessionLocal would provide a real DB session.
    # For this example, let's assume the DB is up.

    # Setup: Create a dummy build and a dummy file
    if not os.path.exists("test_index_dir"):
        os.makedirs("test_index_dir")

    dummy_file_path = "test_index_dir/sample.txt"
    with open(dummy_file_path, "w") as f:
        f.write("This is a test file for indexing.")

    dummy_symlink_path = "test_index_dir/sample_link.txt"
    if os.path.exists(dummy_symlink_path):
        os.unlink(dummy_symlink_path) # Remove existing link if any

    # Symlink creation might fail on Windows if not run as admin or dev mode not enabled
    try:
        os.symlink(dummy_file_path, dummy_symlink_path)
        logger.info(f"Created symlink: {dummy_symlink_path} -> {dummy_file_path}")
    except OSError as e:
        logger.warning(f"Could not create symlink for testing (OSError): {e}. Symlink tests might be skipped.")
    except AttributeError:
         logger.warning(f"os.symlink not available on this system. Symlink tests might be skipped.")


    # Get a DB session
    session = SessionLocal() # type: ignore

    # Dummy build_id for testing
    # In a real application, this would come from an existing Build record
    test_build_id = 1

    # --- Mocking a Build object for the purpose of the test if one doesn't exist ---
    # This is to ensure the foreign key constraint for build_id can be satisfied.
    # In a real run, a Build record with id=test_build_id should exist.
    # For this standalone test, we might need to create one if the DB is clean.
    try:
        build_exists = session.query(db_models.Build).filter_by(id=test_build_id).first()
        if not build_exists:
            logger.info(f"Test Build with id={test_build_id} not found, creating one.")
            test_build = db_models.Build(id=test_build_id, path="/tmp/dummy_build_path")
            session.add(test_build)
            session.commit()
            logger.info(f"Created test Build with id={test_build_id}.")
        else:
            logger.info(f"Test Build with id={test_build_id} already exists.")
    except Exception as e:
        session.rollback()
        logger.error(f"Could not ensure test Build with id={test_build_id} exists: {e}")
        logger.error("Please ensure your database is initialized and a Build record with id=1 exists, or adjust test_build_id.")
        # Exit if we can't guarantee the build
        # exit(1) # Commenting out to allow script to run further even if build creation fails

    logger.info(f"\n--- Indexing regular file: {dummy_file_path} ---")
    indexed_file_obj = index_file_metadata(session, dummy_file_path, test_build_id) # Renamed variable
    if indexed_file_obj:
        print(f"Indexed File DB ID: {indexed_file_obj.id}, Path: {indexed_file_obj.path}, Hash: {indexed_file_obj.hash}, Symlink: {indexed_file_obj.is_symlink}")
        # Check if embedding was created
        embedding_record = session.query(Embedding).filter_by(file_id=indexed_file_obj.id).first()
        if embedding_record:
            print(f"  Embedding found for file ID {indexed_file_obj.id}, vector length: {len(embedding_record.embedding)}")
        else:
            print(f"  No embedding found for file ID {indexed_file_obj.id} (this is expected if OPENAI_API_KEY is not set or file is not suitable).")
    else:
        print(f"Failed to index {dummy_file_path}")

    if os.path.exists(dummy_symlink_path): # Check if symlink was created successfully
        logger.info(f"\n--- Indexing symlink: {dummy_symlink_path} ---")
        indexed_symlink_obj = index_file_metadata(session, dummy_symlink_path, test_build_id) # Renamed variable
        if indexed_symlink_obj:
            print(f"Indexed Symlink DB ID: {indexed_symlink_obj.id}, Path: {indexed_symlink_obj.path}, Hash: {indexed_symlink_obj.hash}, Symlink: {indexed_symlink_obj.is_symlink}")
            # Embedding should not be created for symlinks
            embedding_record_symlink = session.query(Embedding).filter_by(file_id=indexed_symlink_obj.id).first()
            if embedding_record_symlink:
                 print(f"  ERROR: Embedding found for symlink file ID {indexed_symlink_obj.id}. This should not happen.")
            else:
                print(f"  No embedding found for symlink file ID {indexed_symlink_obj.id} (this is expected).")
        else:
            print(f"Failed to index {dummy_symlink_path}")
    else:
        logger.info(f"Skipping symlink test as {dummy_symlink_path} does not exist.")

    # Clean up session
    session.close()

    # Clean up dummy files (optional)
    # os.remove(dummy_file_path)
    # if os.path.exists(dummy_symlink_path): os.remove(dummy_symlink_path) # On Windows, os.remove works for symlinks too
    # os.rmdir("test_index_dir")
    logger.info("\nIndexer test run finished. Check logs and DB for results.")
    logger.info("Make sure your .env file is configured correctly for DATABASE_URL.")

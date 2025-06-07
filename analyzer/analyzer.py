import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
# array_agg is PostgreSQL specific, imported for use.
# For SQLite, group_concat is the typical alternative.
# Since the project uses PostgreSQL (pgvector), array_agg is appropriate.
from sqlalchemy.dialects.postgresql import array_agg
import rapidfuzz.fuzz # For fuzzy string matching
import rapidfuzz.process # For processing collections of strings (optional here but good to know)

from database import models as db_models # SQLAlchemy models
from utils.file_ops import extract_text_content, is_text_file # File operations
from typing import List, Dict, Any # For type hinting, changed to List, Dict, Any

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def find_exact_duplicates(db_session: Session) -> List[Dict[str, any]]:
    """
    Finds sets of exact duplicate files based on their SHA256 hash.
    Excludes symlinks and files without a hash.
    Returns a list of dictionaries, each representing a set of duplicates.
    """
    logger.info("Attempting to find exact duplicate files...")

    try:
        # Query to find duplicate files
        # Selects hash, count of files with that hash, and a list of their paths
        query = db_session.query(
            db_models.File.hash,
            func.count(db_models.File.id).label('count'),
            array_agg(db_models.File.path).label('file_paths') # PostgreSQL specific
            # For SQLite, you might use: func.group_concat(db_models.File.path).label('file_paths')
            # but then file_paths would be a comma-separated string.
        ).filter(
            db_models.File.hash.isnot(None),      # Only consider files that have a hash
            db_models.File.is_symlink == False    # Exclude symbolic links from duplicate analysis
        ).group_by(
            db_models.File.hash
        ).having(
            func.count(db_models.File.id) > 1      # Only include hashes that appear more than once
        ).order_by(
            func.count(db_models.File.id).desc()  # Order by the number of duplicates, descending
        )

        results = query.all()

        duplicate_sets: List[Dict[str, any]] = []
        for row in results:
            duplicate_sets.append({
                'hash': row.hash,
                'count': row.count,
                'file_paths': row.file_paths # This will be a list due to array_agg
            })

        logger.info(f"Found {len(duplicate_sets)} sets of exact duplicate files.")
        return duplicate_sets

    except Exception as e:
        logger.error(f"Error finding exact duplicates: {e}")
        # Depending on the desired error handling, you might want to raise the exception
        # or return an empty list or specific error indicator.
        return []

if __name__ == '__main__':
    from database.database_session import SessionLocal, init_db
    from database.models import File, Build # Import File and Build for creating test data
    import os # For os.path.exists for fuzzy test file creation

    logger.info("Running analyzer.py directly for testing.")

    # Initialize DB (ensure tables are created)
    try:
        init_db()
        logger.info("Database initialized/checked.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}. Ensure DATABASE_URL is correct in .env and DB is running.")
        exit(1)

    session = SessionLocal() # type: ignore

    # Clean up existing test data to make test idempotent (optional, be careful)
    # session.query(File).delete()
    # session.query(Build).delete()
    # session.commit()

    # Add some mock data for testing
    # Ensure a Build record exists, or create one
    test_build_id = 1
    build = session.query(Build).filter_by(id=test_build_id).first()
    if not build:
        build = Build(id=test_build_id, path="/tmp/test_build_for_analyzer")
        session.add(build)
        try:
            session.commit()
            logger.info(f"Created test Build with ID {build.id}")
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create test build: {e}")
            exit(1)


    mock_files_data = [
        # Set 1 of duplicates
        {"path": "/test/fileA.txt", "filename": "fileA.txt", "hash": "hash123", "size_bytes": 100, "is_symlink": False, "build_id": test_build_id},
        {"path": "/test/fileB.txt", "filename": "fileB.txt", "hash": "hash123", "size_bytes": 100, "is_symlink": False, "build_id": test_build_id},
        {"path": "/test/fileC.txt", "filename": "fileC.txt", "hash": "hash123", "size_bytes": 100, "is_symlink": False, "build_id": test_build_id},
        # Set 2 of duplicates
        {"path": "/test/fileD.txt", "filename": "fileD.txt", "hash": "hash456", "size_bytes": 200, "is_symlink": False, "build_id": test_build_id},
        {"path": "/test/fileE.txt", "filename": "fileE.txt", "hash": "hash456", "size_bytes": 200, "is_symlink": False, "build_id": test_build_id},
        # Unique file
        {"path": "/test/fileF.txt", "filename": "fileF.txt", "hash": "hash789", "size_bytes": 300, "is_symlink": False, "build_id": test_build_id},
        # Symlink (should be ignored)
        {"path": "/test/linkG.txt", "filename": "linkG.txt", "hash": "hash123", "size_bytes": 50, "is_symlink": True, "build_id": test_build_id},
        # File with no hash (should be ignored)
        {"path": "/test/fileH.txt", "filename": "fileH.txt", "hash": None, "size_bytes": 400, "is_symlink": False, "build_id": test_build_id},
    ]

    for file_data in mock_files_data:
        # Check if file already exists by path to prevent duplicate entries if script is rerun
        exists = session.query(File).filter_by(path=file_data["path"]).first()
        if not exists:
            db_file = File(**file_data)
            session.add(db_file)

    try:
        session.commit()
        logger.info(f"Added/updated mock File data for testing.")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to add mock data: {e}")
        # Proceeding anyway to see if find_exact_duplicates handles empty or partial data.

    duplicates = find_exact_duplicates(session)

    if duplicates:
        print("\nFound Duplicate Sets:")
        for dup_set in duplicates:
            print(f"  Hash: {dup_set['hash']}")
            print(f"  Count: {dup_set['count']}")
            print(f"  Files: {', '.join(dup_set['file_paths'])}")
            print("-" * 20)
    else:
        print("\nNo duplicate sets found or an error occurred.")

    session.close()
    logger.info("Exact duplicates test run finished.")

    # --- Test for find_fuzzy_duplicates ---
    logger.info("\n--- Testing find_fuzzy_duplicates ---")
    session = SessionLocal() # type: ignore

    # Create some dummy files with actual content for fuzzy matching
    # These paths won't be written to DB for this specific test of fuzzy logic,
    # but file content is needed.
    # We need File records in DB to select a target_file_id and candidates.

    # Ensure build record for fuzzy test files
    fuzzy_test_build_id = 2
    fuzzy_build = session.query(Build).filter_by(id=fuzzy_test_build_id).first()
    if not fuzzy_build:
        fuzzy_build = Build(id=fuzzy_test_build_id, path="/tmp/fuzzy_test_build")
        session.add(fuzzy_build)
        try:
            session.commit()
        except: # General exception if commit fails (e.g. unique constraint if run multiple times)
            session.rollback()


    # Mock file data for fuzzy tests
    # We need to ensure these files exist with content if is_text_file and extract_text_content are not mocked.
    # Let's create temporary files for the test.

    test_dir = "temp_fuzzy_test_files"
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)

    fuzzy_file_specs = [
        {"id": 201, "path_suffix": "fuzzy_doc1.txt", "content": "This is the first document for testing fuzzy logic. It has some common words.", "build_id": fuzzy_test_build_id},
        {"id": 202, "path_suffix": "fuzzy_doc2.txt", "content": "This is the second document for testing fuzzy logic. It has some common words and some different ones.", "build_id": fuzzy_test_build_id},
        {"id": 203, "path_suffix": "fuzzy_doc3.txt", "content": "A completely different text to ensure it does not match strongly.", "build_id": fuzzy_test_build_id},
        {"id": 204, "path_suffix": "fuzzy_doc4_same_build.txt", "content": "This is the first document for testing fuzzy logic. It has some common words. (Almost identical to doc1)", "build_id": fuzzy_test_build_id},
        {"id": 205, "path_suffix": "fuzzy_doc5_other_build.txt", "content": "This is the first document for testing fuzzy logic. (Similar to doc1, different build)", "build_id": fuzzy_test_build_id + 1}, # Different build ID
        {"id": 206, "path_suffix": "fuzzy_symlink.txt", "content": "Symlink content", "is_symlink": True, "build_id": fuzzy_test_build_id},
        {"id": 207, "path_suffix": "fuzzy_notext.bin", "content": b"\x00\x01\x02", "is_text": False, "build_id": fuzzy_test_build_id}, # Non-text file
    ]

    # Ensure another build record for file 205
    other_build_id = fuzzy_test_build_id + 1
    other_build = session.query(Build).filter_by(id=other_build_id).first()
    if not other_build:
        other_build = Build(id=other_build_id, path=f"/tmp/fuzzy_test_build_{other_build_id}")
        session.add(other_build)
        try:
            session.commit()
        except:
            session.rollback()


    for spec in fuzzy_file_specs:
        full_path = os.path.join(test_dir, spec["path_suffix"])
        is_text = spec.get("is_text", True) # Default to true if not specified
        if is_text:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(spec["content"])
        else: # Binary content
             with open(full_path, "wb") as f:
                f.write(spec["content"])


        # Add to DB if not exists
        file_rec = session.query(File).filter_by(id=spec["id"]).first()
        if not file_rec:
            file_rec = File(
                id=spec["id"], path=full_path, filename=spec["path_suffix"],
                hash=f"fuzzy_hash_{spec['id']}", size_bytes=len(spec["content"]),
                is_symlink=spec.get("is_symlink", False), build_id=spec["build_id"]
            )
            session.add(file_rec)
    try:
        session.commit()
        logger.info("Mock data for fuzzy duplicate testing created/updated in DB and temp files written.")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to set up mock data for fuzzy tests: {e}")

    if os.path.exists(os.path.join(test_dir, "fuzzy_doc1.txt")):
        target_file_id_for_fuzzy = 201 # ID of fuzzy_doc1.txt

        logger.info(f"\n--- Finding fuzzy duplicates for File ID {target_file_id_for_fuzzy} (scope 'build', threshold 70) ---")
        fuzzy_results_build = find_fuzzy_duplicates(session, target_file_id_for_fuzzy, threshold=70, scope='build')
        print_fuzzy_results(fuzzy_results_build, target_file_id_for_fuzzy, 'build')

        logger.info(f"\n--- Finding fuzzy duplicates for File ID {target_file_id_for_fuzzy} (scope 'all', threshold 70) ---")
        fuzzy_results_all = find_fuzzy_duplicates(session, target_file_id_for_fuzzy, threshold=70, scope='all')
        print_fuzzy_results(fuzzy_results_all, target_file_id_for_fuzzy, 'all')

        # Test with a non-text file target
        target_non_text_id = 207
        logger.info(f"\n--- Finding fuzzy duplicates for NON-TEXT File ID {target_non_text_id} ---")
        fuzzy_results_non_text = find_fuzzy_duplicates(session, target_non_text_id, threshold=70)
        print_fuzzy_results(fuzzy_results_non_text, target_non_text_id, 'all')


    else:
        logger.warning(f"Skipping fuzzy tests as target file for ID {target_file_id_for_fuzzy} was not found on disk.")


    # Clean up temp files
    # import shutil
    # if os.path.exists(test_dir):
    #     shutil.rmtree(test_dir)
    #     logger.info(f"Cleaned up temporary directory: {test_dir}")

    session.close()
    logger.info("Fuzzy duplicates test run finished.")

def print_fuzzy_results(results: List[Dict[str, Any]], target_id: int, scope: str):
    if results:
        print(f"Fuzzy duplicates for Target ID {target_id} (scope: {scope}):")
        for match in results:
            print(f"  - Match ID: {match['file_id']}, Path: {match['path']}, Score: {match['score']:.2f}")
    else:
        print(f"No fuzzy duplicates found for Target ID {target_id} (scope: {scope}) or target was unsuitable.")

# New function definition for find_fuzzy_duplicates
def find_fuzzy_duplicates(db_session: Session, target_file_id: int, threshold: int = 80, scope: str = 'build', limit_comparisons: int = 1000) -> list[dict]:
    logger.info(f"Attempting to find fuzzy duplicates for target_file_id: {target_file_id} with threshold: {threshold}, scope: {scope}")

    target_file = db_session.query(db_models.File).filter(db_models.File.id == target_file_id).first()

    if not target_file:
        logger.warning(f"Target file with ID {target_file_id} not found in database.")
        return []

    if target_file.is_symlink:
        logger.info(f"Target file {target_file.path} (ID: {target_file_id}) is a symlink. Skipping fuzzy duplicate search.")
        return []

    if not is_text_file(target_file.path): # Check if the actual file is text
        logger.info(f"Target file {target_file.path} (ID: {target_file_id}) is not a text file. Skipping fuzzy duplicate search.")
        return []

    target_content = extract_text_content(target_file.path)
    if not target_content:
        logger.info(f"Could not extract text content from target file {target_file.path} (ID: {target_file_id}). Skipping.")
        return []

    candidates_query = None
    if scope == 'build':
        if target_file.build_id is None:
            logger.warning(f"Target file {target_file.id} does not have a build_id. Cannot scope to build. Returning empty.")
            return []
        logger.info(f"Searching for fuzzy duplicates within build ID: {target_file.build_id}")
        candidates_query = db_session.query(db_models.File).filter(
            db_models.File.build_id == target_file.build_id,
            db_models.File.id != target_file_id,
            db_models.File.is_symlink == False
        )
    else: # scope == 'all' or default
        logger.info("Searching for fuzzy duplicates across all files (excluding target and symlinks).")
        candidates_query = db_session.query(db_models.File).filter(
            db_models.File.id != target_file_id,
            db_models.File.is_symlink == False
        )

    # Apply a limit to manage performance. Consider more sophisticated sampling for large datasets.
    candidate_files = candidates_query.limit(limit_comparisons).all()
    logger.info(f"Comparing against {len(candidate_files)} candidate files (limit was {limit_comparisons}).")

    fuzzy_matches: List[Dict[str, Any]] = [] # Ensure this is List[Dict[str, Any]]
    for candidate_file in candidate_files:
        if candidate_file.id == target_file_id: # Should be filtered by query, but double check
            continue

        if not is_text_file(candidate_file.path): # Check if candidate is a text file
            # logger.debug(f"Candidate file {candidate_file.path} is not text. Skipping.") # Too verbose for INFO
            continue

        candidate_content = extract_text_content(candidate_file.path)
        if not candidate_content:
            # logger.debug(f"No content for candidate {candidate_file.path}. Skipping.") # Too verbose for INFO
            continue

        try:
            score = rapidfuzz.fuzz.ratio(target_content, candidate_content)
        except Exception as e:
            logger.error(f"Error calculating fuzzy ratio between target {target_file_id} and candidate {candidate_file.id}: {e}")
            continue # Skip this pair if ratio calculation fails

        if score >= threshold:
            fuzzy_matches.append({
                'file_id': candidate_file.id,
                'path': candidate_file.path,
                'score': score
            })

    fuzzy_matches.sort(key=lambda x: x['score'], reverse=True)

    logger.info(f"Found {len(fuzzy_matches)} fuzzy matches for target file ID {target_file_id} with threshold {threshold}.")
    return fuzzy_matches

import logging
from sqlalchemy.orm import Session
from sqlalchemy import func # For potential future use, not strictly needed for cosine_distance

from database import models as db_models
from database.database_session import SessionLocal, init_db # For testing
from typing import Tuple, Optional, List # For type hints, changed to use these instead of builtins for older python if needed

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def find_most_similar_file(db: Session, file_id: int) -> Tuple[int, float] | None:
    """
    Finds the most similar file to the given file_id based on embedding cosine distance.
    Updates the target file's embedding record with the closest_file_id and similarity_score.
    """
    logger.info(f"Attempting to find the most similar file for file_id: {file_id}")

    try:
        # Retrieve the embedding for the target file_id
        target_embedding_obj = db.query(db_models.Embedding).filter(db_models.Embedding.file_id == file_id).first()

        if not target_embedding_obj:
            logger.warning(f"No embedding found for target file_id: {file_id}. Cannot find similar files.")
            return None

        if not target_embedding_obj.embedding:
            logger.warning(f"Embedding data is missing for target file_id: {file_id}. Cannot find similar files.")
            return None

        # Query for the most similar file using cosine distance
        # The .cosine_distance operator comes from pgvector.sqlalchemy.Vector
        # It calculates the distance (0 = identical, 1 = orthogonal, 2 = opposite)
        closest_file_result = db.query(
            db_models.Embedding.file_id,
            db_models.Embedding.embedding.cosine_distance(target_embedding_obj.embedding).label('distance')
        ).filter(
            db_models.Embedding.file_id != file_id  # Exclude the file itself
        ).order_by(
            'distance'  # Order by distance (ascending, so closest first)
        ).limit(1).first()

        if closest_file_result:
            closest_file_id = closest_file_result.file_id
            distance = closest_file_result.distance

            # Similarity score for cosine distance is 1 - distance
            # Cosine distance is in [0, 2]. Similarity score will be in [-1, 1].
            # A distance of 0 means identical (similarity 1).
            # A distance of 1 means orthogonal (similarity 0).
            # A distance of 2 means opposite (similarity -1).
            similarity_score = 1.0 - distance

            # Update the original target_embedding_obj with the findings
            target_embedding_obj.closest_file_id = closest_file_id
            target_embedding_obj.similarity_score = similarity_score

            db.commit()
            db.refresh(target_embedding_obj)

            logger.info(f"Most similar file to {file_id} is {closest_file_id} with similarity score: {similarity_score:.4f} (distance: {distance:.4f})")
            return closest_file_id, similarity_score
        else:
            logger.info(f"No other files found to compare with file_id: {file_id}.")
            # Clear previous similarity if no other file is found now
            if target_embedding_obj.closest_file_id is not None or target_embedding_obj.similarity_score is not None:
                target_embedding_obj.closest_file_id = None
                target_embedding_obj.similarity_score = None
                db.commit()
                db.refresh(target_embedding_obj)
                logger.info(f"Cleared previous similarity data for file_id: {file_id} as no comparables were found.")
            return None

    except Exception as e:
        db.rollback()
        logger.error(f"Error finding most similar file for file_id {file_id}: {e}", exc_info=True)
        return None

def compute_similarity_for_all_files(db: Session):
    """
    Computes and updates the most similar file and similarity score for all files
    that have embeddings.
    """
    logger.info("Starting batch computation of similarity for all files with embeddings.")

    try:
        # Query all file_ids that have embeddings
        # Using .with_entities to get just the file_id column, returns list of tuples
        all_embedding_file_ids_tuples = db.query(db_models.Embedding.file_id).all()
        all_file_ids = [fid_tuple[0] for fid_tuple in all_embedding_file_ids_tuples]

        if not all_file_ids:
            logger.info("No files with embeddings found to process.")
            return

        logger.info(f"Found {len(all_file_ids)} files with embeddings to process.")

        processed_count = 0
        for file_id in all_file_ids:
            find_most_similar_file(db, file_id) # This function handles its own logging and commit
            processed_count += 1
            if processed_count % 10 == 0 or processed_count == len(all_file_ids):
                logger.info(f"Processed {processed_count}/{len(all_file_ids)} files for similarity.")

        logger.info("Batch computation of similarity for all files completed.")

    except Exception as e:
        logger.error(f"Error during batch similarity computation: {e}", exc_info=True)


if __name__ == '__main__':
    from database.models import File, Embedding, Build # For creating test data
    import random

    logger.info("Running similarity_engine.py directly for testing.")

    # Initialize DB (ensure tables are created, pgvector extension enabled)
    try:
        init_db()
        logger.info("Database initialized/checked.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}. Ensure DATABASE_URL is correct in .env and DB is running.")
        exit(1)

    session = SessionLocal() # type: ignore

    # --- Setup Mock Data ---
    # Ensure a Build record exists
    test_build_id = 1
    build = session.query(Build).filter_by(id=test_build_id).first()
    if not build:
        build = Build(id=test_build_id, path="/tmp/test_build_for_similarity")
        session.add(build)
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            logger.critical(f"Failed to create test Build: {e}. Exiting test.")
            exit(1)

    # Create some mock File and Embedding records
    # Embedding vector dimension should match what's defined in models.py (e.g., 1536)
    embedding_dim = 1536
    mock_files_embeddings = {
        101: {"path": "/test/sim_fileA.txt", "hash": "sim_hashA", "embedding_v": [random.uniform(0, 1) for _ in range(embedding_dim)]},
        102: {"path": "/test/sim_fileB.txt", "hash": "sim_hashB", "embedding_v": [random.uniform(0, 1) for _ in range(embedding_dim)]},
        103: {"path": "/test/sim_fileC.txt", "hash": "sim_hashC", "embedding_v": [v * 1.05 for v in mock_files_embeddings[101]["embedding_v"]]}, # Similar to A
        104: {"path": "/test/sim_fileD.txt", "hash": "sim_hashD", "embedding_v": [random.uniform(-1, 0) for _ in range(embedding_dim)]}, # Different from others
        105: {"path": "/test/sim_fileE_no_emb.txt", "hash": "sim_hashE_no_emb"}, # File without embedding initially
        106: {"path": "/test/sim_fileF.txt", "hash": "sim_hashF", "embedding_v": mock_files_embeddings[101]["embedding_v"][:]} # Identical to A
    }

    for file_id_key, data in mock_files_embeddings.items():
        file_obj = session.query(File).filter_by(id=file_id_key).first()
        if not file_obj:
            file_obj = File(id=file_id_key, path=data["path"], filename=os.path.basename(data["path"]),
                            hash=data["hash"], size_bytes=100, is_symlink=False, build_id=test_build_id)
            session.add(file_obj)

        if "embedding_v" in data:
            emb_obj = session.query(Embedding).filter_by(file_id=file_id_key).first()
            if not emb_obj:
                emb_obj = Embedding(file_id=file_id_key, embedding=data["embedding_v"], closest_file_id=None, similarity_score=None)
                session.add(emb_obj)
            else: # Ensure embedding data is updated if script is rerun
                emb_obj.embedding = data["embedding_v"]
                emb_obj.closest_file_id = None # Reset for fresh test
                emb_obj.similarity_score = None
    try:
        session.commit()
        logger.info("Mock data for files and embeddings created/updated.")
    except Exception as e:
        session.rollback()
        logger.error(f"Error setting up mock data: {e}")

    # --- Test find_most_similar_file for a specific file ---
    logger.info("\n--- Testing find_most_similar_file for File ID 101 ---")
    # File 103 is designed to be similar to 101. File 106 is identical.
    # Depending on exact float values, 106 should be closer than 103.
    # The distance for 106 should be ~0.
    result = find_most_similar_file(session, 101)
    if result:
        closest_id, score = result
        print(f"Test (find_most_similar_file for 101): Closest to 101 is {closest_id} with score {score:.4f}")
        # Verify in DB
        updated_emb_101 = session.query(Embedding).filter_by(file_id=101).first()
        if updated_emb_101:
            print(f"DB check for 101: closest_file_id={updated_emb_101.closest_file_id}, similarity_score={updated_emb_101.similarity_score:.4f if updated_emb_101.similarity_score else None}")
    else:
        print("Test (find_most_similar_file for 101): No similar file found or error.")

    # --- Test compute_similarity_for_all_files ---
    logger.info("\n--- Testing compute_similarity_for_all_files ---")
    compute_similarity_for_all_files(session)

    print("\n--- Results after compute_similarity_for_all_files (from DB) ---")
    all_embeddings_after = session.query(Embedding).order_by(Embedding.file_id).all()
    for emb in all_embeddings_after:
        if emb.file_id == 105 : continue # Skip file 105 as it has no embedding
        print(f"File ID: {emb.file_id}, Closest File ID: {emb.closest_file_id}, Similarity Score: {emb.similarity_score:.4f if emb.similarity_score is not None else 'N/A'}")

    # Expected for File 101: Closest should be 106 (identical embedding), score ~1.0
    # Expected for File 103: Closest might be 101 or 106.
    # Expected for File 106: Closest should be 101 (identical embedding), score ~1.0
    # Expected for File 102, 104: Might point to any other file, scores will vary.

    session.close()
    logger.info("Similarity engine test run finished.")

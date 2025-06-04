import os
import sqlite3
import tempfile
import datetime
import sys
from pathlib import Path

# Ensure backend directory is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import FileIndexer, SearchEngine, SearchRequest


def setup_temp_db():
    temp_dir = tempfile.TemporaryDirectory()
    db_path = os.path.join(temp_dir.name, "test.db")
    # Initialize database using FileIndexer to ensure schema is correct
    FileIndexer(db_path=db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    now = datetime.datetime.now()
    sample_rows = [
        (
            "/tmp/test1.txt",
            "test1.txt",
            ".txt",
            100,
            now,
            now,
            "user1",
            "hash1",
            "",
            1,
        ),
        (
            "/tmp/test2.log",
            "test2.log",
            ".log",
            200,
            now,
            now,
            "user2",
            "hash2",
            "",
            1,
        ),
    ]

    for row in sample_rows:
        cursor.execute(
            """
            INSERT INTO files_metadata
            (file_path, file_name, file_extension, file_size, creation_date,
             modified_date, owner, content_hash, text_content, is_text_file)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )

    conn.commit()
    conn.close()
    return temp_dir, db_path


def test_search_without_terms_filters_work():
    temp_dir, db_path = setup_temp_db()
    try:
        engine = SearchEngine(db_path=db_path)
        request = SearchRequest(extensions=["txt"], search_terms=None)
        results = engine.search_files(request)
        assert len(results) == 1
        assert results[0]["file_path"] == "/tmp/test1.txt"
    finally:
        temp_dir.cleanup()


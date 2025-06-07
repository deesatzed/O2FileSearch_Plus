import typer
import logging
import pathlib
import os

from sqlalchemy.orm import Session

# Database imports
from database.database_session import SessionLocal, init_db
from database import models as db_models # Renamed for clarity

# Functional module imports
from scanner.scanner import scan_directories
from build_detector.detector import identify_build_folders
from indexer.indexer import index_file_metadata
from analyzer.analyzer import find_exact_duplicates
# Corrected import for find_most_similar_file from similarity_engine.engine
from similarity_engine.engine import find_most_similar_file, compute_similarity_for_all_files

# Initialize Typer app
app = typer.Typer()

# Configure basic logging
# Placed at the top level of the script
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(), # Default to console
        # logging.FileHandler("fso_cli.log") # Optionally add file handler
    ]
)
logger = logging.getLogger(__name__)


@app.command()
def init_db_command():
    """
    Initializes the database, creating tables and enabling extensions if necessary.
    """
    typer.echo("Initializing database...")
    try:
        init_db() # This function from database_session.py handles table creation and extension
        typer.secho("Database initialized successfully.", fg=typer.colors.GREEN)
    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=True)
        typer.secho(f"Database initialization failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

@app.command()
def scan(
    paths_to_scan: list[pathlib.Path] = typer.Argument(..., help="List of directory paths to scan."),
    re_identify_builds: bool = typer.Option(False, "--re-identify-builds", help="Force re-identification of build folders even if they exist."),
    full_reindex: bool = typer.Option(False, "--full-reindex", help="Force re-indexing of all files, even if previously indexed for a build.")
):
    """
    Scans specified directories, identifies build projects, and indexes file metadata and embeddings.
    """
    db: Session = SessionLocal() # type: ignore

    resolved_paths_str = [str(p.resolve()) for p in paths_to_scan]
    typer.echo(f"Starting scan for directories: {resolved_paths_str}")

    try:
        typer.echo("Scanning for all files in specified paths...")
        all_files = scan_directories(resolved_paths_str) # scan_directories handles its own logging
        typer.echo(f"Found a total of {len(all_files)} files across all paths.")

        if not all_files:
            typer.echo("No files found in the specified paths. Exiting scan process.")
            return

        typer.echo("Identifying build folders from the scanned files...")
        # identify_build_folders now checks for existing builds.
        # We might want a flag here if we want to force re-creation or update of build info.
        # For now, it skips if path exists.
        detected_builds = identify_build_folders(db, all_files)

        if not detected_builds:
            typer.echo("No build folders were detected. Indexing will proceed for files without build context if applicable, or halt.")
            # Decide if you want to index files not associated with a build, or just stop.
            # For now, let's assume we only index files within detected builds.
            # If no builds, then nothing further to index in this model.
            return

        typer.echo(f"Detected {len(detected_builds)} build folders.")
        for build_path, build_id in detected_builds:
            typer.echo(f"  - Build: {build_path} (ID: {build_id})")

        files_indexed_total = 0
        for build_path_str, build_id in detected_builds:
            typer.echo(f"\nProcessing files for build: {build_path_str} (ID: {build_id})")
            # Normalize build_path_str to ensure consistent matching (e.g. trailing slashes)
            normalized_build_path = str(pathlib.Path(build_path_str).resolve()) + os.sep

            files_in_build_count = 0
            for file_path_str in all_files:
                normalized_file_path = str(pathlib.Path(file_path_str).resolve())
                # Check if the file belongs to the current build path
                # This simple startswith check works if build_path is a prefix of file_path's directory
                if normalized_file_path.startswith(normalized_build_path):
                    files_in_build_count +=1
                    # TODO: Add logic for full_reindex.
                    # If full_reindex is False, check if file already exists and hash matches.
                    # For now, index_file_metadata will handle `OR REPLACE` if DB supports it,
                    # or fail unique constraint. Better to check first.
                    # Example check (simplified):
                    # existing_file = db.query(db_models.File).filter_by(path=normalized_file_path, build_id=build_id).first()
                    # if existing_file and not full_reindex:
                    #    logger.info(f"File {normalized_file_path} already indexed for build {build_id} and not forcing reindex. Skipping.")
                    #    continue

                    # index_file_metadata also handles embedding generation
                    index_file_metadata(db, normalized_file_path, build_id)

            logger.info(f"Associated {files_in_build_count} files with build {build_path_str}. Indexing them now (if not skipped).")
            files_indexed_total += files_in_build_count # This is more like "processed" than "indexed" if skipping happens

        # Optionally, run similarity computation after indexing new files
        typer.echo("\nComputing similarity for all files with new embeddings (if any)...")
        compute_similarity_for_all_files(db) # This will update closest_file_id and similarity_score

        typer.secho(f"Scan, indexing, and similarity computation complete. Processed {files_indexed_total} file associations.", fg=typer.colors.GREEN)

    except Exception as e:
        logger.error(f"An error occurred during the scan and index process: {e}", exc_info=True)
        typer.secho(f"Scan process failed: {e}", fg=typer.colors.RED)
    finally:
        db.close()
        logger.info("Database session closed.")


@app.command(name="show-duplicates")
def show_duplicates_command():
    """
    Finds and displays sets of exact duplicate files based on content hash.
    """
    db: Session = SessionLocal() # type: ignore
    typer.echo("Finding exact duplicate files...")
    try:
        duplicate_sets = find_exact_duplicates(db)
        if duplicate_sets:
            typer.echo(f"Found {len(duplicate_sets)} sets of duplicate files:")
            for dup_set in duplicate_sets:
                typer.secho(f"\nHash: {dup_set['hash']} - Count: {dup_set['count']}", fg=typer.colors.YELLOW)
                for file_path_str in dup_set['file_paths']: # Ensure it's file_paths_str
                    typer.echo(f"  - {file_path_str}")
        else:
            typer.secho("No duplicate files found.", fg=typer.colors.GREEN)
    except Exception as e:
        logger.error(f"Failed to find duplicates: {e}", exc_info=True)
        typer.secho(f"Failed to find duplicates: {e}", fg=typer.colors.RED)
    finally:
        db.close()

@app.command(name="compare-file")
def compare_file_command(file_id: int = typer.Argument(..., help="The ID of the file to find similarities for.")):
    """
    Finds and displays the most similar file to the given file ID using embeddings.
    """
    db: Session = SessionLocal() # type: ignore
    typer.echo(f"Finding file most similar to file ID: {file_id}")
    try:
        original_file = db.query(db_models.File.path).filter(db_models.File.id == file_id).scalar()
        if not original_file:
            typer.secho(f"Original file with ID {file_id} not found.", fg=typer.colors.RED)
            return

        typer.echo(f"Original file (ID {file_id}): {original_file}")

        result = find_most_similar_file(db, file_id) # This function now updates DB directly.

        if result:
            closest_file_id, similarity_score = result
            closest_file_path = db.query(db_models.File.path).filter(db_models.File.id == closest_file_id).scalar()

            typer.echo(f"Most similar file (ID {closest_file_id}): {closest_file_path}")
            typer.secho(f"Similarity score: {similarity_score:.4f}", fg=typer.colors.CYAN)
        else:
            # Check if the file simply has no other files to compare against or no embedding
            embedding_exists = db.query(db_models.Embedding).filter(db_models.Embedding.file_id == file_id).first()
            if not embedding_exists:
                 typer.secho(f"File ID {file_id} does not have an embedding. Cannot compute similarity.", fg=typer.colors.YELLOW)
            else:
                typer.secho(f"Could not find a similar file for file ID {file_id}, or it was the only one with an embedding.", fg=typer.colors.YELLOW)
    except Exception as e:
        logger.error(f"Failed to compare file {file_id}: {e}", exc_info=True)
        typer.secho(f"Failed to compare file: {e}", fg=typer.colors.RED)
    finally:
        db.close()


@app.command(name="show-build")
def show_build_command(build_id_or_path: str = typer.Argument(..., help="The ID or full path of the build to display.")):
    """
    Displays details for a specific build, including its files.
    """
    db: Session = SessionLocal() # type: ignore
    build_entry = None
    try:
        build_id = int(build_id_or_path)
        build_entry = db.query(db_models.Build).filter(db_models.Build.id == build_id).first()
    except ValueError:
        # Not an integer, assume it's a path
        try:
            normalized_path = str(pathlib.Path(build_id_or_path).resolve())
            build_entry = db.query(db_models.Build).filter(db_models.Build.path == normalized_path).first()
        except Exception as e: # Catch potential errors with path resolution if input is malformed
            logger.error(f"Error processing path '{build_id_or_path}': {e}")
            typer.secho(f"Invalid path provided: {build_id_or_path}", fg=typer.colors.RED)
            db.close()
            return

    if build_entry:
        typer.secho(f"Build Details (ID: {build_entry.id})", fg=typer.colors.BLUE)
        typer.echo(f"Path: {build_entry.path}")
        typer.echo(f"Tag: {build_entry.tag if build_entry.tag else 'N/A'}")
        typer.echo(f"Group ID: {build_entry.group_id if build_entry.group_id else 'N/A'}")

        files_in_build = db.query(
            db_models.File.id,
            db_models.File.path,
            db_models.File.is_symlink,
            db_models.File.filename # Added filename for more context
        ).filter(db_models.File.build_id == build_entry.id).order_by(db_models.File.filename).all() # Ordered by filename

        typer.echo(f"\nFiles ({len(files_in_build)}):")
        if not files_in_build:
            typer.echo("  No files associated with this build.")
        else:
            # Limiting output for brevity
            max_files_to_show = 20
            for i, (f_id, f_path, f_is_symlink, f_name) in enumerate(files_in_build):
                if i >= max_files_to_show:
                    typer.echo(f"  ... and {len(files_in_build) - max_files_to_show} more files.")
                    break
                typer.echo(f"  - ID: {f_id:<5} Name: {f_name:<40} Path: {f_path}{' (symlink)' if f_is_symlink else ''}")
    else:
        typer.secho(f"Build not found with identifier: {build_id_or_path}", fg=typer.colors.RED)

    db.close()


if __name__ == "__main__":
    # This makes the Typer app runnable when the script is executed directly
    # e.g., python main_cli.py scan /path/to/code
    # e.g., python main_cli.py init-db-command
    # Note: Typer command names are auto-generated from function names by default (e.g. init_db_command -> init-db-command)
    # Using @app.command(name="actual-name") is good practice for user-facing commands.
    app()

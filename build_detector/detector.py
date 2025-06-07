import os
import pathlib
import logging
from sqlalchemy.orm import Session
from database import models as db_models # Corrected import

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def identify_build_folders(db_session: Session, all_file_paths: list[str]) -> list[tuple[str, int]]:
    """
    Identifies potential build root folders from a list of file paths,
    creates Build records in the database for them, and returns a list of (path, id) tuples.
    """
    detected_builds: list[tuple[str, int]] = []
    potential_build_roots: set[str] = set()

    project_root_files = [
        'Makefile', 'pom.xml', 'build.gradle', 'setup.py', 'Cargo.toml',
        'package.json', 'manage.py', # 'settings.py' is checked in conjunction with 'manage.py'
        'CMakeLists.txt', 'WORKSPACE', 'BUILD', # Bazel
        '.git', # Presence of .git directory often signifies a project root
        'requirements.txt', 'Pipfile', 'pyproject.toml' # Python project markers
    ]
    # Django specific check: if manage.py is found, also check for a common settings dir/file nearby.
    # This is a simplified check. A more robust check would parse manage.py or look for specific settings.
    django_settings_indicators = ['settings.py'] # Could also be a directory like 'project_name/settings.py'

    build_artifact_dirs = ['target', 'dist', 'build', 'bin', 'out', 'Release', 'Debug']

    # These directories, if they are parents of artifact dirs, are less likely to be the *actual* root
    # e.g. /project/src/target -> /project is root, not /project/src
    # However, this logic is tricky. A simpler approach is to identify roots by markers
    # and then associate files to the *closest* (most specific) root.
    # For now, generic_code_dirs_to_ignore_as_root is not used directly in this manner to avoid complexity.
    # generic_code_dirs_to_ignore_as_root = ['src', 'lib', 'app', 'tests', 'docs', 'examples', 'samples']


    path_objects = [pathlib.Path(p) for p in all_file_paths]

    for file_path in path_objects:
        file_name = file_path.name
        parent_dir = file_path.parent

        # Check for project root files
        if file_name in project_root_files:
            if file_name == 'package.json':
                # Higher confidence if node_modules or common build output dirs exist
                if (parent_dir / 'node_modules').is_dir() or \
                   (parent_dir / 'dist').is_dir() or \
                   (parent_dir / 'build').is_dir():
                    potential_build_roots.add(str(parent_dir.resolve()))
                # else: still consider it a potential root, but with lower confidence (not handled here)
            elif file_name == 'manage.py':
                # Check for settings.py in the same directory or a common app subdirectory
                found_settings = False
                for indicator in django_settings_indicators:
                    if (parent_dir / indicator).exists():
                        found_settings = True
                        break
                    # Check common pattern like parent_dir/project_name/settings.py
                    # This requires listing subdirectories, which can be slow.
                    # Simplified: check only direct settings.py for now.
                if found_settings:
                    potential_build_roots.add(str(parent_dir.resolve()))
                # else: still add manage.py's parent as a potential root, could be a partial Django structure
            elif file_name == '.git' and file_path.is_dir(): # Ensure .git is a directory
                 potential_build_roots.add(str(parent_dir.resolve()))
            elif file_path.is_file(): # For other markers, ensure they are files
                potential_build_roots.add(str(parent_dir.resolve()))


        # Check for parent of build artifact directories
        # parent_dir is some_path/artifact_dir, so parent_dir.parent is some_path
        if parent_dir.name in build_artifact_dirs and parent_dir.parent is not None:
            # We add the grandparent directory as a potential root
            # e.g. if /path/to/project/target/somefile.jar, then /path/to/project is root
            potential_build_roots.add(str(parent_dir.parent.resolve()))

    # Refinement of potential_build_roots:
    # Sort by length to process shorter paths first (e.g., /a before /a/b)
    sorted_roots = sorted(list(potential_build_roots), key=len)
    final_build_roots: set[str] = set()

    for current_root_str in sorted_roots:
        is_subpath = False
        # Check if current_root_str is a subpath of any path already in final_build_roots
        for final_root_str in final_build_roots:
            if current_root_str.startswith(final_root_str + os.sep):
                is_subpath = True
                break
        if not is_subpath:
            final_build_roots.add(current_root_str)

    logger.info(f"Refined {len(final_build_roots)} potential build roots: {final_build_roots}")

    for build_root_path_str in final_build_roots:
        try:
            # Check if build path already exists to avoid duplicates if script is re-run
            # This check should ideally be more robust, perhaps by path and other identifiers.
            existing_build = db_session.query(db_models.Build).filter_by(path=build_root_path_str).first()
            if existing_build:
                logger.info(f"Build path {build_root_path_str} already exists in DB with ID {existing_build.id}. Skipping creation.")
                detected_builds.append((build_root_path_str, existing_build.id))
                continue

            db_build = db_models.Build(path=build_root_path_str)
            db_session.add(db_build)
            db_session.commit()
            db_session.refresh(db_build)
            detected_builds.append((build_root_path_str, db_build.id))
            logger.info(f"Detected and recorded new build folder: {build_root_path_str} (ID: {db_build.id})")
        except Exception as e:
            db_session.rollback()
            logger.error(f"Error creating Build record for path {build_root_path_str}: {e}")

    logger.info(f"Total detected and recorded builds: {len(detected_builds)}")
    return detected_builds

if __name__ == '__main__':
    from database.database_session import SessionLocal, init_db

    logger.info("Running build_detector.py directly for testing.")

    # Initialize DB (ensure tables are created, including Build table)
    # This requires DATABASE_URL to be set in .env
    try:
        init_db()
        logger.info("Database initialized/checked.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}. Ensure DATABASE_URL is correct in .env and DB is running.")
        exit(1)

    # Create a dummy session
    session = SessionLocal() # type: ignore

    # Example file paths (simulate output from scanner.py)
    # These should be absolute paths in a real scenario, but for testing, relative can work if cwd is project root.
    # Making them absolute for robustness in test:
    test_project_root = pathlib.Path("test_build_detector_project").resolve()

    mock_files_structure = {
        "project1_py": ["setup.py", "src/main.py", "requirements.txt", "build/lib/module.py"],
        "project2_java": ["pom.xml", "src/main/java/App.java", "target/app.jar"],
        "project3_js": ["package.json", "node_modules/lib/index.js", "dist/bundle.js"],
        "project4_django": ["manage.py", "my_app/settings.py", "my_app/views.py"],
        "project5_simple_git": [".git/config", "README.md"],
        "project6_nested": ["outer_project_file.txt", "inner_project/setup.py", "inner_project/src/code.py"]
    }

    all_test_files: list[str] = []

    for project_name, files in mock_files_structure.items():
        project_base_path = test_project_root / project_name
        for file_rel_path in files:
            full_file_path = project_base_path / file_rel_path
            # Create dummy files and directories
            full_file_path.parent.mkdir(parents=True, exist_ok=True)
            if file_rel_path.endswith('/'): # It's a directory marker like .git/
                 full_file_path.mkdir(parents=True, exist_ok=True)
            elif not full_file_path.exists(): # Avoid re-writing if already exists
                with open(full_file_path, "w") as f:
                    f.write(f"content of {file_rel_path}")
            all_test_files.append(str(full_file_path))

    logger.info(f"Created {len(all_test_files)} mock files for testing.")

    detected = identify_build_folders(session, all_test_files)
    print("\nDetected build folders (path, id):")
    for path, build_id in detected:
        print(f"- {path} (Build ID: {build_id})")

    # Expected roots (paths will be absolute):
    # test_build_detector_project/project1_py
    # test_build_detector_project/project2_java
    # test_build_detector_project/project3_js
    # test_build_detector_project/project4_django
    # test_build_detector_project/project5_simple_git
    # test_build_detector_project/project6_nested/inner_project
    # (project6_nested itself might be detected if outer_project_file.txt was a root marker, but it's not)

    # Clean up session
    session.close()
    logger.info("Build detector test run finished. Check logs and DB for results.")

    # Optional: Clean up test files (be careful with rmtree)
    # import shutil
    # if test_project_root.exists():
    #     logger.info(f"Cleaning up test directory: {test_project_root}")
    #     # shutil.rmtree(test_project_root)

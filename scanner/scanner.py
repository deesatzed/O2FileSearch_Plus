import os
import pathlib
import logging
from utils.file_ops import should_skip_directory

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def scan_directories(base_paths: list[str]) -> list[str]:
    """
    Scans specified base paths recursively and returns a list of all file paths found.
    Skips directories specified in utils.file_ops.should_skip_directory.
    """
    all_file_paths: list[str] = []
    total_files_found = 0

    for base_path in base_paths:
        files_found_in_base_path = 0
        logger.info(f"Scanning directory: {base_path}")
        # Ensure base_path is a string and an absolute path
        abs_base_path = str(pathlib.Path(base_path).resolve())

        if not os.path.isdir(abs_base_path):
            logger.warning(f"Base path {abs_base_path} is not a directory or does not exist. Skipping.")
            continue

        for root, dirs, files in os.walk(abs_base_path, topdown=True):
            # Prune directories to skip
            # Modifying dirs[:] in place is required by os.walk
            dirs[:] = [d for d in dirs if not should_skip_directory(os.path.join(root, d))]

            for file_name in files:
                file_path = os.path.join(root, file_name)
                # Optionally, add checks here if a file should be skipped based on its properties
                # For example, os.path.islink(file_path) if we want to handle links differently here
                all_file_paths.append(file_path)
                files_found_in_base_path += 1

        logger.info(f"Found {files_found_in_base_path} files in {base_path}")
        total_files_found += files_found_in_base_path

    logger.info(f"Total files found across all paths: {total_files_found}")
    return all_file_paths

if __name__ == '__main__':
    # Example usage:
    # Create some dummy directories and files for testing
    if not os.path.exists("test_scan_dir"):
        os.makedirs("test_scan_dir/subdir1")
        os.makedirs("test_scan_dir/.git") # Should be skipped
        os.makedirs("test_scan_dir/node_modules") # Should be skipped

    with open("test_scan_dir/file1.txt", "w") as f: f.write("test")
    with open("test_scan_dir/subdir1/file2.py", "w") as f: f.write("print('hello')")
    with open("test_scan_dir/.git/config", "w") as f: f.write("git stuff")
    with open("test_scan_dir/node_modules/module.js", "w") as f: f.write("js stuff")

    # Test with a relative path that exists
    paths_to_scan = ["./test_scan_dir", "./non_existent_dir"]
    found_files = scan_directories(paths_to_scan)
    print("\nFound files:")
    for f_path in found_files:
        print(f_path)

    # Expected: file1.txt and subdir1/file2.py (paths will be absolute)
    # Clean up dummy directories and files
    # import shutil
    # shutil.rmtree("test_scan_dir")
    print(f"\nNote: .git and node_modules subdirectories and their contents should have been skipped.")
    print(f"A warning for './non_existent_dir' should have been logged.")

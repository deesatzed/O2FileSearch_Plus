import os
import logging
import openai # Official OpenAI library
from dotenv import load_dotenv

# Assuming utils.file_ops is in the parent directory of openai_client, then parent of utils
# Adjust path if utils is structured differently relative to openai_client
# For a flat structure where utils and openai_client are siblings under a common root:
try:
    from utils.file_ops import extract_text_content, is_text_file
except ModuleNotFoundError:
    # Fallback for cases where the script might be run with different Python paths
    # This assumes 'utils' is in a path discoverable by Python, potentially via PYTHONPATH
    # Or if the project root is added to sys.path elsewhere.
    # For robust imports, especially in larger projects, consider using relative imports
    # if 'utils' and 'openai_client' are part of the same package, or absolute imports
    # if the project is installed or PYTHONPATH is set up.
    # Example: from ..utils.file_ops import ... (if part of a package)
    # For now, direct import assumes 'utils' is findable.
    logging.warning("Could not import from utils.file_ops directly. Ensure PYTHONPATH is set or project structure allows this.")
    # As a simple fallback for this script, if you know the structure:
    import sys
    # Assuming the script is in /openai_client and utils is in /utils at the same level as openai_client's parent
    # This is a common structure. If utils is a sibling of openai_client, this needs adjustment.
    # Example: if project_root/openai_client/client.py and project_root/utils/file_ops.py
    # sys.path.append(os.path.join(os.path.dirname(__file__), '..')) # Add parent dir to path
    # from utils.file_ops import extract_text_content, is_text_file

    # Correcting path addition based on typical project structure:
    # If this script is at /app/openai_client/client.py and utils is at /app/utils/file_ops.py
    # Then the /app directory (parent of openai_client) should be in sys.path.
    # If running from /app, `import utils.file_ops` should work.
    # If running from /app/openai_client, then `from ..utils.file_ops` (if packages) or add /app to path.
    # For now, relying on PYTHONPATH or that the calling context has /app in its path.
    # The provided solution structure seems to imply utils and openai_client are top-level or near top-level.
    from utils.file_ops import extract_text_content, is_text_file # Retry after path adjustment if made


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Load environment variables from .env file in the project root
# Assumes .env is in the parent directory of openai_client/
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)
# Alternatively, can just call load_dotenv() if .env is in current working dir or project root
# and python-dotenv can find it. For robustness, specifying path is good.

# Initialize the OpenAI client globally or within functions as preferred.
# Global initialization can reuse the client instance.
# Ensure API key is loaded before this line if client is initialized globally.
try:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not found in environment variables. OpenAI calls will fail.")
        # raise ValueError("OPENAI_API_KEY not set.") # Or handle as appropriate
    # The client will automatically pick up the OPENAI_API_KEY environment variable.
    client = openai.OpenAI()
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}")
    client = None # Ensure client is None if initialization fails

def get_embedding(content: str, model: str = "text-embedding-3-small") -> list[float] | None:
    """
    Generates an embedding for the given text content using the specified OpenAI model.
    """
    if not client:
        logger.error("OpenAI client is not initialized. Cannot get embedding.")
        return None
    if not content or not content.strip():
        logger.warning("Content for embedding is empty or whitespace. Skipping embedding.")
        return None

    # Log a snippet of the content
    content_snippet = content[:100].replace('\n', ' ') + "..." if len(content) > 100 else content.replace('\n', ' ')
    logger.info(f"Attempting to get embedding for content snippet: '{content_snippet}' using model {model}")

    try:
        response = client.embeddings.create(input=[content], model=model)
        embedding = response.data[0].embedding
        logger.info(f"Successfully generated embedding for content snippet (vector length: {len(embedding)}).")
        return embedding
    except openai.APIAuthenticationError as e:
        logger.error(f"OpenAI API Authentication Error: {e}. Check your API key and organization.")
        return None
    except openai.RateLimitError as e:
        logger.error(f"OpenAI API Rate Limit Exceeded: {e}. Please check your plan and usage.")
        return None
    except openai.APIConnectionError as e:
        logger.error(f"OpenAI API Connection Error: {e}. Could not connect to OpenAI API.")
        return None
    except openai.APIError as e: # Catch other OpenAI API errors
        logger.error(f"OpenAI API Error: {e}")
        return None
    except Exception as e: # Catch any other unexpected errors
        logger.error(f"An unexpected error occurred while generating embedding: {e}")
        return None

def get_embedding_for_file(file_path: str, model: str = "text-embedding-3-small") -> list[float] | None:
    """
    Checks if a file is a text file, extracts its content, and generates an embedding.
    """
    logger.info(f"Attempting to generate embedding for file: {file_path}")

    if not is_text_file(file_path):
        logger.info(f"File {file_path} is not a text file. Skipping embedding generation.")
        return None

    content = extract_text_content(file_path)
    if not content:
        logger.info(f"No content extracted from {file_path} or content is empty. Skipping embedding generation.")
        return None

    # Content can be very large, OpenAI has token limits (e.g., 8191 for text-embedding-3-small)
    # Truncation might be needed here if content routinely exceeds model limits.
    # For now, assuming content fits or specific truncation strategies will be added later if errors occur.
    # A simple truncation:
    # max_tokens = 8000 # Roughly, as tokenization varies. One token is ~4 chars.
    # if len(content) > max_tokens * 3: # Heuristic: 3 chars per token on average
    #     logger.warning(f"Content from {file_path} is very long ({len(content)} chars). Truncating for embedding.")
    #     content = content[:max_tokens * 3]

    return get_embedding(content, model=model)

if __name__ == '__main__':
    logger.info("Running openai_client.py directly for testing.")

    if not OPENAI_API_KEY:
        print("OPENAI_API_KEY is not set in your .env file or environment variables.")
        print("Please set it to run the OpenAI client tests.")
    else:
        print(f"Using OpenAI API Key (last 5 chars): ...{OPENAI_API_KEY[-5:]}")

        # Test get_embedding with sample text
        sample_text = "This is a sample text content for testing the OpenAI embedding generation."
        print(f"\nTesting get_embedding with sample text: '{sample_text}'")
        embedding_vector = get_embedding(sample_text)
        if embedding_vector:
            print(f"Successfully received embedding vector. Length: {len(embedding_vector)}")
            # print(f"First 5 elements: {embedding_vector[:5]}")
        else:
            print("Failed to get embedding for sample text.")

        # Test get_embedding_for_file with a dummy text file
        dummy_file_path = "test_openai_dummy_file.txt"
        print(f"\nTesting get_embedding_for_file with dummy file: '{dummy_file_path}'")
        with open(dummy_file_path, "w") as f:
            f.write("This is content inside a dummy text file.\nIt has multiple lines.")

        file_embedding_vector = get_embedding_for_file(dummy_file_path)
        if file_embedding_vector:
            print(f"Successfully received embedding for dummy file. Length: {len(file_embedding_vector)}")
            # print(f"First 5 elements: {file_embedding_vector[:5]}")
        else:
            print(f"Failed to get embedding for dummy file '{dummy_file_path}'.")

        # Clean up dummy file
        try:
            os.remove(dummy_file_path)
            print(f"\nCleaned up dummy file: {dummy_file_path}")
        except OSError as e:
            print(f"Error removing dummy file {dummy_file_path}: {e}")

    logger.info("OpenAI client test run finished.")

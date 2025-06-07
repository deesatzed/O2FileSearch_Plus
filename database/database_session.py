import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
import logging

# Import Base from your models file
from database.models import Base

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Load environment variables from .env file
# This is useful for local development. In production, variables might be set directly.
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env') # Assuming .env is in project root
load_dotenv(dotenv_path=dotenv_path)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable not set.")
    # You could raise an error here or set a default for local dev,
    # but for now, we'll let it fail later if it's not set.
    # raise ValueError("DATABASE_URL environment variable not set.")

# Create SQLAlchemy engine
# The `connect_args` can be used for SSL or other connection parameters if needed.
# Example for SSL: connect_args={"sslmode": "require"}
try:
    engine = create_engine(DATABASE_URL)
except Exception as e:
    logger.error(f"Failed to create SQLAlchemy engine: {e}")
    # Handle error appropriately, maybe exit or raise
    raise

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """
    Initializes the database by creating all tables defined in models.
    It also ensures the 'vector' extension is enabled in PostgreSQL.
    """
    if not DATABASE_URL:
        logger.error("Cannot initialize database: DATABASE_URL is not set.")
        return

    try:
        logger.info("Initializing database and creating tables...")
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Tables created successfully (if they didn't exist).")

        # Enable pgvector extension
        with engine.connect() as connection:
            try:
                connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                connection.commit() # Make sure to commit DDL if connection is not in autocommit mode for DDL
                logger.info("pgvector extension 'vector' ensured.")
            except OperationalError as oe:
                # This might happen if the user doesn't have superuser privileges
                # or if the extension is already created by another means (e.g. Alembic)
                # and there's a conflict or issue.
                logger.warning(f"Could not execute CREATE EXTENSION vector: {oe}. "
                               "This might be okay if the extension is already enabled "
                               "or if you lack privileges. Check your DB setup.")
                # Depending on policy, you might want to rollback or handle differently.
                # For now, we log a warning and proceed.
                connection.rollback() # Rollback the transaction if extension creation failed
            except Exception as e:
                logger.error(f"An unexpected error occurred while trying to enable 'vector' extension: {e}")
                connection.rollback() # Rollback on other errors too
                # Potentially re-raise or handle as critical failure
                raise

        logger.info("Database initialization process complete.")

    except OperationalError as oe:
        logger.error(f"Operational error during database initialization: {oe}")
        logger.error("Please check your database connection string, server status, and user privileges.")
    except Exception as e:
        logger.error(f"An error occurred during database initialization: {e}")
        # Depending on the application's needs, you might want to re-raise the exception
        # raise

# Example of how to get a DB session (dependency for FastAPI or other parts of the app)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == "__main__":
    # This section is for direct execution, e.g., for setting up the DB manually.
    logger.info("Running database_session.py directly.")

    if not DATABASE_URL:
        print("DATABASE_URL is not set in your .env file or environment variables.")
        print("Please create a .env file in the project root with:")
        print("DATABASE_URL=postgresql://user:password@host:port/database")
    else:
        print(f"Attempting to initialize database at: {DATABASE_URL.split('@')[-1]}") # Mask credentials
        # A simple check to see if the DB is reachable
        try:
            with engine.connect() as connection:
                print("Successfully connected to the database.")
            # Initialize the database
            init_db()
            print("Database initialization script finished.")
        except OperationalError as e:
            print(f"Failed to connect or initialize the database: {e}")
            print("Please ensure your PostgreSQL server is running and accessible, and the DATABASE_URL is correct.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

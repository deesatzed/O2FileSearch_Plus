from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from pgvector.sqlalchemy import Vector # Assuming pgvector is installed

Base = declarative_base()

class Build(Base):
    __tablename__ = "builds"

    id = Column(Integer, primary_key=True, index=True)
    path = Column(String, nullable=False, index=True)
    tag = Column(String, nullable=True)
    group_id = Column(String, nullable=True, index=True)

    files = relationship("File", back_populates="build")

class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    path = Column(String, unique=True, nullable=False, index=True) # Assuming path is unique
    filename = Column(String, nullable=False, index=True)
    hash = Column(String, nullable=False) # SHA256 hash
    size_bytes = Column(Integer, nullable=False)
    is_symlink = Column(Boolean, default=False)

    build_id = Column(Integer, ForeignKey("builds.id"), nullable=True)
    build = relationship("Build", back_populates="files")

    # Index on hash for faster lookups
    __table_args__ = (Index("idx_file_hash", "hash"),)

class Embedding(Base):
    __tablename__ = "embeddings"

    file_id = Column(Integer, ForeignKey("files.id"), primary_key=True)
    embedding = Column(Vector(1536)) # Assuming embedding dimension is 1536
    closest_file_id = Column(Integer, ForeignKey("files.id"), nullable=True)
    similarity_score = Column(Float, nullable=True)

    file = relationship("File") # Basic relationship to owning File
    # If we want a relationship to the closest_file, it would be:
    # closest_file = relationship("File", foreign_keys=[closest_file_id])


    __table_args__ = (
        Index(
            'idx_embedding_cos',
            embedding,
            postgresql_using='hnsw',
            postgresql_with={'m': 16, 'ef_construction': 64},
            postgresql_ops={'embedding': 'vector_cosine_ops'}
        ),
    )

from pydantic import BaseModel
from typing import List, Optional
# pgvector.sqlalchemy will be used in models.py, for Pydantic we might need a custom type or use List[float]
# For now, let's represent embedding as List[float] in Pydantic if direct pgvector type is not straightforward.
# However, pgvector library itself might offer Pydantic integration, let's assume List[float] for now.

class FileBase(BaseModel):
    path: str
    filename: str
    hash: str # SHA256
    size_bytes: int
    is_symlink: bool
    build_id: Optional[int] = None

class FileCreate(FileBase):
    pass

class File(FileBase):
    id: int

    class Config:
        orm_mode = True # Pydantic V2 uses from_attributes = True
        # from_attributes = True # For Pydantic V2

class BuildBase(BaseModel):
    path: str
    tag: Optional[str] = None
    group_id: Optional[str] = None

class BuildCreate(BuildBase):
    pass

class Build(BuildBase):
    id: int

    class Config:
        orm_mode = True
        # from_attributes = True # For Pydantic V2

class EmbeddingBase(BaseModel):
    # file_id is part of the path for creation via API, or derived from context
    # For direct creation, it might be needed. Let's assume it's part of the data.
    file_id: int
    embedding: List[float] # Representing pgvector.sqlalchemy.Vector as List[float]
    closest_file_id: Optional[int] = None
    similarity_score: Optional[float] = None

class EmbeddingCreate(EmbeddingBase):
    pass

class Embedding(EmbeddingBase):
    # In the model, file_id is PK, so it's always present.
    # If we add a separate surrogate PK 'id' to Embedding table, then include it here.
    # For now, sticking to file_id as PK as per instructions.

    class Config:
        orm_mode = True
        # from_attributes = True # For Pydantic V2

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    doc_type: str
    file_format: str
    status: str
    created_at: datetime


class DocumentGenerateRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=5_000)

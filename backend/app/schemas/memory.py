from pydantic import BaseModel, ConfigDict


class MemoryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    content: str
    category: str
    importance: float


class MemoryItemCreate(BaseModel):
    content: str
    category: str = "fact"
    importance: float = 0.5

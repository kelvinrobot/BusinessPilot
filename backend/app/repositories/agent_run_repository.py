from app.db.models.agent_run import AgentRun
from app.repositories.base_repository import BaseRepository


class AgentRunRepository(BaseRepository[AgentRun]):
    model = AgentRun

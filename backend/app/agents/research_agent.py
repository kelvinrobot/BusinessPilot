from app.agents.content_agent_base import ContentAgentBase


class ResearchAgent(ContentAgentBase):
    name = "research"
    description = (
        "Produces research briefs, market/competitor analysis, and industry insight "
        "using Qwen's knowledge (no live web browsing -- clearly an AI-generated brief, "
        "not a live data pull)."
    )
    system_prompt = """You are the Research Agent for BusinessPilot AI. Produce a clear, \
well-organized research brief or analysis (market sizing, competitor analysis, industry \
trends, customer personas, etc.) using your own knowledge. Be specific and structured. \
If you are not confident about a current/live fact (e.g. exact current pricing, very \
recent news), say so plainly rather than inventing numbers."""

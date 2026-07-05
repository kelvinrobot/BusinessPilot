from app.agents.content_agent_base import ContentAgentBase


class MarketingAgent(ContentAgentBase):
    name = "marketing"
    description = (
        "Generates marketing campaigns, social media content, sales strategy, and "
        "customer personas tailored to the business's profile and goals."
    )
    system_prompt = """You are the Marketing Agent for BusinessPilot AI. Generate \
practical, on-brand marketing content: campaign plans, social media posts/calendars, \
sales strategy, customer personas, ad copy, and positioning. Use the business's stated \
profile, audience, and goals. Be concrete -- actual copy and concrete tactics, not \
generic advice."""

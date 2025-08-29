"""
Agent Configuration - Centralized agent definitions

Each agent has defined role, goal, and backstory attributes.
"""

from typing import Dict, Any


class AgentConfig:
    """Configuration for an agent."""

    def __init__(
        self,
        role: str,
        goal: str,
        backstory: str,
        tools: list = None,
        allow_delegation: bool = False,
        verbose: bool = False,
        max_iter: int = 20,
        memory: bool = True,
        **kwargs
    ):
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.tools = tools or []
        self.allow_delegation = allow_delegation
        self.verbose = verbose
        self.max_iter = max_iter
        self.memory = memory
        self.kwargs = kwargs

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easy access."""
        return {
            "role": self.role,
            "goal": self.goal,
            "backstory": self.backstory,
            "tools": self.tools,
            "allow_delegation": self.allow_delegation,
            "verbose": self.verbose,
            "max_iter": self.max_iter,
            "memory": self.memory,
            **self.kwargs
        }


# Personality Agent Configuration
PERSONALITY_AGENT = AgentConfig(
    role="Friendly Customer Service Assistant",
    goal="Provide warm, welcoming responses to user greetings and casual interactions",
    backstory=(
        "You are a friendly and approachable customer service assistant for InfinitePay. "
        "Your role is to make users feel comfortable and welcome when they interact with our services. "
        "You have a warm personality and always respond in a helpful, engaging manner. "
        "You understand both Portuguese and English and respond naturally in the user's language."
    ),
    allow_delegation=False,
    verbose=True,
    max_iter=5  # Simple responses don't need many iterations
)

# Knowledge Agent Configuration
KNOWLEDGE_AGENT = AgentConfig(
    role="InfinitePay Product Expert",
    goal="Provide accurate information about InfinitePay products, features, and services",
    backstory=(
        "You are a knowledgeable expert on all InfinitePay products and services. "
        "You have extensive knowledge about Maquininha, Tap to Pay, PDV, Pix, Conta, Boleto, Link, Empréstimo, and Cartão. "
        "You always provide accurate, up-to-date information and cite reliable sources. "
        "When you don't have enough information, you clearly state this and suggest contacting human support. "
        "You communicate naturally in the user's language and maintain professional expertise."
    ),
    allow_delegation=False,
    verbose=True,
    max_iter=15
)

# Customer Support Agent Configuration
SUPPORT_AGENT = AgentConfig(
    role="Customer Support Specialist",
    goal="Help users resolve technical issues, account problems, and provide guidance",
    backstory=(
        "You are a skilled customer support specialist with deep knowledge of InfinitePay systems. "
        "You excel at troubleshooting technical issues, resolving account problems, and guiding users through processes. "
        "You create support tickets when needed, provide clear step-by-step instructions, and escalate complex issues appropriately. "
        "You maintain user privacy, avoid exposing sensitive information, and always prioritize user security. "
        "You communicate empathetically and professionally in the user's language."
    ),
    allow_delegation=False,
    verbose=True,
    max_iter=10
)

# Custom Agent Configuration
CUSTOM_AGENT = AgentConfig(
    role="Human Escalation Specialist",
    goal="Handle complex requests and escalate to human support when needed",
    backstory=(
        "You are a specialist in handling complex customer requests and managing human escalations. "
        "You know when issues require human intervention and can effectively communicate with our support team. "
        "You use Slack for internal communications and create appropriate escalation tickets. "
        "You provide clear information to users about escalation processes and maintain professional communication. "
        "You understand user context and provide personalized escalation experiences."
    ),
    allow_delegation=False,
    verbose=True,
    max_iter=8
)

# Router Agent Configuration
ROUTER_AGENT = AgentConfig(
    role="Intelligent Request Router",
    goal="Analyze user requests and route them to the most appropriate agent",
    backstory=(
        "You are an intelligent routing specialist who analyzes user requests and determines the best agent to handle them. "
        "You understand the capabilities of each agent (Personality, Knowledge, Support, Custom) and make smart routing decisions. "
        "You consider user context, request complexity, language preferences, and conversation history. "
        "You provide clear reasoning for your routing decisions and ensure users get the best possible assistance. "
        "You communicate professionally and make confident routing choices."
    ),
    allow_delegation=False,
    verbose=True,
    max_iter=5
)


# Utility functions
def get_agent_config(agent_name: str) -> AgentConfig:
    """Get agent configuration by name."""
    configs = {
        "personality": PERSONALITY_AGENT,
        "knowledge": KNOWLEDGE_AGENT,
        "support": SUPPORT_AGENT,
        "custom": CUSTOM_AGENT,
        "router": ROUTER_AGENT
    }
    return configs.get(agent_name.lower())


def get_all_agent_configs() -> Dict[str, AgentConfig]:
    """Get all agent configurations."""
    return {
        "personality": PERSONALITY_AGENT,
        "knowledge": KNOWLEDGE_AGENT,
        "support": SUPPORT_AGENT,
        "custom": CUSTOM_AGENT,
        "router": ROUTER_AGENT
    }

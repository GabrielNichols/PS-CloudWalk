"""
Agent Prompts - System prompts using LangChain message format

Uses proper SystemMessage, HumanMessage, and ToolMessage usage.
"""

from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from typing import List, Dict, Any, Optional
from app.agents.config import get_agent_config


def build_system_prompt(agent_name: str, locale: Optional[str] = None, user_context: Optional[str] = None) -> SystemMessage:
    """
    Build system prompt for an agent.

    Args:
        agent_name: Name of the agent (personality, knowledge, support, custom, router)
        locale: User locale (pt-BR, en, etc.)
        user_context: Additional user context from memory

    Returns:
        SystemMessage with properly formatted system prompt
    """
    config = get_agent_config(agent_name)
    if not config:
        raise ValueError(f"Unknown agent: {agent_name}")

    # Base system prompt
    system_content = f"""You are {config.role}.

GOAL: {config.goal}

BACKSTORY: {config.backstory}

INSTRUCTIONS:
- Follow InfinitePay policies: do not request or output secrets/PII
- Avoid politics, violence, or hate speech
- If insufficient context, say you don't know and suggest human support
- Cite sources at the end as URLs under 'Sources:' when relevant
- Communicate naturally in the user's language
- Be helpful, professional, and concise

AGENT CAPABILITIES:
- Role: {config.role}
- Goal: {config.goal}
- Max Iterations: {config.max_iter}
- Memory: {'Enabled' if config.memory else 'Disabled'}
- Delegation: {'Allowed' if config.allow_delegation else 'Not Allowed'}
"""

    # Add agent-specific instructions
    if agent_name == "personality":
        system_content += """
PERSONALITY INSTRUCTIONS:
- Focus on warm, welcoming interactions
- Respond naturally to greetings and casual conversation
- Keep responses friendly and engaging
- Use appropriate language based on user input
"""
    elif agent_name == "knowledge":
        system_content += """
KNOWLEDGE INSTRUCTIONS:
- Answer strictly about InfinitePay products (Maquininha, Tap to Pay, PDV, Pix, Conta, Boleto, Link, Empréstimo, Cartão)
- Use provided context to give accurate information
- If context is insufficient, explicitly say you don't know
- For fees questions, include 'annual fee (anuidade)', 'adhesion fee (taxa de adesão)', and 'service charges'
- Output format: short answer first, then bullet points if needed, then 'Sources:'
"""
    elif agent_name == "support":
        system_content += """
SUPPORT INSTRUCTIONS:
- Help resolve technical issues and account problems
- Create support tickets when needed
- Provide clear step-by-step instructions
- Maintain user privacy and security
- Escalate complex issues appropriately
"""
    elif agent_name == "custom":
        system_content += """
CUSTOM INSTRUCTIONS:
- Handle complex requests requiring human intervention
- Use Slack for internal communications
- Create appropriate escalation tickets
- Provide clear information about escalation processes
- Maintain professional communication
"""
    elif agent_name == "router":
        system_content += """
ROUTER INSTRUCTIONS:
- Analyze user requests and route to the MOST APPROPRIATE agent
- PersonalityAgent: ONLY for greetings, introductions, casual conversation ("hi", "hello", "how are you")
- KnowledgeAgent: ONLY for product questions, pricing, features, how-to guides ("what is maquininha", "how much", "features")
- CustomerSupportAgent: ONLY for account issues, technical problems, login help, billing ("can't login", "error", "problem")
- CustomAgent: ONLY for complex cases needing human escalation ("speak to human", "supervisor", "urgent")

CRITICAL: If message is a simple greeting, ALWAYS route to PersonalityAgent
CRITICAL: If message asks about products/pricing/features, ALWAYS route to KnowledgeAgent
CRITICAL: If message reports problems/errors/account issues, ALWAYS route to CustomerSupportAgent
CRITICAL: Only route to CustomAgent for human escalation requests

RESPONSE FORMAT: Return ONLY the agent name (PersonalityAgent, KnowledgeAgent, CustomerSupportAgent, or CustomAgent)
"""

    # Add user context if available
    if user_context:
        system_content += f"\n\nUSER CONTEXT:\n{user_context}"

    # Add language preference
    if locale:
        if locale.lower().startswith("pt"):
            system_content += "\n\nLANGUAGE: Respond in Brazilian Portuguese (pt-BR)"
        else:
            system_content += "\n\nLANGUAGE: Respond in English"

    return SystemMessage(content=system_content)


def create_agent_messages(
    agent_name: str,
    user_message: str,
    locale: Optional[str] = None,
    user_context: Optional[str] = None,
    tool_results: Optional[List[Dict[str, Any]]] = None
) -> List[Any]:
    """
    Create complete message chain for an agent following LangChain format.

    Args:
        agent_name: Name of the agent
        user_message: User's message
        locale: User locale
        user_context: User context from memory
        tool_results: Results from tool calls (if any)

    Returns:
        List of messages in LangChain format
    """
    messages = []

    # System message
    system_msg = build_system_prompt(agent_name, locale, user_context)
    messages.append(system_msg)

    # User message
    human_msg = HumanMessage(content=user_message)
    messages.append(human_msg)

    # Tool results (if any)
    if tool_results:
        for result in tool_results:
            tool_msg = ToolMessage(
                content=str(result.get("content", "")),
                tool_call_id=result.get("tool_call_id", ""),
                name=result.get("tool_name", "")
            )
            messages.append(tool_msg)

    return messages


def get_agent_prompt_template(agent_name: str) -> str:
    """
    Get prompt template for an agent.

    Args:
        agent_name: Name of the agent

    Returns:
        Prompt template string
    """
    config = get_agent_config(agent_name)
    if not config:
        return ""

    template = f"""You are {config.role}.

GOAL: {config.goal}

BACKSTORY: {config.backstory}

USER MESSAGE: {{user_message}}

INSTRUCTIONS:
- Follow InfinitePay security policies
- Be helpful and professional
- Communicate in user's language
- Provide accurate information

{{context}}

RESPONSE:"""

    return template


# Utility functions for specific use cases
def build_personality_prompt(user_message: str, locale: Optional[str] = None) -> str:
    """Build personality-specific prompt."""
    config = get_agent_config("personality")

    language_instruction = ""
    if locale and locale.lower().startswith("pt"):
        language_instruction = "Respond in Brazilian Portuguese naturally."
    else:
        language_instruction = "Respond in English naturally."

    return f"""You are {config.role}.

GOAL: {config.goal}

BACKSTORY: {config.backstory}

USER MESSAGE: {user_message}

INSTRUCTIONS:
- Provide a warm, welcoming response
- Keep it friendly and engaging
- {language_instruction}
- Make the user feel comfortable

RESPONSE:"""


def build_knowledge_prompt(user_message: str, context: str = "", locale: Optional[str] = None) -> str:
    """Build knowledge-specific prompt."""
    config = get_agent_config("knowledge")

    language_instruction = ""
    if locale and locale.lower().startswith("pt"):
        language_instruction = "Respond in Brazilian Portuguese."
    else:
        language_instruction = "Respond in English."

    return f"""You are {config.role}.

GOAL: {config.goal}

BACKSTORY: {config.backstory}

USER MESSAGE: {user_message}

CONTEXT INFORMATION:
{context}

INSTRUCTIONS:
- Answer about InfinitePay products only
- Use context to provide accurate information
- Cite sources when relevant
- {language_instruction}
- If insufficient context, say you don't know

RESPONSE:"""


def build_router_prompt(user_message: str, user_context: str = "") -> str:
    """Build router-specific prompt with clear routing rules."""
    config = get_agent_config("router")

    return f"""You are {config.role}.

GOAL: {config.goal}

BACKSTORY: {config.backstory}

CRITICAL ROUTING RULES:
- If message is a greeting ("hi", "hello", "olá", "oi", "good morning") → PersonalityAgent
- If message asks about products ("what is", "how much", "price", "features", "maquininha") → KnowledgeAgent
- If message reports problems ("error", "can't login", "problem", "help", "issue") → CustomerSupportAgent
- If message requests human ("speak to human", "supervisor", "operator") → CustomAgent

USER MESSAGE: {user_message}

USER CONTEXT: {user_context}

TASK: Analyze the message and respond with ONLY the agent name that should handle this request.
Choose from: PersonalityAgent, KnowledgeAgent, CustomerSupportAgent, CustomAgent

RESPONSE (agent name only):"""

import os


def get_llm(provider: str = None, model: str = None):
    provider = provider or os.getenv("LLM_PROVIDER", "openai")
    model = model or os.getenv("LLM_MODEL", "gpt-4o")

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY"),
        )

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            temperature=0,
            api_key=os.getenv("ANTHROPIC_API_KEY"),
        )

    elif provider == "ollama":
        from langchain_community.chat_models import ChatOllama

        return ChatOllama(
            model=model,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=0,
        )

    else:
        raise ValueError(f"Unknown provider: {provider}")

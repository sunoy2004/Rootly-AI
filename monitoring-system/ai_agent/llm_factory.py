import os


def get_llm(model: str = None):
    """Groq LLM via LangChain (primary). Falls back to OpenAI-compatible API if configured."""
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    model = model or os.getenv("GROQ_MODEL") or os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=model,
            temperature=0,
            api_key=os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY"),
            timeout=60,
            max_retries=3,
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        temperature=0,
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        timeout=60,
        max_retries=3,
    )

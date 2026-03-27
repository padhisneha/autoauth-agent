import os


class Settings:
    app_name: str = "AutoAuth Agent"
    environment: str = "development"

    # LLM — using OpenAI gpt-4.5-mini
    openai_api_key: str = ""
    openai_model: str = "gpt-4.5-mini"

    # Legacy Anthropic support (optional)
    anthropic_api_key: str = ""

    database_url: str = "sqlite:///./autoauth.db"
    redis_url: str = "redis://localhost:6379"

    pinecone_api_key: str = ""
    pinecone_environment: str = "us-east-1"

    fhir_server_url: str = "http://localhost:3001/fhir"

    secret_key: str = "development-secret-key-change-in-production"

    demo_mode: bool = True
    mock_responses: bool = True

    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4.5-mini")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.pinecone_api_key = os.getenv("PINECONE_API_KEY", "")
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.demo_mode = os.getenv("DEMO_MODE", "true").lower() == "true"
        self.mock_responses = os.getenv("MOCK_RESPONSES", "true").lower() == "true"
        self.secret_key = os.getenv("SECRET_KEY", self.secret_key)


settings = Settings()
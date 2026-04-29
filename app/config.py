from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration — single source of truth."""

    # LLM & Embeddings
    OPENAI_API_KEY: str = ""
    LLM_MODEL_ANSWER: str = "gpt-4o"
    LLM_MODEL_GRADER: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Vector DB
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "documents"

    # Postgres
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/adv_rag"

    # Cache (Upstash)
    UPSTASH_REDIS_URL: str = ""
    UPSTASH_REDIS_TOKEN: str = ""
    CACHE_TTL_EMBEDDINGS: int = 604800
    CACHE_TTL_RAG: int = 3600
    CACHE_TTL_SQL_GEN: int = 86400
    CACHE_TTL_SQL_RESULT: int = 900
    CACHE_TTL_INTENT: int = 86400

    # Doc dedup
    STORAGE_BACKEND: str = "local"
    S3_CACHE_BUCKET: str = "adv-rag-cache"
    AWS_REGION: str = "us-east-1"

    # Web search
    TAVILY_API_KEY: str = ""

    # Auth
    JWT_SECRET: str = "change-me"
    JWT_EXPIRATION_MINUTES: int = 60

    # Rate limit + budget
    RATE_LIMIT_REQUESTS: int = 20
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    MAX_TOKENS_PER_USER_DAILY: int = 100000

    # Auth-route per-IP rate limits
    AUTH_LOGIN_RATE_LIMIT_PER_MIN: int = 5
    AUTH_REGISTER_RATE_LIMIT_PER_HOUR: int = 3

    # Input restructuring
    MAX_INPUT_TOKENS: int = 3000
    RESERVED_CONTEXT_TOKENS: int = 1000
    RESERVED_OUTPUT_TOKENS: int = 1000

    # Security thresholds
    PROMPT_INJECTION_THRESHOLD: float = 0.75
    TOXICITY_THRESHOLD: float = 0.75
    OUTPUT_TOXICITY_THRESHOLD: float = 0.5
    MAX_VALIDATION_RETRIES: int = 2

    # Retrieval defaults
    HYDE_NUM_HYPOTHESES: int = 3
    HYDE_ENABLED_BY_DEFAULT: bool = False
    HYBRID_SEARCH_ENABLED: bool = True
    RRF_K: int = 60
    RERANKER_BACKEND: str = "local"
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    VOYAGE_API_KEY: str = ""
    VOYAGE_MODEL: str = "rerank-2.5"
    RERANKER_INITIAL_TOP_K: int = 20
    RERANKING_ENABLED_BY_DEFAULT: bool = True
    CRAG_RELEVANCE_THRESHOLD: float = 0.7
    CRAG_AMBIGUOUS_THRESHOLD: float = 0.5
    CRAG_ENABLED_BY_DEFAULT: bool = True
    REFLECTION_MIN_SCORE: float = 0.8
    MAX_REFLECTION_RETRIES: int = 2
    SELF_REFLECTIVE_ENABLED_BY_DEFAULT: bool = False

    # Vanna
    VANNA_MODEL: str = "gpt-4o"
    VANNA_TEMPERATURE: float = 0.0
    VANNA_SEED: int = 42

    # Pending SQL query state
    PENDING_QUERY_TTL_SECONDS: int = 1800

    # Logging
    LOG_JSON: bool = False
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

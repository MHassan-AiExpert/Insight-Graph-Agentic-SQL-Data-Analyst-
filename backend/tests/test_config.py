from app.config import DEFAULT_DB_PATH, Settings


def test_defaults_are_safe(monkeypatch):
    for var in ("LLM_PROVIDER", "DATABASE_URL"):
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None, groq_api_key=None)
    assert s.llm_provider == "groq"
    assert s.groq_model == "llama-3.3-70b-versatile"
    assert s.max_sql_attempts == 3
    assert s.max_result_rows == 500
    assert s.query_timeout_seconds == 10.0
    assert s.database_url.endswith(str(DEFAULT_DB_PATH))


def test_environment_overrides(monkeypatch):
    monkeypatch.setenv("MAX_SQL_ATTEMPTS", "5")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-120b")
    s = Settings(_env_file=None)
    assert s.max_sql_attempts == 5
    assert s.groq_model == "openai/gpt-oss-120b"


def test_cors_origin_list_is_parsed():
    s = Settings(_env_file=None, cors_origins=" http://a.com, ,http://b.com ")
    assert s.cors_origin_list == ["http://a.com", "http://b.com"]


def test_business_rules_define_core_metrics():
    rules = Settings(_env_file=None).business_rules.lower()
    for term in ("revenue", "gross profit", "average order value", "quarters"):
        assert term in rules

"""Configuration validation tests."""
from config import LLMConfig


class TestProviderValidation:
    def test_all_provider_aliases_accepted(self):
        for provider in [
            "gemini", "openai", "anthropic", "claude",
            "zhipu", "glm", "muse", "meta", "openrouter",
        ]:
            assert LLMConfig(provider=provider).provider == provider

    def test_unknown_provider_defaults_to_gemini(self):
        assert LLMConfig(provider="does-not-exist").provider == "gemini"

    def test_provider_is_case_insensitive(self):
        assert LLMConfig(provider="Zhipu").provider == "zhipu"
        assert LLMConfig(provider="OPENROUTER").provider == "openrouter"


class TestModelDefaults:
    """Defaults must match the current model catalog (October 2026)."""

    def test_zhipu_default_is_glm_5_3(self):
        assert LLMConfig().zai_model == "glm-5.3"

    def test_openai_default_is_gpt_6_astra(self):
        assert LLMConfig().openai_model == "gpt-6-astra"

    def test_anthropic_default_is_claude_opus_5_5(self):
        assert LLMConfig().anthropic_model == "claude-opus-5-5"

    def test_gemini_default_is_4_argon(self):
        assert LLMConfig().gemini_model == "gemini-4-argon"

    def test_muse_default_is_spark_1_3_contributor(self):
        assert LLMConfig().muse_model == "muse-spark-1.3-contributor"

    def test_openrouter_default_is_glm_slug(self):
        assert LLMConfig().openrouter_model == "z-ai/glm-5.3"

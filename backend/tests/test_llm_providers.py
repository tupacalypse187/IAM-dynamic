"""Provider factory and missing-key behavior tests."""
import pytest

from llm_service import (
    get_llm_provider,
    GeminiProvider,
    OpenAIProvider,
    AnthropicProvider,
    ZhipuProvider,
    MuseProvider,
    OpenRouterProvider,
    FALLBACK_GUIDANCE,
)
from services.error_handler import UserFacingError


class TestFactory:
    @pytest.mark.parametrize("provider_type,expected_class", [
        ("gemini", GeminiProvider),
        ("openai", OpenAIProvider),
        ("anthropic", AnthropicProvider),
        ("claude", AnthropicProvider),
        ("zhipu", ZhipuProvider),
        ("glm", ZhipuProvider),
        ("muse", MuseProvider),
        ("meta", MuseProvider),
        ("openrouter", OpenRouterProvider),
    ])
    def test_provider_aliases(self, provider_type, expected_class):
        assert isinstance(get_llm_provider(provider_type), expected_class)

    def test_unknown_provider_falls_back_to_gemini(self):
        assert isinstance(get_llm_provider("nope"), GeminiProvider)

    def test_model_override(self):
        provider = get_llm_provider("zhipu", model="glm-4.7")
        assert provider.model_name == "glm-4.7"


class TestGatewayDefaults:
    def test_zhipu_uses_coding_endpoint(self):
        provider = ZhipuProvider()
        assert provider.base_url == "https://api.z.ai/api/coding/paas/v4/"
        assert provider.default_model == "glm-5.3"

    def test_muse_uses_meta_model_api(self):
        provider = MuseProvider()
        assert provider.base_url == "https://api.meta.ai/v1"
        assert provider.default_model == "muse-spark-1.3-contributor"

    def test_openrouter_uses_gateway(self):
        provider = OpenRouterProvider()
        assert provider.base_url == "https://openrouter.ai/api/v1"
        assert provider.default_model == "z-ai/glm-5.3"


class TestParameterCompatibility:
    """
    GPT-5 reasoning models reject temperature != 1 with a 400, and the
    OpenRouter gateway routes to vendors with mixed parameter support.
    """

    def test_openai_omits_temperature(self):
        assert OpenAIProvider.supports_temperature is False

    def test_openrouter_omits_temperature(self):
        assert OpenRouterProvider.supports_temperature is False

    def test_zhipu_and_muse_keep_temperature(self):
        assert ZhipuProvider.supports_temperature is True
        assert MuseProvider.supports_temperature is True


class TestMissingKeyBehavior:
    """
    No provider API keys are set in the test environment (see conftest),
    except OPENAI_API_KEY which may come from a local .env — so these
    tests only cover providers guaranteed to be key-less.
    """

    @pytest.mark.parametrize("provider_type", ["zhipu", "muse", "openrouter"])
    def test_generate_policy_raises_user_facing_error(self, provider_type):
        provider = get_llm_provider(provider_type)
        with pytest.raises(UserFacingError) as exc_info:
            provider.generate_policy("read-only access to a bucket")
        assert "API Key Missing" in exc_info.value.user_message

    @pytest.mark.parametrize("provider_type", ["zhipu", "muse", "openrouter"])
    def test_rejection_guidance_falls_back_instead_of_crashing(self, provider_type):
        """Regression: Zhipu used to raise AttributeError on a missing client."""
        provider = get_llm_provider(provider_type)
        result = provider.generate_rejection_guidance(
            "read all of s3", {"Statement": []}, "high"
        )
        assert result == FALLBACK_GUIDANCE

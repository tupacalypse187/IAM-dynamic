"""Integrity checks for the PROVIDER_MODELS catalog."""
from main import PROVIDER_MODELS

EXPECTED_PROVIDERS = {"gemini", "openai", "claude", "zhipu", "muse", "openrouter"}


class TestCatalogIntegrity:
    def test_all_providers_present(self):
        assert set(PROVIDER_MODELS) == EXPECTED_PROVIDERS

    def test_every_provider_has_models(self):
        for provider_id, models in PROVIDER_MODELS.items():
            assert len(models) > 0, f"{provider_id} has no models"

    def test_model_ids_unique_per_provider(self):
        for provider_id, models in PROVIDER_MODELS.items():
            ids = [m["id"] for m in models]
            assert len(ids) == len(set(ids)), f"duplicate ids in {provider_id}"

    def test_models_have_id_and_name(self):
        for provider_id, models in PROVIDER_MODELS.items():
            for model in models:
                assert set(model) == {"id", "name"}, f"bad entry in {provider_id}: {model}"
                assert model["id"].strip() and model["name"].strip()


class TestCurrentModels:
    def test_zhipu_has_glm_5_3_family(self):
        ids = [m["id"] for m in PROVIDER_MODELS["zhipu"]]
        assert "glm-5.3" in ids
        assert "glm-5.3-flash" in ids

    def test_openai_has_gpt_5_6_family(self):
        ids = [m["id"] for m in PROVIDER_MODELS["openai"]]
        assert "gpt-5.6" in ids
        assert "o1-preview" not in ids, "o1-preview is deprecated (removed Dec 2026)"

    def test_gemini_has_current_flash_models(self):
        ids = [m["id"] for m in PROVIDER_MODELS["gemini"]]
        assert "gemini-3.1-pro-preview" in ids
        assert "gemini-3.8-flash" in ids
        assert "gemini-3.1-flash-lite-preview" not in ids, "model was shut down"

    def test_claude_has_generation_5(self):
        ids = [m["id"] for m in PROVIDER_MODELS["claude"]]
        assert "claude-opus-5" in ids
        assert "claude-sonnet-5" in ids

    def test_muse_has_contributor_and_standard(self):
        ids = [m["id"] for m in PROVIDER_MODELS["muse"]]
        assert "muse-spark-1.3-contributor" in ids
        assert "muse-spark-1.3" in ids

    def test_openrouter_slugs_are_vendor_slash_model(self):
        for model in PROVIDER_MODELS["openrouter"]:
            assert "/" in model["id"], f"OpenRouter slug missing vendor prefix: {model['id']}"

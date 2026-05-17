#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

from unittest.mock import MagicMock, patch

from rag.llm.embedding_model import Base, GeminiEmbed, GoogleEmbed


class TestMaxBatchSizeAttribute:
    def test_base_default_is_16(self):
        assert Base.max_batch_size == 16

    def test_gemini_overrides_to_100(self):
        assert GeminiEmbed.max_batch_size == 100

    def test_google_overrides_to_250(self):
        assert GoogleEmbed.max_batch_size == 250


def _make_gemini_response(n: int, dim: int = 8):
    resp = MagicMock()
    resp.embeddings = [MagicMock(values=[0.1] * dim) for _ in range(n)]
    return resp


class TestGeminiBatching:
    @patch.object(GeminiEmbed, "__init__", return_value=None)
    def test_single_api_call_for_max_batch(self, _init):
        embed = GeminiEmbed.__new__(GeminiEmbed)
        embed.model_name = "gemini-embedding-001"
        embed.client = MagicMock()
        embed.types = MagicMock()

        embed.client.models.embed_content.side_effect = (
            lambda *, model, contents, config: _make_gemini_response(len(contents))
        )

        with patch.object(embed, "_build_embedding_config", return_value=None):
            result, _ = embed.encode(["x"] * 100)

        assert embed.client.models.embed_content.call_count == 1
        assert result.shape == (100, 8)

    @patch.object(GeminiEmbed, "__init__", return_value=None)
    def test_two_api_calls_for_just_over_max(self, _init):
        embed = GeminiEmbed.__new__(GeminiEmbed)
        embed.model_name = "gemini-embedding-001"
        embed.client = MagicMock()
        embed.types = MagicMock()

        embed.client.models.embed_content.side_effect = (
            lambda *, model, contents, config: _make_gemini_response(len(contents))
        )

        with patch.object(embed, "_build_embedding_config", return_value=None):
            result, _ = embed.encode(["x"] * 101)

        assert embed.client.models.embed_content.call_count == 2
        assert result.shape == (101, 8)

    @patch.object(GeminiEmbed, "__init__", return_value=None)
    def test_single_api_call_for_small_batch(self, _init):
        embed = GeminiEmbed.__new__(GeminiEmbed)
        embed.model_name = "gemini-embedding-001"
        embed.client = MagicMock()
        embed.types = MagicMock()

        embed.client.models.embed_content.side_effect = (
            lambda *, model, contents, config: _make_gemini_response(len(contents))
        )

        with patch.object(embed, "_build_embedding_config", return_value=None):
            result, _ = embed.encode(["x"] * 16)

        assert embed.client.models.embed_content.call_count == 1
        assert result.shape == (16, 8)


class TestEmbeddingBatchSizeHelper:
    def _helper(self):
        # Import lazily so the task_executor module isn't loaded at collection time.
        from rag.svr.task_executor import _embedding_batch_size
        return _embedding_batch_size

    def test_model_cap_wins_when_above_env_floor(self, monkeypatch):
        from common import settings
        monkeypatch.setattr(settings, "EMBEDDING_BATCH_SIZE", 16, raising=False)
        helper = self._helper()
        mdl = MagicMock(max_batch_size=100)
        assert helper(mdl) == 100

    def test_env_floor_wins_when_above_model_cap(self, monkeypatch):
        from common import settings
        monkeypatch.setattr(settings, "EMBEDDING_BATCH_SIZE", 200, raising=False)
        helper = self._helper()
        mdl = MagicMock(max_batch_size=100)
        assert helper(mdl) == 200

    def test_falls_back_to_env_when_attribute_missing(self, monkeypatch):
        from common import settings
        monkeypatch.setattr(settings, "EMBEDDING_BATCH_SIZE", 16, raising=False)
        helper = self._helper()

        class NoCap:
            pass

        assert helper(NoCap()) == 16

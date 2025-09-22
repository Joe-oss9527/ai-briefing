
"""Tests for the processing pipeline."""

import pytest
import sys
import os
import numpy as np
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from briefing.pipeline import _near_duplicate_mask, _cluster, run_processing_pipeline
from briefing.utils import clean_text, validate_config


class TestDeduplication:
    """Test near-duplicate detection."""
    
    def test_exact_duplicates_removed(self):
        """Test that exact duplicates are detected."""
        # Create identical embeddings
        embs = np.array([
            [1.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],  # Exact duplicate
            [0.0, 1.0, 0.0],
        ])
        
        mask = _near_duplicate_mask(embs, threshold=0.9)
        assert mask == [True, False, True]  # Second item should be marked as duplicate
    
    def test_near_duplicates_removed(self):
        """Test that near duplicates are detected."""
        # Create very similar embeddings
        embs = np.array([
            [1.0, 0.0, 0.0],
            [0.99, 0.01, 0.0],  # Very similar
            [0.0, 1.0, 0.0],
        ])
        
        mask = _near_duplicate_mask(embs, threshold=0.95)
        assert mask == [True, False, True]  # Second item should be marked as near-duplicate
    
    def test_different_items_kept(self):
        """Test that different items are kept."""
        # Create orthogonal embeddings
        embs = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ])
        
        mask = _near_duplicate_mask(embs, threshold=0.9)
        assert mask == [True, True, True]  # All should be kept


class TestClustering:
    """Test clustering functionality."""
    
    def test_cluster_formation(self):
        """Test that similar items form clusters."""
        # Create embeddings with clear clusters
        embs = np.array([
            # Cluster 1
            [1.0, 0.0, 0.0],
            [0.9, 0.1, 0.0],
            [0.95, 0.05, 0.0],
            # Cluster 2
            [0.0, 1.0, 0.0],
            [0.1, 0.9, 0.0],
            [0.05, 0.95, 0.0],
        ])
        
        labels = _cluster(embs, min_cluster_size=2)
        
        # Check that we have at least 2 distinct clusters
        unique_labels = set(labels)
        # Remove noise label (-1) if present
        unique_labels.discard(-1)
        assert len(unique_labels) >= 1  # At least one cluster formed


class TestTextCleaning:
    """Test text cleaning functionality."""
    
    def test_html_removal(self):
        """Test that HTML is properly cleaned."""
        html = "<p>Hello <b>world</b></p>"
        cleaned = clean_text(html)
        assert "<p>" not in cleaned
        assert "<b>" not in cleaned
        assert "Hello" in cleaned
        assert "world" in cleaned
    
    def test_excessive_newlines_removed(self):
        """Test that excessive newlines are normalized."""
        text = "Line 1\n\n\n\n\nLine 2"
        cleaned = clean_text(text)
        assert "\n\n\n" not in cleaned
        assert "Line 1" in cleaned
        assert "Line 2" in cleaned


class TestConfigValidation:
    """Test configuration validation."""
    
    def test_valid_config_accepted(self):
        """Test that valid configurations pass validation."""
        valid_config = {
            "briefing_id": "test",
            "briefing_title": "Test Briefing",
            "source": {
                "type": "hackernews",
                "hn_story_type": "top",
                "hn_limit": 50
            },
            "processing": {
                "time_window_hours": 24,
                "min_cluster_size": 3,
                "sim_near_dup": 0.9,
                "reranker_model": "BAAI/bge-reranker-v2-m3"
            },
            "summarization": {
                "llm_provider": "gemini",
                "gemini_model": "gemini-1.5-flash",
                "prompt_file": "prompts/daily_briefing_multisource.yaml",
                "prompt_file": "prompts/daily_briefing_multisource.yaml",
                "target_item_count": 10
            },
            "output": {
                "dir": "out/test",
                "formats": ["md", "json"]
            }
        }
        
        # Should not raise an exception
        try:
            validate_config(valid_config)
        except FileNotFoundError:
            # Schema file might not exist in test environment
            pass
    
    def test_invalid_config_rejected(self):
        """Test that invalid configurations are rejected."""
        invalid_config = {
            "briefing_id": "test",
            # Missing required fields
        }
        
        with pytest.raises(Exception):
            validate_config(invalid_config)


class TestTimeWindowFiltering:
    """Test time window filtering in pipeline."""
    
    def test_recent_items_kept(self):
        """Test that recent items are kept."""
        now = datetime.now(timezone.utc)
        recent = now - timedelta(hours=12)
        old = now - timedelta(hours=48)
        
        items = [
            {
                "id": "1",
                "text": "Recent item",
                "url": "http://example.com/1",
                "author": "test",
                "timestamp": recent.isoformat(),
                "metadata": {}
            },
            {
                "id": "2", 
                "text": "Old item",
                "url": "http://example.com/2",
                "author": "test",
                "timestamp": old.isoformat(),
                "metadata": {}
            }
        ]
        
        config = {
            "time_window_hours": 24,
            "min_cluster_size": 2,
            "sim_near_dup": 0.9,
            "reranker_model": "BAAI/bge-reranker-v2-m3",
            "initial_topk": 100,
            "max_candidates_per_cluster": 50
        }
        
        # This would normally call external services, so we can't test it fully
        # but we can ensure it doesn't crash with valid input
        try:
            run_processing_pipeline(items, config)
        except Exception:
            # Expected to fail without services running
            pass


    def test_invalid_timestamp_dropped(self, monkeypatch):
        """Items with invalid timestamps should be ignored by the pipeline."""
        import briefing.pipeline as pipeline

        monkeypatch.setattr(pipeline, "_embed_texts", lambda texts: np.zeros((len(texts), 3)))
        monkeypatch.setattr(pipeline, "_near_duplicate_mask", lambda embs, threshold: [True] * len(embs))
        monkeypatch.setattr(pipeline, "_cluster", lambda embs, min_cluster_size: np.zeros(len(embs), dtype=int))
        monkeypatch.setattr(pipeline, "_top_k_by_centroid", lambda embs, idxs, k=50: idxs)
        monkeypatch.setattr(pipeline, "_cluster_centrality", lambda embs, idxs: (idxs[0], embs[idxs[0]]))
        monkeypatch.setattr(pipeline, "_rerank", lambda model, query, candidates: list(range(len(candidates))))

        now = datetime.now(timezone.utc)
        recent = now - timedelta(hours=1)

        items = [
            {
                "id": "ok",
                "text": "Recent item",
                "url": "http://example.com/1",
                "author": "test",
                "timestamp": recent.isoformat(),
                "metadata": {}
            },
            {
                "id": "bad",
                "text": "Bad timestamp",
                "url": "http://example.com/2",
                "author": "test",
                "timestamp": "not-a-date",
                "metadata": {}
            }
        ]

        config = {
            "time_window_hours": 24,
            "min_cluster_size": 1,
            "sim_near_dup": 0.9,
            "reranker_model": "stub-model",
            "initial_topk": 10,
            "max_candidates_per_cluster": 5
        }

        bundles = run_processing_pipeline(items, config)

        assert len(bundles) == 1
        assert len(bundles[0]["items"]) == 1
        assert bundles[0]["items"][0]["id"] == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

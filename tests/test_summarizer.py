import pytest
import json
from unittest.mock import patch, MagicMock
from summarizer import generate_summary, _mk_prompt, _is_empty


class TestSummarizer:
    
    def test_mk_prompt_requires_prompt_file(self):
        """Test that _mk_prompt raises ValueError when prompt_file is missing"""
        config = {"summarization": {}}
        with pytest.raises(ValueError, match="summarization.prompt_file is required"):
            _mk_prompt([], config)
    
    @patch('summarizer.render_prompt')
    def test_mk_prompt_calls_render_prompt(self, mock_render):
        """Test that _mk_prompt calls render_prompt with correct parameters"""
        mock_render.return_value = "rendered prompt"
        bundles = [{"id": "test", "text": "test content"}]
        config = {
            "briefing_title": "Test Briefing",
            "summarization": {"prompt_file": "test_prompt.yaml"}
        }
        
        result = _mk_prompt(bundles, config)
        
        mock_render.assert_called_once_with("Test Briefing", bundles, "test_prompt.yaml")
        assert result == "rendered prompt"
    
    def test_is_empty_with_no_topics(self):
        """Test _is_empty returns True when no topics"""
        assert _is_empty({}) is True
        assert _is_empty({"topics": []}) is True
        assert _is_empty(None) is True
    
    def test_is_empty_with_topics(self):
        """Test _is_empty returns False when topics exist"""
        assert _is_empty({"topics": [{"title": "test"}]}) is False
    
    def test_generate_summary_with_empty_bundles(self):
        """Test generate_summary returns None for empty bundles"""
        result = generate_summary([], {})
        assert result == (None, None)
    
    @patch('summarizer.llm_call')
    @patch('summarizer.render_prompt')
    @patch('summarizer.validate_briefing')
    @patch('summarizer.render_md')
    def test_generate_summary_success(self, mock_render_md, mock_validate, mock_render_prompt, mock_llm):
        """Test successful generate_summary flow"""
        # Setup mocks
        mock_render_prompt.return_value = "test prompt"
        mock_llm.return_value = '{"topics": [{"title": "Test Topic", "summary": "Test content"}]}'
        mock_validate.return_value = None
        mock_render_md.return_value = "# Test Briefing\n## Test Topic\nTest content"
        
        bundles = [{"id": "1", "text": "test content"}]
        config = {
            "briefing_title": "Test Briefing",
            "summarization": {
                "llm_provider": "gemini",
                "prompt_file": "prompts/daily_briefing_multisource.yaml",
                "target_item_count": 10
            }
        }
        
        md, obj = generate_summary(bundles, config)
        
        # Verify results
        assert md == "# Test Briefing\n## Test Topic\nTest content"
        assert "topics" in obj
        assert len(obj["topics"]) == 1
        assert obj["topics"][0]["title"] == "Test Topic"
        assert "title" in obj
        assert "date" in obj
        
        # Verify mock calls
        mock_llm.assert_called_once()
        mock_validate.assert_called_once()
        mock_render_md.assert_called_once()
    
    @patch('summarizer.llm_call')
    @patch('summarizer.render_prompt')
    def test_generate_summary_json_parse_error(self, mock_render_prompt, mock_llm):
        """Test generate_summary handles JSON parse errors"""
        mock_render_prompt.return_value = "test prompt"
        mock_llm.return_value = "invalid json"
        
        bundles = [{"id": "1", "text": "test"}]
        config = {
            "summarization": {
                "llm_provider": "gemini", 
                "prompt_file": "test.yaml",
                "target_item_count": 10
            }
        }
        
        with pytest.raises(json.JSONDecodeError):
            generate_summary(bundles, config)
    
    @patch('summarizer.llm_call')
    @patch('summarizer.render_prompt')
    @patch('summarizer.validate_briefing')
    def test_generate_summary_empty_topics_after_validation(self, mock_validate, mock_render_prompt, mock_llm):
        """Test generate_summary returns None when topics are empty after validation"""
        mock_render_prompt.return_value = "test prompt"
        mock_llm.return_value = '{"topics": []}'
        mock_validate.return_value = None
        
        bundles = [{"id": "1", "text": "test"}]
        config = {
            "summarization": {
                "llm_provider": "gemini",
                "prompt_file": "test.yaml", 
                "target_item_count": 10
            }
        }
        
        result = generate_summary(bundles, config)
        assert result == (None, None)
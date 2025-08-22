"""Security-focused tests for AI-Briefing platform."""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from publisher import _run_safe
from utils import redact_secrets


class TestCommandInjectionProtection:
    """Test that dangerous commands are properly blocked."""
    
    def test_dangerous_commands_blocked(self):
        """Ensure dangerous commands are rejected."""
        dangerous_commands = [
            ['rm', '-rf', '/'],
            ['curl', 'evil.com'],
            ['wget', 'malicious.site'],
            ['sh', '-c', 'evil'],
            ['bash', '-c', 'evil'],
            ['/bin/sh', 'script.sh'],
        ]
        
        for cmd in dangerous_commands:
            with pytest.raises(ValueError) as exc_info:
                _run_safe(cmd)
            assert "not allowed" in str(exc_info.value).lower()
    
    def test_git_command_whitelist(self):
        """Test that only whitelisted git commands are allowed."""
        # These should fail
        with pytest.raises(ValueError):
            _run_safe(['git', 'gc'])  # Not in whitelist
        
        with pytest.raises(ValueError):
            _run_safe(['git', 'reflog'])  # Not in whitelist
        
        # These should pass validation (but may fail execution)
        allowed = [
            ['git', 'init'],
            ['git', 'status'],
            ['git', 'config', 'user.name', 'Test'],
        ]
        
        for cmd in allowed:
            try:
                _run_safe(cmd, cwd='/tmp')
            except RuntimeError:
                # Execution may fail, but validation should pass
                pass
    
    def test_empty_command_rejected(self):
        """Test that empty or malformed commands are rejected."""
        with pytest.raises(ValueError):
            _run_safe([])
        
        with pytest.raises(ValueError):
            _run_safe(['git'])  # Missing subcommand


class TestSecretRedaction:
    """Test that secrets are properly redacted from logs."""
    
    def test_environment_variable_redaction(self):
        """Test that environment variables are redacted."""
        # Set a test environment variable
        os.environ['GEMINI_API_KEY'] = 'test_secret_key_12345'
        
        test_string = "Using API key: test_secret_key_12345 for request"
        redacted = redact_secrets(test_string)
        
        assert "test_secret_key_12345" not in redacted
        assert "***" in redacted
        
        # Clean up
        del os.environ['GEMINI_API_KEY']
    
    def test_common_secret_patterns(self):
        """Test that common secret patterns are redacted."""
        test_cases = [
            ("token=ghp_abcd1234567890abcd1234567890abcd12", "ghp_***"),
            ("x-access-token:mytoken@github.com", "x-access-token:***@"),
            ("api_key=sk-proj-verylongsecretkey123456", "api_key"),
            ("password=MySecretPassword123!", "password"),
            ("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload", "bearer ***"),
        ]
        
        for test_input, expected_pattern in test_cases:
            redacted = redact_secrets(test_input)
            assert expected_pattern.lower() in redacted.lower() or "***" in redacted
            # Ensure the actual secret is not present
            if "=" in test_input:
                secret = test_input.split("=")[1].split()[0]
                if len(secret) > 8:
                    assert secret not in redacted
    
    def test_empty_string_handling(self):
        """Test that empty strings are handled correctly."""
        assert redact_secrets("") == ""
        assert redact_secrets(None) == None


class TestEmptyBriefingHandling:
    """Test that empty briefings are handled correctly."""
    
    def test_empty_briefing_detection(self):
        """Test that empty briefings are properly detected."""
        from summarizer import generate_summary
        
        # Test with empty bundles
        md, js = generate_summary([], {"summarization": {
            "llm_provider": "gemini",
            "prompt_system": "prompts/system_common.txt",
            "prompt_template": "prompts/template_daily.txt",
            "target_item_count": 10
        }})
        
        assert md is None
        assert js is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
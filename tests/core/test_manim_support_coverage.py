"""
Coverage tests for manim_support.py - Tier 4 Task T4

Target: Raise coverage from 33% to 75%+
Manim support with pre-compiled examples and one-click execution
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import os

from sandbox.core.manim_support import ManIMExamples, ManIMHelper


class TestManIMExamplesInit:
    """Test ManIMExamples initialization."""

    @pytest.fixture
    def artifacts_dir(self, tmp_path):
        """Create temporary artifacts directory."""
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        return artifacts

    def test_init_creates_manim_dir(self, artifacts_dir):
        """Test that manim directory is created."""
        examples = ManIMExamples(artifacts_dir)
        assert examples.artifacts_dir == artifacts_dir
        assert examples.manim_dir == artifacts_dir / "manim"
        assert examples.manim_dir.exists()

    def test_init_creates_examples_dict(self, artifacts_dir):
        """Test that examples dictionary is initialized."""
        examples = ManIMExamples(artifacts_dir)
        assert isinstance(examples.examples, dict)
        assert len(examples.examples) > 0


class TestManIMExamplesListExamples:
    """Test listing available examples."""

    @pytest.fixture
    def examples(self, tmp_path):
        """Create ManIMExamples instance."""
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        return ManIMExamples(artifacts)

    def test_list_examples_returns_dict(self, examples):
        """Test that list_examples returns a dictionary."""
        result = examples.list_examples()
        assert isinstance(result, dict)

    def test_list_examples_has_entries(self, examples):
        """Test that list_examples has example entries."""
        result = examples.list_examples()
        assert len(result) > 0

    def test_list_examples_has_descriptions(self, examples):
        """Test that examples have descriptions."""
        result = examples.list_examples()
        for name, info in result.items():
            assert 'description' in info
            assert 'complexity' in info


class TestManIMExamplesGetExampleCode:
    """Test getting example code."""

    @pytest.fixture
    def examples(self, tmp_path):
        """Create ManIMExamples instance."""
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        return ManIMExamples(artifacts)

    def test_get_example_code_valid(self, examples):
        """Test getting valid example code."""
        code = examples.get_example_code('basic_shapes')
        assert code is not None
        assert 'from manim import' in code
        assert 'class' in code

    def test_get_example_code_invalid(self, examples):
        """Test getting invalid example code."""
        code = examples.get_example_code('nonexistent')
        assert code is None


class TestManIMExamplesExecuteExample:
    """Test example execution."""

    @pytest.fixture
    def examples(self, tmp_path):
        """Create ManIMExamples instance."""
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        return ManIMExamples(artifacts)

    def test_execute_example_not_found(self, examples):
        """Test executing non-existent example."""
        success, message, files = examples.execute_example('nonexistent')
        assert success is False
        assert 'not found' in message
        assert files == []

    def test_execute_example_with_mock(self, examples):
        """Test executing example with mocked subprocess."""
        with patch('subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "Success"
            mock_run.return_value = mock_result

            success, message, files = examples.execute_example('basic_shapes', quality='medium')
            assert success is True
            assert 'successfully' in message

    def test_execute_example_fails_on_error(self, examples):
        """Test execution failure handling."""
        with patch('subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stderr = "Error rendering"
            mock_run.return_value = mock_result

            success, message, files = examples.execute_example('basic_shapes')
            assert success is False
            assert 'failed' in message


class TestManIMExamplesGetSupportedAnimations:
    """Test getting supported animations."""

    @pytest.fixture
    def examples(self, tmp_path):
        """Create ManIMExamples instance."""
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        return ManIMExamples(artifacts)

    def test_get_supported_animations_returns_dict(self, examples):
        """Test that supported animations returns a dictionary."""
        result = examples.get_supported_animations()
        assert isinstance(result, dict)

    def test_has_animation_categories(self, examples):
        """Test that major animation categories exist."""
        result = examples.get_supported_animations()
        expected_categories = ['Creation', 'Transform', 'Movement', 'Fading']
        for category in expected_categories:
            assert category in result

    def test_animations_have_names(self, examples):
        """Test that animations have names."""
        result = examples.get_supported_animations()
        for category, animations in result.items():
            assert isinstance(animations, list)
            assert len(animations) > 0


class TestManIMExamplesCreateCustomExample:
    """Test creating custom examples."""

    @pytest.fixture
    def examples(self, tmp_path):
        """Create ManIMExamples instance."""
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        return ManIMExamples(artifacts)

    def test_create_custom_example_success(self, examples):
        """Test creating custom example."""
        code = "from manim import *\nclass Test(Scene):\n    pass"
        result = examples.create_custom_example('test_custom', code, 'Test description')
        assert result is True
        assert 'test_custom' in examples.examples

    def test_create_custom_example_adds_to_dict(self, examples):
        """Test that custom example is added to examples dict."""
        code = "from manim import *\nclass Test(Scene):\n    pass"
        examples.create_custom_example('my_custom', code, 'My test')
        assert 'my_custom' in examples.examples
        assert examples.examples['my_custom']['code'] == code


class TestManIMExamplesExportExample:
    """Test exporting examples."""

    @pytest.fixture
    def examples(self, tmp_path):
        """Create ManIMExamples instance."""
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        return ManIMExamples(artifacts)

    def test_export_example_valid(self, examples, tmp_path):
        """Test exporting valid example."""
        export_path = tmp_path / "exported.py"
        result = examples.export_example('basic_shapes', str(export_path))
        assert result is True
        assert export_path.exists()

    def test_export_example_invalid(self, examples, tmp_path):
        """Test exporting invalid example."""
        export_path = tmp_path / "exported.py"
        result = examples.export_example('nonexistent', str(export_path))
        assert result is False

    def test_export_example_writes_code(self, examples, tmp_path):
        """Test that export writes the code."""
        export_path = tmp_path / "exported.py"
        examples.export_example('basic_shapes', str(export_path))
        content = export_path.read_text()
        assert 'from manim import' in content


class TestManIMHelperInit:
    """Test ManIMHelper initialization."""

    @pytest.fixture
    def artifacts_dir(self, tmp_path):
        """Create temporary artifacts directory."""
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        return artifacts

    def test_init_creates_helper(self, artifacts_dir):
        """Test helper initialization."""
        helper = ManIMHelper(artifacts_dir)
        assert helper.artifacts_dir == artifacts_dir
        assert helper.examples is not None
        assert isinstance(helper.examples, ManIMExamples)


class TestManIMHelperCheckManimInstallation:
    """Test Manim installation checking."""

    @pytest.fixture
    def helper(self, tmp_path):
        """Create ManIMHelper instance."""
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        return ManIMHelper(artifacts)

    def test_check_manim_installed(self, helper):
        """Test when Manim is installed."""
        with patch('subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "Manim Community v0.18.0"
            mock_run.return_value = mock_result

            success, message = helper.check_manim_installation()
            assert success is True
            assert "Manim" in message

    def test_check_manim_not_installed(self, helper):
        """Test when Manim is not installed."""
        with patch('subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 1
            mock_run.return_value = mock_result

            success, message = helper.check_manim_installation()
            assert success is False
            assert "not found" in message

    def test_check_manim_file_not_found(self, helper):
        """Test when manim command doesn't exist."""
        with patch('subprocess.run', side_effect=FileNotFoundError):
            success, message = helper.check_manim_installation()
            assert success is False
            assert "not installed" in message


class TestManIMHelperGetManimConfig:
    """Test getting Manim configuration."""

    @pytest.fixture
    def helper(self, tmp_path):
        """Create ManIMHelper instance."""
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        return ManIMHelper(artifacts)

    def test_get_manim_config_success(self, helper):
        """Test getting config successfully."""
        with patch('subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "config data"
            mock_run.return_value = mock_result

            config = helper.get_manim_config()
            assert 'config' in config
            assert config['status'] == 'available'

    def test_get_manim_config_error(self, helper):
        """Test getting config with error."""
        with patch('subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 1
            mock_run.return_value = mock_result

            config = helper.get_manim_config()
            assert config['status'] == 'error'

    def test_get_manim_config_exception(self, helper):
        """Test getting config with exception."""
        with patch('subprocess.run', side_effect=Exception("Error")):
            config = helper.get_manim_config()
            assert config['status'] == 'unavailable'


class TestManIMHelperOptimizeForSandbox:
    """Test sandbox optimization."""

    @pytest.fixture
    def helper(self, tmp_path):
        """Create ManIMHelper instance."""
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        return ManIMHelper(artifacts)

    def test_optimize_for_sandbox_returns_dict(self, helper):
        """Test that optimization returns a dictionary."""
        result = helper.optimize_for_sandbox()
        assert isinstance(result, dict)

    def test_optimize_has_quality_setting(self, helper):
        """Test that optimization includes quality setting."""
        result = helper.optimize_for_sandbox()
        assert 'quality' in result

    def test_optimize_has_disable_caching(self, helper):
        """Test that optimization includes caching disabled."""
        result = helper.optimize_for_sandbox()
        assert result['disable_caching'] is True

    def test_optimize_has_media_dir(self, helper):
        """Test that optimization includes media directory."""
        result = helper.optimize_for_sandbox()
        assert 'media_dir' in result
        assert 'manim' in result['media_dir']


class TestManIMHelperGetTroubleshootingGuide:
    """Test troubleshooting guide."""

    @pytest.fixture
    def helper(self, tmp_path):
        """Create ManIMHelper instance."""
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        return ManIMHelper(artifacts)

    def test_get_troubleshooting_guide_returns_dict(self, helper):
        """Test that guide returns a dictionary."""
        guide = helper.get_troubleshooting_guide()
        assert isinstance(guide, dict)

    def test_has_installation_guide(self, helper):
        """Test that installation guide exists."""
        guide = helper.get_troubleshooting_guide()
        assert 'installation' in guide

    def test_has_rendering_slow_guide(self, helper):
        """Test that rendering speed guide exists."""
        guide = helper.get_troubleshooting_guide()
        assert 'rendering_slow' in guide

    def test_has_memory_issues_guide(self, helper):
        """Test that memory issues guide exists."""
        guide = helper.get_troubleshooting_guide()
        assert 'memory_issues' in guide

    def test_has_file_not_found_guide(self, helper):
        """Test that file not found guide exists."""
        guide = helper.get_troubleshooting_guide()
        assert 'file_not_found' in guide


class TestIntegration:
    """Integration tests for Manim support."""

    @pytest.fixture
    def helper(self, tmp_path):
        """Create ManIMHelper instance."""
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        return ManIMHelper(artifacts)

    def test_helper_examples_integration(self, helper):
        """Test that helper properly integrates with examples."""
        assert helper.examples is not None
        assert isinstance(helper.examples, ManIMExamples)
        assert helper.examples.artifacts_dir == helper.artifacts_dir

    def test_full_workflow(self, helper):
        """Test full workflow from check to optimize."""
        # Check installation
        with patch('subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "Manim v0.18.0"
            mock_run.return_value = mock_result

            installed, msg = helper.check_manim_installation()
            assert installed is True

        # Get optimizations
        opts = helper.optimize_for_sandbox()
        assert 'quality' in opts

        # Get examples
        examples = helper.examples.list_examples()
        assert len(examples) > 0

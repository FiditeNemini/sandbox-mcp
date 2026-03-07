"""
Tests for the CodeValidator class.
"""

import pytest


class TestCodeValidatorImport:
    """Test that CodeValidator can be imported and instantiated."""

    def test_code_validator_import(self):
        """Test that CodeValidator can be imported from the core module."""
        from sandbox.core.code_validator import CodeValidator
        
        assert CodeValidator is not None

    def test_code_validator_instantiation(self):
        """Test that CodeValidator can be instantiated."""
        from sandbox.core.code_validator import CodeValidator
        
        validator = CodeValidator()
        assert validator is not None

    def test_code_validator_has_validate_and_format(self):
        """Test that CodeValidator has the validate_and_format method."""
        from sandbox.core.code_validator import CodeValidator
        
        validator = CodeValidator()
        assert hasattr(validator, 'validate_and_format')
        assert callable(validator.validate_and_format)


class TestCodeValidatorBasicFunctionality:
    """Test basic validation functionality."""

    def test_valid_python_code(self):
        """Test validation of valid Python code."""
        from sandbox.core.code_validator import CodeValidator
        
        validator = CodeValidator()
        code = "x = 1\ny = 2\nprint(x + y)"
        
        result = validator.validate_and_format(code)
        
        assert result['valid'] is True
        assert len(result['issues']) == 0

    def test_invalid_python_code(self):
        """Test validation of invalid Python code."""
        from sandbox.core.code_validator import CodeValidator
        
        validator = CodeValidator()
        code = "x = 1\ny = 2\nprint(x +"  # Missing closing paren
        
        result = validator.validate_and_format(code)
        
        assert result['valid'] is False
        assert len(result['issues']) > 0
        assert 'Syntax error' in result['issues'][0]

    def test_empty_code(self):
        """Test validation of empty code."""
        from sandbox.core.code_validator import CodeValidator
        
        validator = CodeValidator()
        code = ""
        
        result = validator.validate_and_format(code)
        
        assert result['valid'] is True

    def test_code_with_comments(self):
        """Test validation of code with comments."""
        from sandbox.core.code_validator import CodeValidator
        
        validator = CodeValidator()
        code = "# This is a comment\nx = 1  # Inline comment\n"
        
        result = validator.validate_and_format(code)
        
        assert result['valid'] is True


class TestCodeValidatorAutoFixes:
    """Test automatic code fixes and formatting."""

    def test_add_missing_imports_matplotlib(self):
        """Test that matplotlib imports are added automatically."""
        from sandbox.core.code_validator import CodeValidator
        
        validator = CodeValidator()
        code = "plt.plot([1, 2, 3])"
        
        result = validator.validate_and_format(code)
        
        assert result['valid'] is True
        assert 'import matplotlib.pyplot as plt' in result['formatted_code']
        # Verify actual newlines, not literal \\n
        assert '\\n' not in repr(result['formatted_code']) or '\n' in result['formatted_code']

    def test_add_missing_imports_numpy(self):
        """Test that numpy imports are added automatically."""
        from sandbox.core.code_validator import CodeValidator
        
        validator = CodeValidator()
        code = "np.array([1, 2, 3])"
        
        result = validator.validate_and_format(code)
        
        assert result['valid'] is True
        assert 'import numpy as np' in result['formatted_code']

    def test_add_missing_imports_multiple(self):
        """Test that multiple imports are added with proper newlines."""
        from sandbox.core.code_validator import CodeValidator
        
        validator = CodeValidator()
        code = "np.array([1, 2, 3])\nplt.plot([1, 2, 3])"
        
        result = validator.validate_and_format(code)
        
        assert result['valid'] is True
        formatted = result['formatted_code']
        assert 'import matplotlib.pyplot as plt' in formatted
        assert 'import numpy as np' in formatted
        # Verify imports are on separate lines
        lines = formatted.split('\n')
        import_lines = [l for l in lines if l.startswith('import ')]
        assert len(import_lines) >= 2

    def test_format_for_display(self):
        """Test code formatting for display with line numbers."""
        from sandbox.core.code_validator import CodeFormatter
        
        code = "x = 1\ny = 2\nprint(x + y)"
        formatted = CodeFormatter.format_for_display(code)
        
        assert '1 |' in formatted
        assert '2 |' in formatted
        assert '3 |' in formatted
        # Verify actual newlines in output
        lines = formatted.split('\n')
        assert len(lines) == 3

    def test_create_executable_wrapper(self):
        """Test that executable wrapper is valid Python."""
        from sandbox.core.code_validator import CodeFormatter
        
        user_code = "print('Hello, World!')"
        wrapper = CodeFormatter.create_executable_wrapper(user_code)
        
        # Verify the wrapper is valid Python
        import ast
        try:
            ast.parse(wrapper)
            valid_syntax = True
        except SyntaxError:
            valid_syntax = False
        
        assert valid_syntax, "Wrapper should be valid Python code"
        assert "print('Hello, World!')" in wrapper

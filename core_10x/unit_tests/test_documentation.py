"""
Test documentation examples by extracting and running code blocks at runtime.

This module automatically extracts Python code blocks from documentation files
and runs them as tests to ensure examples remain functional.
"""

import ast
import re
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from core_10x.ts_store import TsStore

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Module-level variable for documentation files to avoid duplication
DOCUMENTATION_FILES = [
    'README.md',
    'GETTING_STARTED.md',
    'INSTALLATION.md',
    'CONTRIBUTING.md',
]


def extract_code_blocks_from_file(filepath: Path) -> Generator[tuple[str, str], None, None]:
    """Extract Python code blocks from a markdown file."""
    try:
        content = filepath.read_text(encoding='utf-8')
    except FileNotFoundError:
        return

    # Find code blocks (```python ... ```)
    pattern = r'```python\s*\n(.*?)\n```'
    matches = re.findall(pattern, content, re.DOTALL)

    for i, code_block in enumerate(matches, 1):
        # Clean up the code block
        code_block = code_block.strip()

        # Skip empty blocks
        if not code_block:
            continue

        # Generate a test name from the file and block number
        test_name = f'{filepath.stem}_block_{i}'
        yield test_name, code_block


def extract_code_blocks_from_docs() -> Generator[tuple[str, str, str], None, None]:
    """Extract all Python code blocks from documentation files."""
    docs_dir = project_root

    for doc_file in DOCUMENTATION_FILES:
        filepath = docs_dir / doc_file
        for test_name, code_block in extract_code_blocks_from_file(filepath):
            yield f'{doc_file}_{test_name}', code_block, doc_file


def is_ui_code_block(code_block: str) -> bool:
    """Check if a code block contains UI-related imports or usage."""
    ui_indicators = [
        'import rio',
        'from rio',
        'rio.',
        'import ui_10x',
        'from ui_10x',
        'ui_10x.',
        'class.*Component',
        'def build(',
        '@rio.page',
        'rio.Text(',
        'rio.Button(',
        'rio.Column(',
        'rio.Row(',
    ]
    return any(indicator in code_block for indicator in ui_indicators)


def validate_python_syntax(code: str) -> bool:
    """Validate that code has valid Python syntax."""
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


@pytest.mark.parametrize(
    'test_name,code_block,source_file',
    [
        (f'{src}_{name}', code, src)
        for name, code, src in extract_code_blocks_from_docs()
        if not is_ui_code_block(code)  # Skip UI code blocks - tested separately
    ],
)
def test_documentation_code_block_execution(test_name: str, code_block: str, source_file: str):
    """Test that documentation code blocks can execute successfully."""
    # Skip if code block is empty
    if not code_block.strip():
        pytest.skip('Empty code block')

    # Validate syntax
    assert validate_python_syntax(code_block), f'Syntax error in {source_file} {test_name}'

    import builtins
    import sys

    # Create a minimal namespace that avoids complex traitable issues
    # We'll just check that the code can be executed in a basic context
    namespace = {
        '__builtins__': builtins.__dict__.copy(),
    }

    # Add a fake module to sys.modules to avoid KeyError
    fake_module_name = f'__doc_test_{test_name}__'
    fake_module = type(sys)('module')
    fake_module.__dict__.update(
        {
            '__name__': fake_module_name,
            '__file__': f'<{source_file}_{test_name}>',
        }
    )
    sys.modules[fake_module_name] = fake_module
    try:
        exec(code_block, namespace)
    finally:
        # Clean up the fake module
        if fake_module_name in sys.modules:
            del sys.modules[fake_module_name]

        TsStore.s_instances.clear()


@pytest.mark.parametrize(
    'test_name,code_block,source_file',
    [
        (f'{src}_{name}', code, src)
        for name, code, src in extract_code_blocks_from_docs()
        if is_ui_code_block(code)  # Only test UI code blocks
    ],
)
def test_documentation_ui_code_block_syntax(test_name: str, code_block: str, source_file: str):
    """Test that UI documentation code blocks have valid syntax (execution tested separately in UI tests)."""
    # Skip if code block is empty
    if not code_block.strip():
        pytest.skip('Empty code block')

    # Validate syntax only for UI blocks (execution requires async UI environment)
    assert validate_python_syntax(code_block), f'Syntax error in UI code block {source_file} {test_name}'


def test_documentation_files_and_code_blocks():
    """Test that documentation files exist and contain Python code blocks."""
    docs_dir = project_root
    total_blocks = 0
    ui_blocks = 0
    core_blocks = 0

    # Check that all expected documentation files exist
    for filename in DOCUMENTATION_FILES:
        filepath = docs_dir / filename
        assert filepath.exists(), f'Documentation file {filename} not found'
        assert filepath.stat().st_size > 0, f'Documentation file {filename} is empty'

    # Check that files contain Python code blocks
    for test_name, code_block, source_file in extract_code_blocks_from_docs():
        total_blocks += 1
        if is_ui_code_block(code_block):
            ui_blocks += 1
        else:
            core_blocks += 1

    # Ensure we found some code blocks
    assert total_blocks > 0, 'No Python code blocks found in documentation'
    assert core_blocks > 0, 'No core Python code blocks found in documentation'

    # We expect some UI blocks but most should be core functionality
    assert core_blocks >= ui_blocks, f'Expected more core blocks ({core_blocks}) than UI blocks ({ui_blocks})'

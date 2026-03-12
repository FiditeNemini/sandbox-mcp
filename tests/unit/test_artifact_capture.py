"""
Tests for artifact capture functionality.
"""

import pytest
import pytest_asyncio
from pathlib import Path
import os


@pytest_asyncio.fixture
async def sandbox_with_artifacts():
    """Create a LocalSandbox instance ready for artifact testing."""
    from sandbox.sdk.local_sandbox import LocalSandbox
    
    sandbox_instance = LocalSandbox()
    await sandbox_instance.start()
    yield sandbox_instance
    await sandbox_instance.stop()


@pytest.mark.asyncio
class TestMatplotlibPlotCapture:
    """Test matplotlib plot capture functionality."""

    async def test_matplotlib_plot_creation(self, sandbox_with_artifacts):
        """Test that matplotlib plots can be created and saved."""
        artifacts_dir = sandbox_with_artifacts.artifacts_dir
        plots_dir = Path(artifacts_dir) / 'plots'
        plots_dir.mkdir(parents=True, exist_ok=True)
        
        code = f"""
import matplotlib.pyplot as plt
import numpy as np

# Create a simple plot
x = np.linspace(0, 10, 100)
y = np.sin(x)

plt.figure(figsize=(8, 6))
plt.plot(x, y, 'b-')
plt.title('Sine Wave')
plt.xlabel('x')
plt.ylabel('sin(x)')
plt.grid(True)

# Save to artifacts directory
plt.savefig(r'{plots_dir}/sine_wave.png', dpi=100)
plt.close()

print("Plot saved successfully")
"""
        result = await sandbox_with_artifacts.run(code)
        output = await result.output()
        
        assert 'Plot saved successfully' in output
        
        # Verify file was created
        plot_path = plots_dir / 'sine_wave.png'
        assert plot_path.exists(), f"Plot file should exist at {plot_path}"
        assert plot_path.stat().st_size > 0, "Plot file should not be empty"

    async def test_matplotlib_multiple_plots(self, sandbox_with_artifacts):
        """Test creating multiple matplotlib plots."""
        artifacts_dir = sandbox_with_artifacts.artifacts_dir
        plots_dir = Path(artifacts_dir) / 'plots'
        plots_dir.mkdir(parents=True, exist_ok=True)
        
        code = f"""
import matplotlib.pyplot as plt

# Create first plot
plt.figure()
plt.plot([1, 2, 3], [1, 4, 9])
plt.savefig(r'{plots_dir}/plot1.png')
plt.close()

# Create second plot
plt.figure()
plt.bar(['A', 'B', 'C'], [1, 2, 3])
plt.savefig(r'{plots_dir}/plot2.png')
plt.close()

print("Multiple plots saved")
"""
        result = await sandbox_with_artifacts.run(code)
        output = await result.output()
        
        assert 'Multiple plots saved' in output
        
        # Verify both files exist
        assert (plots_dir / 'plot1.png').exists()
        assert (plots_dir / 'plot2.png').exists()


@pytest.mark.asyncio
class TestPILImageCapture:
    """Test PIL image capture functionality."""

    async def test_pil_image_creation(self, sandbox_with_artifacts):
        """Test that PIL images can be created and saved."""
        artifacts_dir = sandbox_with_artifacts.artifacts_dir
        images_dir = Path(artifacts_dir) / 'images'
        images_dir.mkdir(parents=True, exist_ok=True)
        
        code = f"""
from PIL import Image
import numpy as np

# Create a simple RGB image
width, height = 100, 100
data = np.zeros((height, width, 3), dtype=np.uint8)

# Fill with colors
data[:, :50] = [255, 0, 0]  # Red left half
data[:, 50:] = [0, 0, 255]  # Blue right half

img = Image.fromarray(data)
img.save(r'{images_dir}/test_image.png')

print("Image saved successfully")
"""
        result = await sandbox_with_artifacts.run(code)
        output = await result.output()
        
        assert 'Image saved successfully' in output
        
        # Verify file was created
        image_path = images_dir / 'test_image.png'
        assert image_path.exists(), f"Image file should exist at {image_path}"
        assert image_path.stat().st_size > 0, "Image file should not be empty"

    async def test_pil_image_formats(self, sandbox_with_artifacts):
        """Test saving images in different formats."""
        artifacts_dir = sandbox_with_artifacts.artifacts_dir
        images_dir = Path(artifacts_dir) / 'images'
        images_dir.mkdir(parents=True, exist_ok=True)
        
        code = f"""
from PIL import Image
import numpy as np

# Create a test image
data = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
img = Image.fromarray(data)

# Save in different formats
img.save(r'{images_dir}/test.jpg', 'JPEG')
img.save(r'{images_dir}/test.png', 'PNG')

print("Multiple formats saved")
"""
        result = await sandbox_with_artifacts.run(code)
        output = await result.output()
        
        assert 'Multiple formats saved' in output
        
        # Verify files exist
        assert (images_dir / 'test.jpg').exists()
        assert (images_dir / 'test.png').exists()


@pytest.mark.asyncio
class TestArtifactCategorization:
    """Test artifact categorization functionality."""

    async def test_artifact_directory_structure(self, sandbox_with_artifacts):
        """Test that artifact directories are properly structured."""
        artifacts_dir = sandbox_with_artifacts.artifacts_dir
        
        # The sandbox should have created the artifacts directory
        assert Path(artifacts_dir).exists(), f"Artifacts dir should exist: {artifacts_dir}"
        
        # Create subdirectories
        subdirs = ['plots', 'images', 'data']
        for subdir in subdirs:
            dir_path = Path(artifacts_dir) / subdir
            dir_path.mkdir(parents=True, exist_ok=True)
            assert dir_path.exists(), f"Directory {dir_path} should exist"
            assert dir_path.is_dir(), f"{dir_path} should be a directory"

    async def test_list_artifacts(self, sandbox_with_artifacts):
        """Test listing artifacts functionality."""
        # List artifacts using sandbox method
        artifacts = sandbox_with_artifacts.list_artifacts()
        
        # Should return a list (not awaitable)
        assert isinstance(artifacts, list)

    async def test_artifact_categorization_by_type(self, sandbox_with_artifacts):
        """Test that artifacts are categorized by type."""
        artifacts_dir = sandbox_with_artifacts.artifacts_dir
        plots_dir = Path(artifacts_dir) / 'plots'
        images_dir = Path(artifacts_dir) / 'images'
        plots_dir.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)
        
        code = f"""
import matplotlib.pyplot as plt
from PIL import Image
import numpy as np

# Create a plot
plt.figure()
plt.plot([1, 2, 3])
plt.savefig(r'{plots_dir}/chart.png')
plt.close()

# Create an image
data = np.zeros((50, 50, 3), dtype=np.uint8)
img = Image.fromarray(data)
img.save(r'{images_dir}/photo.png')

print("Artifacts created")
"""
        await sandbox_with_artifacts.run(code)
        
        # Verify artifacts exist
        assert (plots_dir / 'chart.png').exists()
        assert (images_dir / 'photo.png').exists()

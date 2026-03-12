# Python Sandbox: FAQ and Limitations

## Overview

The Python Sandbox provides a secure, isolated environment for executing Python code with advanced features including artifact management, web app hosting, and Manim animation support.

## Frequently Asked Questions

### 1. Environment and Setup

**Q: What Python version does the sandbox use?**
A: The sandbox runs Python 3.11+ in a dedicated virtual environment located at `/home/usr/sandbox/.venv`.

**Q: What libraries are pre-installed?**
A: Core libraries include:
- `numpy` - Numerical computing
- `matplotlib` - Plotting and visualization
- `pandas` - Data manipulation
- `PIL/Pillow` - Image processing
- `manim` - Mathematical animations
- `flask` - Web application framework
- `streamlit` - Data app framework
- `jupyter` - Interactive computing

**Q: Can I install additional packages?**
A: Yes, while all commonly needed packages are pre-installed, the install commands can be used to safely install packages that do not require sudo permissions.

### 2. Code Execution

**Q: How do I properly format code for execution?**
A: Follow these guidelines:
```python
# ✅ Correct - Use forward slashes for paths
plt.savefig('/artifacts/plot.png')

# ❌ Incorrect - Avoid backslashes
plt.savefig('\\artifacts\\plot.png')

# ✅ Correct - Use raw strings for Windows-style paths if needed
path = r'C:\Users\data\file.txt'
```

**Q: Why do I get syntax errors with my code?**
A: Common issues:
- Trailing backslashes in strings
- Incorrect path separators
- Missing imports
- Indentation errors

**Q: How long can code execute?**
A: Default timeout is 30 seconds for Python code and 10 seconds for shell commands.

### 3. Artifact Management

**Q: Where are artifacts stored?**
A: Artifacts are stored in session-specific directories:
- Base path: `/home/usr/sandbox/sessions/{session_id}/artifacts/`
- Subdirectories: `plots/`, `images/`, `videos/`, `data/`, `manim/`

**Q: What file types are supported as artifacts?**
A: Supported formats:
- **Images**: PNG, JPG, JPEG, GIF, BMP, SVG
- **Videos**: MP4, AVI, MOV, WEBM
- **Data**: CSV, JSON, XML, YAML, HDF5
- **Documents**: PDF, TXT, MD
- **Code**: PY, HTML, CSS, JS

**Q: How do I ensure my artifacts are saved?**
A: Use absolute paths to the artifacts directory:
```python
import matplotlib.pyplot as plt
import os

# Create the artifacts directory if it doesn't exist
os.makedirs('/artifacts/plots', exist_ok=True)

# Save your plot
plt.savefig('/artifacts/plots/my_plot.png')
```

### 4. Web Applications

**Q: How do I create a web app?**
A: Use Flask or Streamlit:
```python
# Flask example
from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "Hello from Sandbox!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
```

**Q: How do I access my web app?**
A: Web apps are accessible at `http://127.0.0.1:8000` (or assigned port) from your local machine.

### 5. Manim Animations

**Q: How do I create Manim animations?**
A: Use the pre-compiled examples or create custom scenes:
```python
from manim import *

class MyScene(Scene):
    def construct(self):
        circle = Circle()
        self.play(Create(circle))
        self.wait(1)
```

**Q: Why don't my Manim animations render?**
A: Common issues:
- Incorrect scene class structure
- Missing `construct` method
- Syntax errors in animation code
- Memory limitations for complex scenes

### 6. Interactive Features

**Q: What REPL features are available?**
A: Enhanced REPL includes:
- Command history
- Tab completion (basic)
- Custom commands: `artifacts`, `stats`, `help`
- Session persistence
- Colored output

**Q: How do I access previous execution results?**
A: Use the history command in REPL:
```python
history()  # Show recent executions
stats()    # Show performance statistics
```

## Limitations and Restrictions

### 1. Filesystem Access

**Restrictions:**
- ❌ No access to system directories outside sandbox
- ❌ Cannot modify system files or configurations
- ❌ Limited to session-specific artifact directories
- ❌ No network access to external APIs (security)

**Allowed:**
- ✅ Read/write to artifact directories
- ✅ Create temporary files in session space
- ✅ Access pre-installed library data

### 2. Resource Limitations

**Memory:**
- Maximum 1GB RAM per session
- Automatic cleanup of large objects
- Session isolation prevents memory leaks

**CPU:**
- Single-threaded execution
- 30-second timeout for Python code
- 10-second timeout for shell commands

**Storage:**
- 100MB maximum per session
- Automatic cleanup of old sessions
- No persistent storage between sessions

### 3. Network and External Access

**Restrictions:**
- ❌ No internet access for security
- ❌ Cannot access external databases
- ❌ No external API calls
- ❌ Cannot send emails or notifications

**Allowed:**
- ✅ Local web server hosting
- ✅ Inter-process communication within sandbox
- ✅ File-based data exchange

### 4. Package Management

**Restrictions:**
- ❌ Cannot install new packages (`pip install`)
- ❌ Cannot modify package configurations
- ❌ No access to package source code modification

**Alternatives:**
- ✅ All common packages pre-installed
- ✅ Multiple versions of key libraries available
- ✅ Request additional packages for future updates

### 5. Shell Access

**Restrictions:**
- ❌ No system administration commands
- ❌ Cannot modify system services
- ❌ Limited to sandbox directory operations
- ❌ No access to sensitive system information

**Allowed:**
- ✅ File operations within sandbox
- ✅ Basic utilities (ls, cat, grep)
- ✅ Python script execution
- ✅ Text processing commands

## Best Practices

### 1. Code Organization

```python
# Structure your code clearly
import numpy as np
import matplotlib.pyplot as plt
import os

# Set up artifact directory
artifact_dir = '/artifacts/plots'
os.makedirs(artifact_dir, exist_ok=True)

# Your main code
data = np.random.randn(1000)
plt.hist(data, bins=50)
plt.title('Random Data Distribution')

# Save with absolute path
plt.savefig(f'{artifact_dir}/histogram.png')
plt.show()
```

### 2. Error Handling

```python
try:
    # Your code here
    result = some_operation()
except Exception as e:
    print(f"Error: {e}")
    # Log error for debugging
    with open('/artifacts/error_log.txt', 'a') as f:
        f.write(f"Error at {datetime.now()}: {e}\n")
```

### 3. Resource Management

```python
# Clean up large objects
import gc

# After processing large data
del large_data_structure
gc.collect()

# Use context managers for files
with open('/artifacts/data.csv', 'w') as f:
    f.write(data_string)
```

### 4. Session Management

```python
# Save important session data
session_data = {
    'variables': list(globals().keys()),
    'artifacts': os.listdir('/artifacts'),
    'timestamp': datetime.now().isoformat()
}

with open('/artifacts/session_info.json', 'w') as f:
    json.dump(session_data, f, indent=2)
```

## Troubleshooting Guide

### Common Issues and Solutions

**1. "No artifacts found" error**
- Check artifact directory exists: `os.makedirs('/artifacts', exist_ok=True)`
- Use absolute paths: `/artifacts/filename.ext`
- Verify file was actually created: `os.path.exists('/artifacts/filename.ext')`

**2. "Syntax error" in code execution**
- Remove trailing backslashes from strings
- Check indentation consistency
- Verify all imports are included

**3. "Web app not accessible"**
- Ensure host is set to '0.0.0.0'
- Check port availability (8000-8010 range)
- Verify Flask/Streamlit is running

**4. "Manim animation failed"**
- Check scene class structure
- Verify `construct` method exists
- Ensure proper Manim imports

**5. "Memory limit exceeded"**
- Reduce data size or complexity
- Use generators instead of lists for large datasets
- Clean up unused variables with `del`

## Getting Help

For additional support:
1. Use the `help()` command in REPL
2. Check example code in `/examples/` directory
3. Review error logs in `/artifacts/logs/`
4. Test with minimal code examples first

## Security Notes

The sandbox environment is designed for educational and development purposes with the following security measures:
- Process isolation
- Filesystem restrictions
- Network isolation
- Resource limitations
- Automatic session cleanup

These limitations ensure safe execution while providing powerful development capabilities within the restricted environment.

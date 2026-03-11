"""
File template generators for web application exports.

This module provides template functions for generating the files needed
to export Flask and Streamlit applications as Docker containers.

Templates include:
- app.py (the user code)
- requirements.txt (Python dependencies)
- Dockerfile (Docker configuration)
- docker-compose.yml (Docker Compose configuration)
- README.md (documentation)
"""

from __future__ import annotations

from typing import Dict, Callable


def get_flask_app_templates() -> Dict[str, Callable[[str, str], str]]:
    """
    Get file templates for Flask app export.

    Returns:
        Dictionary mapping filenames to template functions.
        Each template function takes (code: str, name: str) and returns file content.
    """
    def app_template(code: str, name: str) -> str:
        return code

    def requirements_template(code: str, name: str) -> str:
        return "Flask>=2.0.0\ngunicorn>=20.0.0\n"

    def dockerfile_template(code: str, name: str) -> str:
        return '''FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
'''

    def compose_template(code: str, name: str) -> str:
        return f'''version: '3.8'
services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - FLASK_ENV=production
'''

    def readme_template(code: str, name: str) -> str:
        return f'''# {name}

Exported Flask application from sandbox.

## Running with Docker

```bash
docker-compose up --build
```

The application will be available at http://localhost:8000

## Running locally

```bash
pip install -r requirements.txt
python app.py
```

## Files

- `app.py` - Main Flask application
- `requirements.txt` - Python dependencies
- `Dockerfile` - Docker configuration
- `docker-compose.yml` - Docker Compose configuration
'''

    return {
        'app.py': app_template,
        'requirements.txt': requirements_template,
        'Dockerfile': dockerfile_template,
        'docker-compose.yml': compose_template,
        'README.md': readme_template
    }


def get_streamlit_app_templates() -> Dict[str, Callable[[str, str], str]]:
    """
    Get file templates for Streamlit app entry.

    Returns:
        Dictionary mapping filenames to template functions.
        Each template function takes (code: str, name: str) and returns file content.
    """
    def app_template(code: str, name: str) -> str:
        return code

    def requirements_template(code: str, name: str) -> str:
        return "streamlit>=1.28.0\npandas>=1.5.0\nnumpy>=1.24.0\n"

    def dockerfile_template(code: str, name: str) -> str:
        return '''FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
'''

    def compose_template(code: str, name: str) -> str:
        return f'''version: '3.8'
services:
  web:
    build: .
    ports:
      - "8501:8501"
    environment:
      - STREAMLIT_SERVER_PORT=8501
      - STREAMLIT_SERVER_ADDRESS=0.0.0.0
'''

    def readme_template(code: str, name: str) -> str:
        return f'''# {name}

Exported Streamlit application from sandbox.

## Running with Docker

```bash
docker-compose up --build
```

The application will be available at http://localhost:8501

## Running locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Files

- `app.py` - Main Streamlit application
- `requirements.txt` - Python dependencies
- `Dockerfile` - Docker configuration
- `docker-compose.yml` - Docker Compose configuration
'''

    return {
        'app.py': app_template,
        'requirements.txt': requirements_template,
        'Dockerfile': dockerfile_template,
        'docker-compose.yml': compose_template,
        'README.md': readme_template
    }


def get_templates_for_app_type(app_type: str) -> Dict[str, Callable[[str, str], str]]:
    """
    Get file templates for the specified app type.

    Args:
        app_type: Type of application ('flask' or 'streamlit')

    Returns:
        Dictionary mapping filenames to template functions.

    Raises:
        ValueError: If app_type is not supported.
    """
    templates = {
        'flask': get_flask_app_templates,
        'streamlit': get_streamlit_app_templates
    }

    if app_type not in templates:
        raise ValueError(f"Unsupported app type: {app_type}. Use 'flask' or 'streamlit'")

    return templates[app_type]()

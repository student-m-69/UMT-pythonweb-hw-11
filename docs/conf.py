"""Sphinx configuration for the Contacts API documentation.

Build with:

    sphinx-build -b html docs docs/_build/html
"""

import os
import sys

# Make the project importable and satisfy the settings module, which
# refuses to load without a secret key.
sys.path.insert(0, os.path.abspath(".."))
os.environ.setdefault("SECRET_KEY", "docs-build-only")

project = "Contacts API"
author = "Murad Imanov"
release = "3.0.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

# Docstrings in the project use the Google style.
napoleon_google_docstring = True
napoleon_numpy_docstring = False

html_theme = "sphinx_rtd_theme"

exclude_patterns = ["_build"]

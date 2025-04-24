# Django Manticoresearch

Django integration for Manticore Search engine.

## Installation

```bash
pip install django-manticoresearch
```

## Configuration

Add `django_manticoresearch` to your `INSTALLED_APPS` in settings.py:

```python
INSTALLED_APPS = [
    # ...
    'django_manticoresearch',
    # ...
]
```

Configure Manticore connection settings:

```python
MANTICORE_SCHEMA = "http"
MANTICORE_HOST = "localhost"
MANTICORE_PORT = 9308
```

## Basic Usage

### Define Indices

```python
from django_manticoresearch import BaseManticoreIndex, TextField, BigintField, index_registry
from myapp.models import Post

@index_registry.register
class PostIndex(BaseManticoreIndex):
    _index_name = "posts"
    model = Post
    
    fields = (
        TextField("title"),
        TextField("content"),
        BigintField("views"),
    )
    
    # Optional field weights for relevance scoring
    field_weights = {
        "title": 10,
        "content": 5,
    }
```

## Searching

```python
# Initialize the index
index = PostIndex()

# Basic search
results = index.search("query text")

# Advanced search with options
results = index.search(
    query="query text",
    match_fields=["title", "content"],
    enable_wildcard_search=True,
    infix_search=True
)

# Convert results to Django QuerySet
queryset = index.search_result_to_queryset(results)
```

## Auto-Indexing

The package automatically connects signals to update indices when model instances are created, updated, or deleted.

## Management Commands

Create all indices:

```bash
python manage.py indexing
```

Create indices for a specific app:

```bash
python manage.py indexing --app=myapp
```

Create indices and index all objects:

```bash
python manage.py indexing --reindex
```

Drop existing indices before creating:

```bash
python manage.py indexing --recreate
```

## Features

- Django ORM-like interface for Manticore search
- Advanced search with wildcards, prefix, infix and full-text search
- Automatic index management with Django signals
- Field type validation and transformation
- Rich query builder API
- Highlighting support
- Support for complex data structures # django-manticoresearch

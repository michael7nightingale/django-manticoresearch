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

You can define indices using two different styles:

#### Style 1: Tuple-based field definitions

```python
from django_manticoresearch import ManticoreIndex, TextField, BigintField, index_registry
from myapp.models import Post

@index_registry.register
class PostIndex(ManticoreIndex):
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

#### Style 2: Class attribute field definitions

```python
from django_manticoresearch import ManticoreIndex, CharField, IntegerField, BooleanField
from myapp.models import Post

class PostIndex(ManticoreIndex):
    title = CharField()
    content = CharField()
    views = IntegerField()
    is_published = BooleanField(default=False)
    
    class Meta:
        index_name = 'posts'
        model = Post
```

### Field Definitions

The following field types are available for defining index fields:

```python
class PostIndex(ManticoreIndex):
    # Field definition in the fields tuple
    fields = (
        # Text fields for full-text search
        TextField("title"),
        TextField("content"),
        
        # Numeric fields
        IntegerField("category_id"),
        BigintField("views"),
        
        # Boolean field
        BooleanField("is_published"),
        
        # Date/time field
        DateTimeField("publication_date"),
        
        # String field (for exact match, not full-text)
        StringField("slug"),
        
        # Multi-value array field
        MVAField("tags"),
    )
```

## Auto-Discovery of Indices

By default, django-manticoresearch automatically discovers and registers indices from all installed apps. The package looks for index definitions in these files:

1. `<app_name>/indexes.py`
2. `<app_name>/indices.py` 

To use auto-discovery:

1. Create one of these files in your Django app
2. Define your ManticoreIndex classes in that file
3. No manual registration is needed

Example app structure:
```
myapp/
  ├── models.py
  ├── views.py
  └── indexes.py  # Your ManticoreIndex definitions go here
```

You can disable auto-discovery by setting `MANTICORE_AUTO_REGISTER_MODELS` to `False` in your Django settings:

```python
MANTICORE_AUTO_REGISTER_MODELS = False  # Default is True
```

If you disable auto-discovery, you'll need to manually register your indices:

```python
from django_manticoresearch import index_registry

@index_registry.register
class MyIndex(ManticoreIndex):
    # Your index definition...
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
- Support for complex data structures

"""Example Manticore indexes."""
from django_manticoresearch import (
    BaseManticoreIndex,
    TextField,
    BigintField,
    DateTimeField,
    index_registry
)
# Import for original style index
from django_manticoresearch import ManticoreIndex, CharField, IntegerField, BooleanField

from example.blog.models import Post


@index_registry.register
class PostIndex(BaseManticoreIndex):
    """Index for blog posts using the new API."""
    
    _index_name = "blog_posts"
    model = Post
    
    # Field definitions
    fields = (
        TextField("title"),
        TextField("content"),
        DateTimeField("pub_date"),
        BigintField("views"),
    )
    
    # Optional field weights for relevance scoring
    field_weights = {
        "title": 10,
        "content": 5,
    }


# Example using the original style with field attributes
class PostIndexLegacy(ManticoreIndex):
    """Index for blog posts using the original attribute-based API."""
    
    title = CharField()
    content = CharField()
    pub_date = DateTimeField()
    views = IntegerField()
    is_featured = BooleanField(default=False)
    
    class Meta:
        index_name = "blog_posts_legacy"
        model = Post 
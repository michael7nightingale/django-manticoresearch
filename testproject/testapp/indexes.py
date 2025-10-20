"""Example Manticore indexes."""

# Import for original style index
from django_manticoresearch import (
    #BaseManticoreIndex,
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    TextField,
    IntegerField,
    ManticoreIndex,
)
from .models.post_model import Post
from .models.tags_model import Tags


# Example using the original style with field attributes
class PostIndex(ManticoreIndex):
    """Index for blog posts using the original attribute-based API."""

    title = CharField()
    content = TextField()
    #pub_date = DateField()
    #pub_date_time = DateTimeField()
    views = IntegerField()
    is_featured = BooleanField(default=False)

    class Meta:
        index_name = "blog_posts"
        model = Post



class TagsIndex(ManticoreIndex):
    """Index for blog posts using the original attribute-based API."""


    class Meta:
        index_name = "blog_tags"
        model = Tags

        fields = (
            CharField("title"),
        )
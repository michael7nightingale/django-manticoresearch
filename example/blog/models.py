"""Example blog models."""
from django.db import models


class Post(models.Model):
    """Blog post model."""
    
    title = models.CharField(max_length=200)
    content = models.TextField()
    pub_date = models.DateTimeField(auto_now_add=True)
    views = models.IntegerField(default=0)
    
    def __str__(self):
        return self.title 
from django.contrib import admin

from .models.post_model import Post
from .models import Tags

admin.site.register([Post, Tags])
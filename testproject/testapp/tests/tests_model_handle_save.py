from django.test import TestCase
from django_manticoresearch.registry import index_registry
from ..models import Post, Tags

class TestsModelHandleSave(TestCase):

    def setUp(self):
        self.indices = index_registry.get_all_indices()

    def test_00_drop_index(self):
        for index_class in self.indices:
            index = index_class()
            self.assertEqual(index.drop_index(), True)

    def test_01_create_index(self):
        for index_class in self.indices:
            index = index_class()
            self.assertEqual(index.create_index(), True)

    def test_02_create_document_int_pk(self):
        instance = Post.objects.create(title="A new document")

    def test_03_create_document_int_pk(self):
        instance = Tags.objects.create(title="A new document")


    # def test_03_reindex(self):
    #     instance = Post.objects.create(id=1, title="A new document")
    #     instance = Post.objects.create(id=2, title="A new document")
    #
    #     for index_class in self.indices:
    #         index = index_class()
    #         index.delete(instance)
    #         print(index.index_all(ensure_delete=False))


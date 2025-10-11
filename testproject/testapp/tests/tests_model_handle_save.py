from django.test import TestCase
from django_manticoresearch.registry import index_registry
from django_manticoresearch.indexes import ManticoreIndex
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

        index = ManticoreIndex()
        index._index_name = 'blog_posts'
        print('pk', instance.pk)
        print('index pk', index.search_pk(pk=instance.pk))

        instance.title='A new document2'
        instance.save()


    def test_03_create_document_random_pk(self):
        instance = Tags.objects.create(
            uuid='642d92be-f309-4c4a-9c72-3ceaf43afe1d',title="A new document")
        instance.title='A new document2'
        instance.save()

        #print('instance pk', instance.pk)


    # def test_03_reindex(self):
    #     instance = Post.objects.create(id=1, title="A new document")
    #     instance = Post.objects.create(id=2, title="A new document")
    #
    #     for index_class in self.indices:
    #         index = index_class()
    #         index.delete(instance)
    #         print(index.index_all(ensure_delete=False))


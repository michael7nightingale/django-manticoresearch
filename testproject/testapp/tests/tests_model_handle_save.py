from django.test import TestCase
from django_manticoresearch.registry import index_registry
from django_manticoresearch.indexes import ManticoreIndex
from ..models import Post, Tags
from ..indexes import PostIndex

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

    def test_02_00_create_document_int_pk(self):
        id = 1
        instance = Post.objects.create(id=id, title="Snow!", content="What often falls at the North Pole but never gets hurt?")
        index = PostIndex()
        self.assertEqual(index.search_pk(pk=id), id)

        instance.title='A new document2'
        instance.save()

        search_result = index.raw(body=f'select title from `blog_posts` where _pk={id}')
        self.assertEqual(search_result.actual_instance[0]['data'][0]['title'],instance.title)

        #search_result = index.raw(body="select title from `blog_posts` where match('1')")
        #print(search_result)

    def test_03_create_document_random_pk(self):
        id = '642d92be-f309-4c4a-9c72-3ceaf43afe1d'
        instance = Tags.objects.create(uuid=id,title="A new document")

        index = PostIndex()
        self.assertEqual(index.search_pk(pk=id), id)

        instance.title='A new document2'
        instance.save()

        search_result = index.raw(body=f'select title from `blog_tags` where `title`=\'{instance.title}\'')
        self.assertEqual(search_result.actual_instance[0]['data'][0]['title'],instance.title)


    # def test_03_reindex(self):
    #     instance = Post.objects.create(id=1, title="A new document")
    #     instance = Post.objects.create(id=2, title="A new document")
    #
    #     for index_class in self.indices:
    #         index = index_class()
    #         index.delete(instance)
    #         print(index.index_all(ensure_delete=False))


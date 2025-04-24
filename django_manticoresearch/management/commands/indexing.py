"""Management command to create Manticore indexes."""
from django.core.management.base import BaseCommand

from django_manticoresearch.indexes import index_registry


class Command(BaseCommand):
    """Command to create all Manticore indexes."""
    
    help = "Create all Manticore indexes defined in your project"
    
    def add_arguments(self, parser):
        parser.add_argument(
            "--app",
            help="Only create indexes for the specified app",
        )
        parser.add_argument(
            "--recreate",
            action="store_true",
            help="Drop existing indexes before creating them",
        )
        parser.add_argument(
            "--reindex",
            action="store_true",
            help="Index all objects after creating indexes",
        )
    
    def handle(self, *args, **options):
        """Command handler."""
        app_name = options.get("app")
        recreate = options.get("recreate", False)
        reindex = options.get("reindex", False)
        
        if app_name:
            # Filter indices by app name
            indices = [idx for idx in index_registry.get_all_indices() 
                      if idx.model._meta.app_label == app_name]
        else:
            indices = index_registry.get_all_indices()
        
        if recreate:
            # Drop and recreate all indices
            for index_class in indices:
                try:
                    index_name = index_class._index_name
                    self.stdout.write(f"Dropping index '{index_name}'...")
                    index = index_class()
                    index.drop_index()
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Failed to drop index '{index_name}': {e}")
                    )
        
        # Create indices
        for index_class in indices:
            try:
                index_name = index_class._index_name
                self.stdout.write(f"Creating index '{index_name}'...")
                index = index_class()
                index.create_index()
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully created index '{index_name}'")
                )
                
                # Reindex if requested
                if reindex:
                    self.stdout.write(f"Indexing objects for '{index_name}'...")
                    index.index_all(ensure_delete=False)
                    self.stdout.write(
                        self.style.SUCCESS(f"Successfully indexed objects for '{index_name}'")
                    )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Failed to process index '{index_name}': {e}")
                ) 
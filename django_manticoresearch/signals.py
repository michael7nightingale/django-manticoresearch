"""Signal handlers for Django models to Manticore indices."""

from typing import Any, Dict, Type

from django.db.models import Model
from django.db.models.signals import post_delete, post_save
from django_manticoresearch.indexes import index_registry


class ManticoreSignalProcessor:
    """Signal processor for automatically updating Manticore indexes (Legacy API)."""

    @classmethod
    def connect_model(cls, model: Type[Model], index_class, mapping_func=None):
        """Connect a Django model to a Manticore index.

        Note: This is provided for backward compatibility. The new API automatically
        connects signals when registering the index.

        Args:
            model: Django model class
            index_class: Manticore index class
            mapping_func: Optional function to convert model instance to document
        """
        # Register the index if it's not already registered
        index_registry.register(index_class)

        # The rest happens automatically through the registry's registration process

        def get_document(instance: Model) -> Dict[str, Any]:
            """Convert a model instance to a document."""
            if mapping_func:
                return mapping_func(instance)

            # Default mapping: convert model fields to index fields
            document = {}
            for field_name in index_class._meta["fields"].keys():
                if hasattr(instance, field_name):
                    document[field_name] = getattr(instance, field_name)

            return document

        def handle_save(sender, instance, **kwargs):
            """Handle post_save signal."""
            document = get_document(instance)

            # Use the model's primary key as the document ID
            document_id = instance.pk

            # Check if the document exists
            if kwargs.get("created", False):
                # Insert new document
                index_class.insert(document)
            else:
                # Update existing document
                index_class.update(document_id, document)

        def handle_delete(sender, instance, **kwargs):
            """Handle post_delete signal."""
            document_id = instance.pk
            index_class.delete(document_id)

        # Connect signals
        post_save.connect(handle_save, sender=model, weak=False)
        post_delete.connect(handle_delete, sender=model, weak=False)

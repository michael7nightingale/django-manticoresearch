from importlib import import_module
from typing import List, Type

from django.apps import apps
from django.utils.module_loading import module_has_submodule
from django_manticoresearch import ManticoreIndex


class IndexRegistry:
    """Registry for Manticore indices."""

    def __init__(self):
        """Initialize empty registry."""
        self._index_classes = set()

    def register(self, index_class: Type[ManticoreIndex]) -> Type[ManticoreIndex]:
        """Register index class and connect signals.

        Args:
            index_class: Manticore index class

        Returns:
            Registered index class
        """
        if index_class not in self._index_classes:
            self._index_classes.add(index_class)

            # Connect signals for auto-indexing when models change
            index_class.connect_signals()

        return index_class

    def autodiscover_indices(self):
        """Auto-discover indices in installed apps.

        Looks for ManticoreIndex subclasses in a 'indexes.py' or 'indices.py'
        module in each installed app and registers them.
        """
        for app_config in apps.get_app_configs():
            if module_has_submodule(app_config.module, "indices") or module_has_submodule(app_config.module, "indexes"):
                try:
                    # Try both common naming conventions
                    module_name = "indices" if module_has_submodule(app_config.module, "indices") else "indexes"
                    module = import_module(f"{app_config.name}.{module_name}")

                    # Find and register all ManticoreIndex subclasses
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, ManticoreIndex)
                            and attr != ManticoreIndex
                            and hasattr(attr, "model")
                        ):
                            # Register the index
                            self.register(attr)
                except Exception as e:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.error(f"Error discovering indices in {app_config.name}: {e}")

    def get_all_indices(self) -> List[Type[ManticoreIndex]]:
        """Get all registered index classes.

        Returns:
            List of registered index classes
        """
        return list(self._index_classes)

    def create_all_indices(self):
        """Create all registered indices."""
        for index_class in self._index_classes:
            try:
                index = index_class()
                index.create_index()
            except Exception as e:
                # Log the error instead of crashing
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Error creating index {index_class._index_name}: {e}")

    def drop_all_indices(self):
        """Drop all registered indices."""
        for index_class in self._index_classes:
            try:
                index = index_class()
                index.drop_index()
            except Exception as e:
                # Log the error instead of crashing
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Error dropping index {index_class._index_name}: {e}")

    def reindex_all(self, ensure_delete: bool = True):
        """Reindex all registered indices.

        Args:
            ensure_delete: Whether to ensure indices are deleted before reindexing
        """
        if ensure_delete:
            self.drop_all_indices()
            self.create_all_indices()

        for index_class in self._index_classes:
            try:
                index = index_class()
                index.index_all(ensure_delete=False)
            except Exception as e:
                # Log the error instead of crashing
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Error reindexing {index_class._index_name}: {e}")


# Global registry instance
index_registry = IndexRegistry()

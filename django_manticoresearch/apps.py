"""Django app configuration for django-manticoresearch."""

from importlib import import_module

from django.apps import AppConfig
from django.utils.module_loading import module_has_submodule
from django.utils.translation import gettext_lazy as _


class ManticoreSearchConfig(AppConfig):
    """Django app configuration for Manticore Search integration."""

    name = "django_manticoresearch"
    verbose_name = _("Manticore Search")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        """Connect signals when the app is ready."""

        from django.conf import settings

        auto_register = getattr(settings, "MANTICORE_AUTO_REGISTER_MODELS", True)

        if auto_register:
            from django_manticoresearch.registry import index_registry

            # Scan apps for index classes
            index_registry.autodiscover_indices()

    def discover_indices(self):
        """Auto-discover indices in installed apps."""
        from django.apps import apps
        from django_manticoresearch.indexes import ManticoreIndex
        from django_manticoresearch.registry import index_registry

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
                            index_registry.register(attr)
                except Exception as e:
                    print(f"Error discovering indices in {app_config.name}: {e}")

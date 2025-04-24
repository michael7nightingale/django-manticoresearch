"""Manticore Search index classes and registry."""

from enum import StrEnum
from typing import Any, Dict, List, Optional, Sequence, Tuple, Type, Union

import ndjson
from django.conf import settings
from django.db.models import Model
from django.db.models.signals import post_delete, post_save
from django_manticoresearch.connection import ManticoreConnector
from django_manticoresearch.fields import ManticoreField


class ManticoreMatchMethodEnum(StrEnum):
    """Enum for Manticore match methods."""

    MATCH = "match"
    MATCH_PHRASE = "matchphrase"


class ManticoreIndexMeta(type):
    """Metaclass for ManticoreIndex that collects fields from class attributes."""

    def __new__(mcs, name, bases, attrs):
        if name == "ManticoreIndex":
            return super().__new__(mcs, name, bases, attrs)

        # Create _meta attribute for the index
        meta = attrs.pop("Meta", type("Meta", (), {}))
        index_name = getattr(meta, "index_name", name.lower())
        model = getattr(meta, "model", None)

        # Collect fields
        fields = ()
        for key, value in list(attrs.items()):
            if isinstance(value, ManticoreField):
                fields = fields + (value,)
                # fields[key] = value
                # Set field name if not already set
                # if not hasattr(value, "name") or not value.name:
                #     value.name = key

        has_id_field = any(field.name == "_id" for field in fields)
        if not has_id_field:
            from django_manticoresearch.fields import BigintField

            fields = (BigintField("_id", processor=lambda obj: obj.id),) + fields

        fields_map = {field.name: field for field in fields}

        # Set required attributes
        attrs["_index_name"] = index_name
        attrs["_model"] = model
        attrs["_fields"] = fields
        attrs["_fields_map"] = fields_map

        # Set model from Meta if available
        if hasattr(meta, "model"):
            attrs["model"] = meta.model

        # Store Meta class
        attrs["Meta"] = meta

        # Create the class
        cls = super().__new__(mcs, name, bases, attrs)

        return cls


class ManticoreIndex(metaclass=ManticoreIndexMeta):
    """Base abstract class for Manticore indices."""

    _highlight_pre_tags = '<span class="highlight">'
    _highlight_post_tags = "</span>"
    _signal_handlers_connected = False
    _index_name: str
    _model: Type[Model]
    _fields: Tuple[ManticoreField]
    _field_weights: Optional[Dict[Union[str, int], Any]] = None

    def __init__(self):
        """Initialize Manticore index with connector and fields."""
        self.manticore = ManticoreConnector()

    def get_queryset(self):
        """Get queryset of objects to index.

        Returns:
            Django queryset with all objects
        """
        return self._model.objects.all()

    def index_all(self, ensure_delete: bool = True, batch_size: int = 1000):
        """Index all objects from the queryset.

        Args:
            ensure_delete: Whether to ensure the index is deleted before indexing
            batch_size: Number of objects to index in one batch
        """
        batch = []
        for obj in self.get_queryset():
            if len(batch) >= batch_size:
                self.bulk(batch)
                batch.clear()
            batch.append(obj)
        if batch:
            self.bulk(batch)

    @property
    def index_name(self) -> str:
        """Get index name with suffix.

        Returns:
            Full Manticore index name
        """
        if getattr(settings, "DEBUG", False):
            return "test_" + self._index_name
        return self._index_name

    @staticmethod
    def escape_query(query: str) -> str:
        """Escape special characters in query.

        Args:
            query: Query string

        Returns:
            Escaped query string
        """
        query = query.replace("http://", "").replace("https://", "")
        escape_symbols = {
            "!",
            '"',
            "\\",
            "$",
            "(",
            ")",
            "-",
            "/",
            "<",
            "@",
            "^",
            "|",
            "~",
        }
        escaped_query = ""
        for symbol in query:
            if symbol in escape_symbols:
                escaped_query += "\\"
            escaped_query += symbol
        return escaped_query

    @staticmethod
    def prepare_wildcard_query(query: str, prefix: bool = True, postfix: bool = True) -> str:
        """Prepare query for wildcard search by adding wildcards to terms.

        Args:
            query: Original query string
            prefix: Whether to add wildcard before terms (prefix search)
            postfix: Whether to add wildcard after terms (postfix search)

        Returns:
            Query with added wildcards for search
        """
        if not query:
            return query

        prefix_char = "*" if prefix else ""
        postfix_char = "*" if postfix else ""

        terms = query.split()
        return (
            " ".join([f"{prefix_char}{term}{postfix_char}" for term in terms])
            if terms
            else f"{prefix_char}{query}{postfix_char}"
        )

    @staticmethod
    def prepare_infix_query(query: str) -> str:
        """Generate query for infix/substring search.

        This creates multiple search patterns to match parts of words:
        - The original word with wildcards (e.g., *Писарев*)
        - Substrings of the word (e.g., исарев, Писар, арев)

        Args:
            query: Original query string

        Returns:
            Query with additional substring patterns
        """
        if not query:
            return query

        terms = query.split()
        result_patterns = []

        for term in terms:
            # Add the original term with wildcards
            result_patterns.append(f"*{term}*")

            # Add substrings of length >= 3 to avoid too many matches
            if len(term) > 3:
                # Generate substrings of different lengths
                for i in range(len(term) - 2):
                    for j in range(i + 3, len(term) + 1):
                        substring = term[i:j]
                        if len(substring) >= 3:  # Only add substantial substrings
                            result_patterns.append(f"*{substring}*")

        return " | ".join(result_patterns) if terms else f"*{query}*"

    def obj_to_document(self, obj: Model) -> Dict[str, Any]:
        """Convert model object to Manticore document.

        Args:
            obj: Django model instance

        Returns:
            Dictionary representation for Manticore
        """
        return {field.name: field.process(obj) for field in self._fields}

    def insert(self, obj: Model):
        """Insert single object into index.

        Args:
            obj: Django model instance
        """
        self.manticore.insert(
            index_name=self.index_name,
            document=self.obj_to_document(obj),
        )

    def bulk(self, queryset: Sequence[Model]):
        """Insert multiple objects into index.

        Args:
            queryset: Sequence of Django model instances
        """
        self.manticore.bulk(
            ndjson.dumps(
                [
                    {
                        "insert": {
                            "index": self.index_name,
                            "doc": self.obj_to_document(obj),
                        }
                    }
                    for obj in queryset
                ]
            )
        )

    def _build_search_payload(
        self,
        query: str,
        highlight: bool,
        offset: int,
        limit: int,
        root_filters: dict | None = None,
    ) -> Dict[str, Any]:
        """Build search payload from query components.

        Args:
            query: Search query string
            highlight: Whether to enable highlighting
            limit: Result limit

        Returns:
            Complete search payload
        """
        payload = {
            "index": self.index_name,
            "query": {
                "query_string": self.escape_query(self.prepare_wildcard_query(query)),
            },
            "limit": limit,
            "offset": offset,
            "max_matches": 100000,
        }

        if root_filters:
            payload["query"].update(root_filters)

        if highlight:
            payload["highlight"] = {
                "pre_tags": self._highlight_pre_tags,
                "post_tags": self._highlight_post_tags,
            }
        if self._field_weights:
            payload["query"]["field_weights"] = self._field_weights

        print(payload)
        return payload

    def search(
        self,
        query: Optional[str] = None,
        match_fields: Optional[List[str]] = None,
        highlight: bool = True,
        limit: int = 20,
        offset: int = 0,
        root_filters: dict | None = None,
    ):
        """Search the index with given query parameters.

        Args:
            query: Search query string
            match_fields: Fields to search in
            highlight: Whether to enable highlighting
            limit: Result limit
            offset: Result offset

        Returns:
            Search results

        Raises:
            ValueError: If no query or extra match is provided
        """
        payload = self._build_search_payload(
            query=query,
            highlight=highlight,
            limit=limit,
            offset=offset,
            root_filters=root_filters,
        )

        return self.manticore.search_api.search(payload)

    def search_result_to_queryset(self, result):
        """Convert search result to Django queryset.

        Args:
            result: Manticore search result

        Returns:
            Django queryset of matching objects
        """
        return self._model.objects.filter(id__in=[hit["_source"]["_id"] for hit in result.hits.hits])

    @classmethod
    def highlight_value(cls, fragment: str, value: str) -> str:
        """Apply highlight to value.

        Args:
            fragment: Highlight fragment
            value: Value to highlight

        Returns:
            Highlighted value
        """
        return value.replace(
            fragment.replace(cls._highlight_pre_tags, "").replace(cls._highlight_post_tags, "").strip(),
            fragment.strip(),
        )

    def highlight_data(self, data: List[Dict], search_result) -> List[Dict]:
        """Apply highlights to result data.

        Args:
            data: List of result data dictionaries
            search_result: Raw search result with highlights

        Returns:
            Data with highlights applied
        """
        highlight_map = {}
        for hit in search_result.hits.hits:
            highlight_map[hit["_source"]["_id"]] = hit["highlight"]

        highlight_data = []

        if not data or not highlight_map:
            return data

        highlight_fields = [field for field in self._fields if field.name in highlight_map[data[0].get("id")]]

        for obj in data:
            if obj.get("id") not in highlight_map:
                highlight_data.append(obj)
                continue
            for field in highlight_fields:
                for highlight_fragment in highlight_map[obj.get("id")].get(field.name, []):
                    obj = field.get_highlight_object_value(self, highlight_fragment, obj)
            highlight_data.append(obj)

        return highlight_data

    @classmethod
    def search_result_to_ids(cls, result) -> List[int]:
        """Extract IDs from search result.

        Args:
            result: Manticore search result

        Returns:
            List of object IDs
        """
        return [hit["_source"]["_id"] for hit in result.hits.hits]

    def search_ids(self, *args, **kwargs) -> List[int]:
        """Search and return only IDs.

        Args:
            *args: Positional arguments for search
            **kwargs: Keyword arguments for search

        Returns:
            List of matching object IDs
        """
        return self.search_result_to_ids(self.search(*args, **kwargs))

    def raw(self, *args, **kwargs):
        """Execute raw SQL query.

        Args:
            *args: Positional arguments for SQL
            **kwargs: Keyword arguments for SQL

        Returns:from inspect import isclass

            SQL query result
        """
        return self.manticore.utils_api.sql(*args, **kwargs)

    def delete(self, obj: Model):
        """Delete object from index.

        Args:
            obj: Django model instance
        """
        self.raw(f"DELETE FROM {self.index_name} WHERE _id={obj.pk}")

    def drop_index(self):
        """Drop index if it exists."""
        self.raw(f"DROP TABLE IF EXISTS {self.index_name}")

    def create_index(self):
        """Create index with fields and configuration."""
        self.manticore.create_index(index_name=self.index_name, field_defs=self.get_field_definitions())

    def get_field_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Get field definitions for index creation."""
        fields = {}
        for field in self._fields:
            fields[field.name] = {
                "type": field.manticore_type,
            }
        return fields

    @classmethod
    def handle_save(cls, sender, instance, **kwargs):
        """Handle post_save signal."""
        index = cls()
        try:
            # Use the model's primary key as the document ID
            if kwargs.get("created", False):
                # Insert new document
                index.insert(instance)
            else:
                # Update existing document
                # First delete then insert to ensure it's updated properly
                index.delete(instance)
                index.insert(instance)
        except Exception as e:
            # Log the error instead of crashing
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error updating index {cls._index_name} for {instance}: {e}")

    @classmethod
    def handle_delete(cls, sender, instance, **kwargs):
        """Handle post_delete signal."""
        index = cls()
        try:
            index.delete(instance)
        except Exception as e:
            # Log the error instead of crashing
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error deleting from index {cls._index_name} for {instance}: {e}")

    @classmethod
    def connect_signals(cls):
        """Connect Django signals to update this index automatically."""
        if cls._signal_handlers_connected:
            return

        cls._signal_handlers_connected = True

        # Connect signals
        post_save.connect(cls.handle_save, sender=cls._model, weak=False)
        post_delete.connect(cls.handle_delete, sender=cls._model, weak=False)

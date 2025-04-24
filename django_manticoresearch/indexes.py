"""Manticore Search index classes and registry."""
import logging
from typing import List, Dict, Any, Type, Optional, Tuple, Set, Union
from inspect import isclass
import re

from django.db import models
from django.db.models.signals import post_save, post_delete

from django_manticoresearch.connection import ManticoreConnector
from django_manticoresearch.fields import Field, ManticoreField

from abc import ABC
from enum import StrEnum
from typing import Dict, List, Any, Type, Optional, ClassVar, Tuple, Union, Sequence

import ndjson
from django.conf import settings
from django.db.models import Model
from django.db.models.signals import post_save, post_delete

from django_manticoresearch.connection import ManticoreConnector
from django_manticoresearch.fields import Field, ManticoreField


class ManticoreMatchMethodEnum(StrEnum):
    """Enum for Manticore match methods."""

    MATCH = "match"
    MATCH_PHRASE = "match_phrase"


class BaseManticoreIndex(ABC):
    """Base abstract class for Manticore indices."""

    _index_name: str
    model: Type[Model]
    field_weights: Optional[Dict[Union[str, int], Any]] = None
    fields: Tuple[Field, ...]
    HIGHLIGHT_PRE_TAGS = '<span class="highlight">'
    HIGHLIGHT_POST_TAGS = "</span>"
    _signal_handlers_connected = False

    def __init__(self):
        """Initialize Manticore index with connector and fields."""
        self.manticore = ManticoreConnector()
        # Prepend ID field if not already included
        has_id_field = any(field.name == "_id" for field in self.fields)
        if not has_id_field:
            from django_manticoresearch.fields import BigintField
            self.fields = (BigintField("_id", processor=lambda obj: obj.id),) + self.fields
        
        self.fields_map = {field.name: field for field in self.fields}

    def get_queryset(self):
        """Get queryset of objects to index.

        Returns:
            Django queryset with all objects
        """
        return self.model.objects.all()

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
        return " ".join([f"{prefix_char}{term}{postfix_char}" for term in terms]) if terms else f"{prefix_char}{query}{postfix_char}"

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
        return {field.name: field.process(obj) for field in self.fields}

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

    def _build_search_query(
        self,
        query: Optional[str],
        match_fields: Optional[List[str]],
        method: ManticoreMatchMethodEnum,
        enable_wildcard_search: bool,
        prefix_search: bool = True,
        postfix_search: bool = True,
        infix_search: bool = False,
    ) -> Tuple[List[Dict], List[Dict]]:
        """Build search query components.

        Args:
            query: Search query string
            match_fields: Fields to search in
            method: Match method to use
            enable_wildcard_search: Whether to enable wildcard searching
            prefix_search: Whether to enable prefix searching
            postfix_search: Whether to enable postfix searching
            infix_search: Whether to enable infix/substring searching

        Returns:
            Tuple of must_matches and should_matches components
        """
        must_matches = []
        should_matches = []

        if not query:
            return must_matches, should_matches

        if match_fields:
            common_match_fields = ",".join(match_fields)
        else:
            common_match_fields = "*"

        # When infix search is enabled, use that instead of regular wildcard search
        if infix_search:
            infix_query = self.prepare_infix_query(query)
            if common_match_fields == "*":
                must_matches = [{"query_string": self.escape_query(infix_query)}]
            else:
                must_matches = [
                    {
                        method.value: {common_match_fields: self.escape_query(infix_query)},
                    }
                ]
        # Otherwise use standard wildcard search if enabled
        elif enable_wildcard_search:
            wildcard_query = self.prepare_wildcard_query(query, prefix_search, postfix_search)
            if common_match_fields == "*":
                must_matches = [{"query_string": self.escape_query(wildcard_query)}]
            else:
                must_matches = [
                    {
                        method.value: {common_match_fields: self.escape_query(wildcard_query)},
                    }
                ]
        # Or use exact match if no wildcard search
        else:
            if common_match_fields == "*":
                must_matches = [{"query_string": self.escape_query(query)}]
            else:
                must_matches = [
                    {
                        method.value: {common_match_fields: self.escape_query(query)},
                    }
                ]

        # Add should matches for space-separated terms
        if query and " " in query:
            if infix_search:
                # For infix search we want to process each term with prepare_infix_query
                if common_match_fields == "*":
                    should_matches.extend(
                        [{"query_string": self.escape_query(self.prepare_infix_query(query_part))} for query_part in query.split(" ")]
                    )
                else:
                    should_matches.extend(
                        [
                            {
                                method.value: {common_match_fields: self.escape_query(self.prepare_infix_query(query_part))},
                            }
                            for query_part in query.split(" ")
                        ]
                    )
            elif enable_wildcard_search:
                if common_match_fields == "*":
                    should_matches.extend(
                        [{"query_string": self.escape_query(self.prepare_wildcard_query(query_part, prefix_search, postfix_search))} for query_part in query.split(" ")]
                    )
                else:
                    should_matches.extend(
                        [
                            {
                                method.value: {common_match_fields: self.escape_query(self.prepare_wildcard_query(query_part, prefix_search, postfix_search))},
                            }
                            for query_part in query.split(" ")
                        ]
                    )
            else:
                if common_match_fields == "*":
                    should_matches.extend(
                        [{"query_string": self.escape_query(query_part)} for query_part in query.split(" ")]
                    )
                else:
                    should_matches.extend(
                        [
                            {
                                method.value: {common_match_fields: self.escape_query(query_part)},
                            }
                            for query_part in query.split(" ")
                        ]
                    )

        # Add should matches for @ separated terms
        if query and "@" in query:
            if infix_search:
                should_matches.extend(
                    [
                        {
                            method.value: {common_match_fields: self.escape_query(self.prepare_infix_query(query_part))},
                        }
                        for query_part in query.split("@")
                    ]
                )
            elif enable_wildcard_search:
                should_matches.extend(
                    [
                        {
                            method.value: {common_match_fields: self.escape_query(self.prepare_wildcard_query(query_part, prefix_search, postfix_search))},
                        }
                        for query_part in query.split("@")
                    ]
                )
            else:
                should_matches.extend(
                    [
                        {
                            method.value: {common_match_fields: self.escape_query(query_part)},
                        }
                        for query_part in query.split("@")
                    ]
                )

        return must_matches, should_matches

    def _build_search_payload(
        self,
        query: Optional[str],
        must_matches: List[Dict],
        should_matches: List[Dict],
        filter_match: Optional[Dict],
        highlight: bool,
        limit: int,
        method: ManticoreMatchMethodEnum,
        prefix_search: bool = True,
        postfix_search: bool = True,
        infix_search: bool = False,
    ) -> Dict[str, Any]:
        """Build search payload from query components.

        Args:
            query: Search query string
            must_matches: Must match components
            should_matches: Should match components
            filter_match: Filter match components
            highlight: Whether to enable highlighting
            limit: Result limit
            method: Match method to use
            prefix_search: Whether to enable prefix searching
            postfix_search: Whether to enable postfix searching
            infix_search: Whether to enable infix/substring searching

        Returns:
            Complete search payload
        """
        payload = {
            "index": self.index_name,
            "query": {
                "bool": {"should": [{"bool": {"must": list(must_matches)}}]},
            },
            "limit": limit,
            "max_matches": 100000,
        }

        if should_matches:
            payload["query"]["bool"]["should"].append({"bool": {"must": should_matches}})

        if query and " " in query:
            concatenated_query = query.replace(" ", "")
            if infix_search:
                payload["query"]["bool"]["should"].append(
                    {
                        "bool": {
                            "must": [
                                {
                                    "query_string": self.escape_query(
                                        self.prepare_infix_query(concatenated_query)
                                    ),
                                }
                            ]
                        }
                    }
                )
            else:
                payload["query"]["bool"]["should"].append(
                    {
                        "bool": {
                            "must": [
                                {
                                    "query_string": self.escape_query(
                                        self.prepare_wildcard_query(concatenated_query, prefix_search, postfix_search)
                                    ),
                                }
                            ]
                        }
                    }
                )

        if filter_match:
            if "must" not in payload["query"]["bool"]:
                payload["query"]["bool"]["must"] = []
            for key, value in filter_match.items():
                payload["query"]["bool"]["must"].append({method.value: {key: self.escape_query(value)}})

        if highlight:
            payload["highlight"] = {
                "pre_tags": self.HIGHLIGHT_PRE_TAGS,
                "post_tags": self.HIGHLIGHT_POST_TAGS,
            }
            if must_matches:
                payload["highlight"]["highlight_query"] = {
                    "bool": {
                        "must": must_matches,
                    },
                }

        if self.field_weights:
            payload["query"]["field_weights"] = self.field_weights

        return payload

    def search(
        self,
        query: Optional[str] = None,
        match_fields: Optional[List[str]] = None,
        filter_match: Optional[Dict] = None,
        extra_match: Optional[Dict] = None,
        highlight: bool = True,
        limit: int = 10000,
        method: ManticoreMatchMethodEnum = ManticoreMatchMethodEnum.MATCH,
        extra_method: ManticoreMatchMethodEnum = ManticoreMatchMethodEnum.MATCH,
        enable_wildcard_search: bool = True,
        prefix_search: bool = True,
        postfix_search: bool = True,
        infix_search: bool = False,
    ):
        """Search the index with given query parameters.

        Args:
            query: Search query string
            match_fields: Fields to search in
            filter_match: Filter match conditions
            extra_match: Additional match conditions
            highlight: Whether to enable highlighting
            limit: Result limit
            method: Match method for primary query
            extra_method: Match method for extra query
            enable_wildcard_search: Whether to enable wildcard searching
            prefix_search: Whether to enable prefix searching
            postfix_search: Whether to enable postfix searching
            infix_search: Whether to enable infix/substring searching

        Returns:
            Search results

        Raises:
            ValueError: If no query or extra match is provided
        """
        if not any((query, extra_match)):
            raise ValueError("Query or extra match are required")

        must_matches, should_matches = self._build_search_query(
            query, match_fields, method, enable_wildcard_search, 
            prefix_search, postfix_search, infix_search
        )

        # Add extra match conditions
        if extra_match:
            for key, value in extra_match.items():
                must_matches.append({extra_method.value: {key: self.escape_query(value)}})

        payload = self._build_search_payload(
            query, must_matches, should_matches, filter_match, highlight, limit, method, 
            prefix_search, postfix_search, infix_search
        )

        return self.manticore.search_api.search(payload)

    def search_result_to_queryset(self, result):
        """Convert search result to Django queryset.

        Args:
            result: Manticore search result

        Returns:
            Django queryset of matching objects
        """
        return self.model.objects.filter(id__in=[hit["_source"]["_id"] for hit in result.hits.hits])

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
            fragment.replace(cls.HIGHLIGHT_PRE_TAGS, "").replace(cls.HIGHLIGHT_POST_TAGS, "").strip(),
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

        highlight_fields = [field for field in self.fields if field.name in highlight_map[data[0].get("id")]]

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

        Returns:
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
        self.manticore.create_index(
            index_name=self.index_name,
            field_defs=self.get_field_definitions()
        )
    
    def get_field_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Get field definitions for index creation."""
        fields = {}
        for field in self.fields:
            fields[field.name] = {
                "type": field.manticore_type,
                "nullable": getattr(field, "null", False),
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
        post_save.connect(cls.handle_save, sender=cls.model, weak=False)
        post_delete.connect(cls.handle_delete, sender=cls.model, weak=False)


class IndexRegistry:
    """Registry for Manticore indices."""

    def __init__(self):
        """Initialize empty registry."""
        self._index_classes = set()

    def register(self, index_class: Type[BaseManticoreIndex]) -> Type[BaseManticoreIndex]:
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
    
    def get_all_indices(self) -> List[Type[BaseManticoreIndex]]:
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


class ManticoreIndexMeta(type):
    """Metaclass for ManticoreIndex that collects fields from class attributes."""
    
    def __new__(mcs, name, bases, attrs):
        if name == "ManticoreIndex":
            return super().__new__(mcs, name, bases, attrs)
        
        # Create _meta attribute for the index
        meta = attrs.pop("Meta", type("Meta", (), {}))
        index_name = getattr(meta, "index_name", name.lower())
        
        # Collect fields
        fields = {}
        for key, value in list(attrs.items()):
            if isinstance(value, ManticoreField):
                fields[key] = value
                # Set field name if not already set
                if not hasattr(value, "name") or not value.name:
                    value.name = key
        
        # Set required attributes for BaseManticoreIndex compatibility
        attrs["_index_name"] = index_name
        
        # Set model from Meta if available
        if hasattr(meta, "model"):
            attrs["model"] = meta.model
        
        # Use the ManticoreField instances directly as they now inherit from Field
        attrs["fields"] = tuple(fields.values())
        
        # Create the class
        cls = super().__new__(mcs, name, bases, attrs)
        
        # Auto-register with the index registry
        index_registry.register(cls)
        
        return cls


class ManticoreIndex(BaseManticoreIndex, metaclass=ManticoreIndexMeta):
    """Base class for defining Manticore indexes with field attributes."""
    
    # This is required for backward compatibility
    connection: ClassVar[ManticoreConnector] = None
    
    def __init__(self):
        """Initialize ManticoreIndex instance."""
        # Set model if not defined from Meta
        if not hasattr(self, "model") and hasattr(self, "Meta"):
            meta = getattr(self, "Meta")
            if hasattr(meta, "model"):
                self.model = meta.model
        
        # Continue with BaseManticoreIndex initialization
        super().__init__()
    
    @classmethod
    def get_queryset(cls):
        """Get queryset of objects to index.

        Returns:
            Django queryset with all objects
        """
        if hasattr(cls, "Meta") and hasattr(cls.Meta, "model"):
            return cls.Meta.model.objects.all()
        return cls.model.objects.all() if hasattr(cls, "model") else None
    
    @classmethod
    def get_connection(cls) -> ManticoreConnector:
        """Get or create a Manticore connection."""
        if cls.connection is None:
            config = getattr(settings, "MANTICORE_CONFIG", {})
            cls.connection = ManticoreConnector(**config)
        return cls.connection
    
    @classmethod
    def search(cls, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search the index with the given query."""
        connection = cls.get_connection()
        index_name = cls._index_name
        return connection.search(index_name, query, **kwargs)
    
    @classmethod
    def insert(cls, document: Dict[str, Any]) -> int:
        """Insert a document into the index."""
        connection = cls.get_connection()
        index_name = cls._index_name
        return connection.insert(index_name, document)
    
    @classmethod
    def update(cls, document_id: int, document: Dict[str, Any]) -> bool:
        """Update a document in the index."""
        connection = cls.get_connection()
        index_name = cls._index_name
        return connection.update(index_name, document_id, document)
    
    @classmethod
    def delete(cls, document_id: int) -> bool:
        """Delete a document from the index."""
        connection = cls.get_connection()
        index_name = cls._index_name
        return connection.delete(index_name, document_id) 
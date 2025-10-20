"""Connection module for Manticore Search."""

import manticoresearch
from manticoresearch.models.insert_document_request import InsertDocumentRequest
from manticoresearch.models.replace_document_request import ReplaceDocumentRequest

from django.conf import settings
import logging

class ManticoreConnector:
    """Connector class for Manticore Search services."""
    logger = logging.getLogger(__name__)

    def __init__(
        self,
        schema: str | None = None,
        host: str | None = None,
        port: int | None = None,
        hard_exit: int | None = None,
    ):
        """Initialize Manticore connector with connection parameters.

        Args:
            schema: Connection schema (http/https)
            host: Manticore host address
            port: Manticore port
        """
        if schema is None:
            schema = getattr(settings, "MANTICORE_SCHEMA", "http")
        if host is None:
            host = getattr(settings, "MANTICORE_HOST", "localhost")
        if port is None:
            port = getattr(settings, "MANTICORE_PORT", 9308)
        if hard_exit is None:
            hard_exit = getattr(settings, "MANTICORE_HARD_EXIT", False)

        connection_string = f"{schema}://{host}:{port}"
        self._config = manticoresearch.Configuration(host=connection_string)
        self._client = manticoresearch.ApiClient(self.config)
        self._search_api = manticoresearch.SearchApi(self.client)
        self._index_api = manticoresearch.IndexApi(self.client)
        self._utils_api = manticoresearch.UtilsApi(self.client)
        self.hard_exit=hard_exit

    @property
    def config(self) -> manticoresearch.Configuration:
        return self._config

    @property
    def client(self) -> manticoresearch.ApiClient:
        return self._client

    @property
    def search_api(self) -> manticoresearch.SearchApi:
        return self._search_api

    @property
    def index_api(self) -> manticoresearch.IndexApi:
        return self._index_api

    @property
    def utils_api(self) -> manticoresearch.UtilsApi:
        return self._utils_api

    def search(self, index_name: str, query: str, **kwargs):
        """Basic search method for legacy compatibility."""
        return self.search_api.search(
            {"index": index_name, "query": {"query_string": query}, "limit": kwargs.get("limit", 20)}
        )

    def search_raw(self, index_name: str, query: str, **kwargs):
        """Basic search method for legacy compatibility."""
        self.logger.debug(f"Search RAW index: {index_name}, query: {query}")

        return self.search_api.search(
            {"table": index_name, "query": query, "limit": kwargs.get("limit", 20)}
        )

    def insert(self, index_name: str, id:int, doc: dict):
        """Insert a document into an index."""
        self.logger.debug(f"Insert document: id:{id}, doc: {doc}")
        return self.index_api.insert(InsertDocumentRequest(
                table=index_name,
                id=id,
                doc=doc
            )
        )

    def replace(self, index_name: str, id:int, doc: dict):
        """Rerlace a document into an index."""
        self.logger.debug(f"Replace document: id:{id}, doc: {doc}")
        return self.index_api.replace(InsertDocumentRequest(
                table=index_name,
                id=id,
                doc=doc
            )
        )
        # return ReplaceDocumentRequest(
        #          table=index_name,
        #          id=id,
        #          doc=doc
        #      )

    def update(self, index_name: str, document_id: int, document: dict):
        """Update a document in an index."""
        return self.index_api.update(
            {
                "index": index_name,
                "id": document_id,
                "doc": document,
            }
        )

    def delete(self, index_name: str, document_id: int):
        """Delete a document from an index."""
        self.utils_api.sql(f"DELETE FROM {index_name} WHERE _id={document_id}")

    def delete_index(self, index_name):
        """Drop index if it exists."""
        sql_query = f"DROP TABLE IF EXISTS {index_name}"
        result = self.utils_api.sql(sql_query)
        self.logger.debug(f"Drop Index {index_name}, result: {result}")
        return "error" not in result


    def create_index(self, index_name: str, field_defs: dict, index_defs: dict):
        """Create an index with specified field definitions."""
        field_strings = []
        for name, props in field_defs.items():
            field_type = props.get("type", "text")
            field_strings.append(f"{name} {field_type}")

        fields_clause = ", ".join(field_strings)
        sql_query = f"CREATE TABLE IF NOT EXISTS {index_name} ({fields_clause})\n" + "\n".join(
            f"{attr}='{value}'" for attr, value in index_defs.items()
        )
        result = self.utils_api.sql(sql_query)
        return "error" not in result

    def bulk(self, bulk_data: str):
        """Execute a bulk operation."""
        result = self.index_api.bulk(bulk_data)
        return "error" not in result

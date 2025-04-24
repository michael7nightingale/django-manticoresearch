"""Field definitions for Manticore indexes."""
from abc import ABC
from typing import Any, Callable, Optional, Tuple, Union, Dict, List

from django.db.models import Model
from django.db.models.query_utils import DeferredAttribute


class ManticoreField(ABC):
    """Base abstract field class for Manticore index fields."""

    manticore_type: str
    default_processor: Callable = lambda self, value: value
    __slots__ = ("name", "model_field", "processor", "highlight_object_path", "null", "default", "primary_key")

    def __init__(
        self,
        name: Optional[str] = None,
        model_field: Optional[DeferredAttribute] = None,
        processor: Optional[Callable] = None,
        highlight_object_path: Optional[Tuple[str, ...]] = None,
        null: bool = False,
        default: Any = None,
        primary_key: bool = False,
    ):
        """Initialize field with name and processing options.

        Args:
            name: Field name in Manticore
            model_field: Django model attribute to get field data from
            processor: Custom processor function to transform field value
            highlight_object_path: Path to navigate to get highlight value
            null: Whether the field can be null
            default: Default value for the field
            primary_key: Whether this field is a primary key
        """
        self.name = name
        self.model_field = model_field
        self.processor = processor
        self.null = null
        self.default = default
        self.primary_key = primary_key
        
        if highlight_object_path:
            self.highlight_object_path = highlight_object_path
        else:
            self.highlight_object_path = (self.name,) if self.name else None

    def __set_name__(self, owner, name):
        """Set field name from class attribute name."""
        if not self.name:
            self.name = name
        if hasattr(self, "highlight_object_path") and not self.highlight_object_path:
            self.highlight_object_path = (self.name,)

    def process(self, obj: Model) -> Any:
        """Process object to extract and transform field value.

        Args:
            obj: Django model instance

        Returns:
            Processed field value

        Raises:
            Exception: If field processing fails
        """
        try:
            if self.model_field:
                field_value = getattr(obj, self.model_field.field.name)
                if self.processor:
                    return self.processor(field_value)
                return self.default_processor(field_value)
            else:
                has_attribute = hasattr(obj, self.name)
                if self.processor:
                    if has_attribute:
                        return self.processor(getattr(obj, self.name))
                    return self.processor(obj)
                else:
                    if has_attribute:
                        return self.default_processor(getattr(obj, self.name))
                    return self.default_processor(obj)
        except Exception as e:
            raise Exception(f"Failed to process field {self.name} value for object: {obj}") from e

    @classmethod
    def highlight_primitive(cls, index, highlight_fragment: str, data: Any) -> str:
        """Apply highlight formatting to primitive data.

        Args:
            index: Manticore index instance
            highlight_fragment: Highlight fragment from search result
            data: Data to highlight

        Returns:
            Highlighted data
        """
        return index.highlight_value(highlight_fragment, data)

    def get_highlight_object_value(
        self,
        index,
        highlight_fragment: str,
        data: Union[Dict, List, str],
        highlight_object_path: Optional[Tuple[str, ...]] = None,
    ) -> Any:
        """Apply highlights to complex data structures.

        Args:
            index: Manticore index instance
            highlight_fragment: Highlight fragment from search result
            data: Data to highlight
            highlight_object_path: Path to navigate for highlighting

        Returns:
            Data with highlights applied
        """
        if highlight_object_path is None:
            highlight_object_path = self.highlight_object_path

        if isinstance(data, str):
            return self.highlight_primitive(index, highlight_fragment, data)

        if isinstance(data, list):
            return [
                self.get_highlight_object_value(index, highlight_fragment, value_item, highlight_object_path)
                for value_item in data
            ]

        if not highlight_object_path:
            return data

        highlight_object_path_item = highlight_object_path[0]

        if isinstance(data, dict):
            if highlight_object_path_item in data:
                data[highlight_object_path_item] = self.get_highlight_object_value(
                    index, highlight_fragment, data[highlight_object_path_item], highlight_object_path[1:]
                )
            return data


class CharField(ManticoreField):
    """Text field for Manticore indexes."""
    
    field_type = "text"
    manticore_type = "text"
    default_processor = lambda self, value: str(value) if value is not None else ""


class TextField(CharField):
    """Alias for CharField, for compatibility."""
    pass


class TextArrayField(ManticoreField):
    """Text array field for Manticore indexes."""

    field_type = "text"
    manticore_type = "text"
    default_processor = lambda self, value: ", ".join(str(v) for v in value) if value else ""

    def __init__(
        self,
        name: Optional[str] = None,
        model_field: Optional[DeferredAttribute] = None,
        processor: Optional[Callable] = None,
        highlight_object_path: Optional[Tuple[str, ...]] = None,
        separator: str = ", ",
        null: bool = False,
        default: Any = None,
        primary_key: bool = False,
    ):
        """Initialize text array field.

        Args:
            name: Field name in Manticore
            model_field: Django model attribute to get field data from
            processor: Custom processor function
            highlight_object_path: Path to navigate for highlighting
            separator: Separator for joining array elements
            null: Whether the field can be null
            default: Default value for the field
            primary_key: Whether this field is a primary key
        """
        super().__init__(
            name=name,
            model_field=model_field,
            processor=processor,
            highlight_object_path=highlight_object_path,
            null=null,
            default=default,
            primary_key=primary_key,
        )
        self.separator = separator

    @classmethod
    def highlight_primitive(cls, index, highlight_fragment: str, data: Any) -> str:
        """Apply highlight formatting to text array data.

        Args:
            index: Manticore index instance
            highlight_fragment: Highlight fragment from search result
            data: Data to highlight

        Returns:
            Highlighted data
        """
        for highlight_fragment_item in highlight_fragment.split(", "):
            data = super().highlight_primitive(index, highlight_fragment_item, data)
        return data


class IntegerField(ManticoreField):
    """Integer field for Manticore indexes."""
    
    field_type = "integer"
    manticore_type = "bigint"
    default_processor = lambda self, value: int(value) if value is not None else 0


class BigintField(IntegerField):
    """Alias for IntegerField, with correct manticore type."""
    pass


class FloatField(ManticoreField):
    """Float field for Manticore indexes (stored as bigint in Manticore)."""
    
    field_type = "float"
    manticore_type = "bigint"
    
    def process(self, obj: Model) -> int:
        """Process float value to integer for Manticore."""
        value = super().process(obj)
        try:
            return int(float(value)) if value is not None else 0
        except (ValueError, TypeError):
            return 0


class DateTimeField(ManticoreField):
    """DateTime field for Manticore indexes (stored as timestamp)."""
    
    field_type = "timestamp"
    manticore_type = "bigint"
    
    def process(self, obj: Model) -> int:
        """Process datetime to timestamp."""
        value = super().process(obj)
        if value is None:
            return 0
        
        # Handle both datetime objects and timestamp values
        if hasattr(value, 'timestamp'):
            return int(value.timestamp())
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0


class BooleanField(ManticoreField):
    """Boolean field for Manticore indexes (stored as integer)."""
    
    field_type = "integer"
    manticore_type = "bigint"
    
    def __init__(
        self,
        name: Optional[str] = None,
        model_field: Optional[DeferredAttribute] = None,
        processor: Optional[Callable] = None,
        highlight_object_path: Optional[Tuple[str, ...]] = None,
        null: bool = False,
        default: Any = None,
        primary_key: bool = False,
    ):
        """Initialize boolean field."""
        super().__init__(
            name=name,
            model_field=model_field,
            processor=processor,
            highlight_object_path=highlight_object_path,
            null=null,
            default=default,
            primary_key=primary_key,
        )
        if self.default is not None:
            self.default = 1 if self.default else 0
    
    def process(self, obj: Model) -> int:
        """Process boolean value to integer."""
        value = super().process(obj)
        if value is None:
            return 0
        return 1 if value else 0 
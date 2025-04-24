"""Django Manticoresearch package."""

__version__ = '0.1.0'

# Import StrEnum for match methods
from enum import StrEnum

# Import all field types
from django_manticoresearch.fields import (
    Field,
    ManticoreField,
    CharField,
    TextField,
    IntegerField,
    BigintField,
    BooleanField,
    DateTimeField,
    StringField,
    MVAField,
)

# Import main classes from indexes module
from django_manticoresearch.indexes import (
    BaseManticoreIndex,
    ManticoreIndex,
    IndexRegistry,
    ManticoreMatchMethodEnum,
    index_registry,
) 
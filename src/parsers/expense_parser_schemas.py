"""Typed schemas for LLM expense parser responses."""
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, RootModel


class ParserSchemaModel(BaseModel):
    """Base parser schema with strict field names and compatible normalisation."""

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    def to_parser_dict(self) -> dict:
        return self.model_dump()


class ParsedQuery(ParserSchemaModel):
    intent: Literal['query']
    query_type: Literal['category_balance', 'account_balance', 'budget_summary']
    query_target: Optional[str] = None
    confidence: float = Field(ge=0, le=1)


class ParsedExpense(ParserSchemaModel):
    intent: Literal['expense']
    amount: float = Field(gt=0)
    category: str = Field(min_length=1)
    payee: str = Field(min_length=1)
    account: Optional[str] = None
    memo: str = Field(min_length=1)
    date: Optional[str] = None
    confidence: float = Field(ge=0, le=1)


class ParsedSharedExpense(ParserSchemaModel):
    intent: Literal['shared_expense']
    amount: float = Field(gt=0)
    category: str = Field(min_length=1)
    payee: str = Field(min_length=1)
    account: Optional[str] = None
    memo: str = Field(min_length=1)
    date: Optional[str] = None
    confidence: float = Field(ge=0, le=1)
    person: str = Field(min_length=1)
    proportion: Optional[str] = None
    split_amount: Optional[float] = Field(default=None, gt=0)
    user_share_amount: Optional[float] = Field(default=None, gt=0)
    other_share_amount: Optional[float] = Field(default=None, gt=0)
    payer: Literal['user', 'other'] = 'user'


ParsedResponseUnion = Annotated[
    Union[ParsedQuery, ParsedExpense, ParsedSharedExpense],
    Field(discriminator='intent'),
]


class ParsedExpenseResponse(RootModel[ParsedResponseUnion]):
    """Discriminated union wrapper for all parse_message response variants."""

    def to_parser_dict(self) -> dict:
        return self.root.to_parser_dict()


def message_response_format_schema() -> dict:
    """Return the JSON schema used for OpenAI Structured Outputs.
    
    Wraps the discriminated union in a root 'result' object to comply with
    OpenAI's requirement that the root be a simple object, while still
    using anyOf to force the model to only output relevant fields.
    """
    nullable_string = {'type': ['string', 'null']}
    nullable_number = {'type': ['number', 'null']}

    # 1. Query Schema
    query_schema = {
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'intent': {'type': 'string', 'enum': ['query']},
            'query_type': {
                'type': 'string',
                'enum': ['category_balance', 'account_balance', 'budget_summary'],
            },
            'query_target': nullable_string,
            'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1},
        },
        'required': ['intent', 'query_type', 'query_target', 'confidence'],
    }

    # 2. Expense Schema
    expense_schema = {
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'intent': {'type': 'string', 'enum': ['expense']},
            'amount': {'type': 'number', 'exclusiveMinimum': 0},
            'category': {'type': 'string', 'minLength': 1},
            'payee': {'type': 'string', 'minLength': 1},
            'account': nullable_string,
            'memo': {'type': 'string', 'minLength': 1},
            'date': nullable_string,
            'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1},
        },
        'required': [
            'intent',
            'amount',
            'category',
            'payee',
            'account',
            'memo',
            'date',
            'confidence',
        ],
    }

    # 3. Shared Expense Schema
    shared_expense_schema = {
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'intent': {'type': 'string', 'enum': ['shared_expense']},
            'amount': {'type': 'number', 'exclusiveMinimum': 0},
            'category': {'type': 'string', 'minLength': 1},
            'payee': {'type': 'string', 'minLength': 1},
            'account': nullable_string,
            'memo': {'type': 'string', 'minLength': 1},
            'date': nullable_string,
            'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1},
            'person': {'type': 'string', 'minLength': 1},
            'proportion': nullable_string,
            'split_amount': nullable_number,
            'user_share_amount': nullable_number,
            'other_share_amount': nullable_number,
            'payer': {'type': 'string', 'enum': ['user', 'other']},
        },
        'required': [
            'intent',
            'amount',
            'category',
            'payee',
            'account',
            'memo',
            'date',
            'confidence',
            'person',
            'proportion',
            'split_amount',
            'user_share_amount',
            'other_share_amount',
            'payer',
        ],
    }

    return {
        'type': 'object',
        'properties': {
            'result': {
                'anyOf': [query_schema, expense_schema, shared_expense_schema],
            },
        },
        'required': ['result'],
        'additionalProperties': False,
    }

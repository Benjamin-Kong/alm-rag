"""Bounded literal equality over preserved immutable source metadata."""
import json,math
from typing import Any,Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator

class FieldEquality(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kind:Literal['NORMALIZED','SOURCE']
    key:str=Field(min_length=1,max_length=1024)
    value:Any

class SearchFilters(BaseModel):
    model_config=ConfigDict(extra='forbid')
    item_uids:list[str]|None=Field(default=None,min_length=1,max_length=1000)
    source_item_ids:list[str]|None=Field(default=None,min_length=1,max_length=1000)
    source_scope_ids:list[str]|None=Field(default=None,min_length=1,max_length=1000)
    fields:list[FieldEquality]=Field(default_factory=list,max_length=32)

    @model_validator(mode='after')
    def bounded(self):
        for values in (self.item_uids,self.source_item_ids,self.source_scope_ids):
            if values is not None and (len(set(values))!=len(values) or any(not x or len(x)>1024 for x in values)):
                raise ValueError('unique nonempty bounded identities required')
        try:serialized=json.dumps(self.model_dump(),allow_nan=False,ensure_ascii=False)
        except (ValueError,TypeError,RecursionError):raise ValueError('finite JSON equality values required') from None
        if len(serialized.encode())>65536:raise ValueError('filters exceed 65536 bytes')
        return self


def equal(left,right):
    if type(left) is not type(right):return False
    if isinstance(left,dict):return left.keys()==right.keys() and all(equal(left[k],right[k]) for k in left)
    if isinstance(left,list):return len(left)==len(right) and all(equal(a,b) for a,b in zip(left,right))
    return left==right

_NORMALIZED={'id','project_id','scope_id','revision','title','status','type','created_at','updated_at','url','source_type'}
def matches(filters,row):
    if filters is None:return True
    envelope=json.loads(row['raw_payload'])
    for key,column in [('item_uids','item_uid'),('source_item_ids','source_item_id'),('source_scope_ids','scope_id')]:
        values=getattr(filters,key)
        actual=envelope.get('scope_id') if key=='source_scope_ids' else row[column]
        if values is not None and actual not in values:return False
    for predicate in filters.fields:
        if predicate.kind=='SOURCE':
            values=[f['raw_value'] for f in envelope.get('fields',[]) if f.get('source_field_id')==predicate.key and 'raw_value' in f]
            if not values or not all(equal(value,predicate.value) for value in values):return False
        else:
            if predicate.key=='description.raw':
                description=envelope.get('description',{})
                if not isinstance(description,dict) or 'raw' not in description:return False
                value=description['raw']
            elif predicate.key in _NORMALIZED and predicate.key in envelope:value=envelope[predicate.key]
            else:return False
            if isinstance(value,(dict,list)) or not equal(value,predicate.value):return False
    return True

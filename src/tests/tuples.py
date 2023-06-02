from typing import NamedTuple, Optional


class ColumnTuple(NamedTuple):
    attname: str
    type: str
    attstattarget: int
    attnum: int
    is_array: bool
    type_mod: Optional[int]
    nullable: bool
    atthasdef: bool
    attidentity: str
    attgenerated: str
    collname: str
    expr: str
    sequence_name: str


class TableTuple(NamedTuple):
    tablename: str
    tableowner: str
    schemaname: str
    tablespace: str
    rowsecurity: bool
    oid: int

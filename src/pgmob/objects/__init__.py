"""Objects in this module are mirrors for remote postgres objects. Any change of the object
(if allowed) will result in affecting that mirrored remote object after executing .apply() method.
When object attributes change, an object schedules a Change closure that would execute once .apply()
is called, which allows users to chain modifications together.

The object state can be refreshed any time by calling .refresh() on the object.
"""

from .databases import Database, DatabaseCollection
from .replication_slots import ReplicationSlot, ReplicationSlotCollection
from .roles import Role, RoleCollection
from .hba_rules import HBARule, HBARuleCollection
from .sequences import Sequence, SequenceCollection
from .tables import Table, TableCollection
from .procedures import (
    Procedure,
    Function,
    Aggregate,
    WindowFunction,
    Volatility,
    ParallelSafety,
    ProcedureVariations,
    ProcedureCollection,
)
from .views import View, ViewCollection
from .schemas import Schema, SchemaCollection
from .large_objects import LargeObject, LargeObjectCollection

from typing import List
from unittest.mock import Mock
from pgmob.sql import Composed


class PGMobTester:
    @staticmethod
    def _parse_calls(*args, statement: int = None) -> List[str]:
        singletons: List[str] = []
        statements = [args[statement]] if statement else args
        for singleton in [x.args[0] for x in statements]:
            if isinstance(singleton, Composed):
                singletons.extend([str(x._value) for x in singleton._parts])
            else:
                singletons.append(singleton._value)
        return singletons

    @staticmethod
    def assertSql(sql: str, cursor: Mock, statement: int = None, mogrify: bool = False):
        singletons = PGMobTester._parse_calls(
            *(cursor.mogrify.call_args_list if mogrify else cursor.execute.call_args_list)
        )
        assert any(
            [sql in x for x in singletons]
        ), "{sql} was supposed to be among statements:\n{stmts}".format(sql=sql, stmts="\n".join(singletons))

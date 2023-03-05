from pgmob.objects import generic


def test_mapped_collection():
    class A(generic.MappedCollection[int]):
        pass

    col = A()
    col["b"] = 2
    col["a"] = 1
    assert list(col) == [1, 2]
    assert list(col.keys()) == ["a", "b"]
    assert str(col) == "A('a', 'b')"
    assert repr(col) == "A('a', 'b')"

    col2 = A(sorted=False)
    col2["b"] = 2
    col2["a"] = 1
    assert list(col2) == [2, 1]
    assert list(col2.keys()) == ["b", "a"]
    assert str(col2) == "A('b', 'a')"
    assert repr(col2) == "A('b', 'a')"

    assert col != col2

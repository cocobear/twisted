# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Tests for L{twisted.python.compat}.
"""

from __future__ import division, absolute_import

import socket, sys, traceback, io, codecs

from twisted.trial import unittest

from twisted.python.compat import (
    reduce, execfile, _PYPY, comparable, cmp, nativeString,
    networkString, unicode as unicodeCompat, lazyByteSlice, reraise,
    NativeStringIO, iterbytes, intToBytes, ioType, bytesEnviron, iteritems,
    _coercedUnicode, unichr, raw_input, _bytesRepr, _get_async_param,
)
from twisted.python.filepath import FilePath
from twisted.python.runtime import platform



class IOTypeTests(unittest.SynchronousTestCase):
    """
    Test cases for determining a file-like object's type.
    """

    def test_3StringIO(self):
        """
        An L{io.StringIO} accepts and returns text.
        """
        self.assertEqual(ioType(io.StringIO()), unicodeCompat)


    def test_3BytesIO(self):
        """
        An L{io.BytesIO} accepts and returns bytes.
        """
        self.assertEqual(ioType(io.BytesIO()), bytes)


    def test_3openTextMode(self):
        """
        A file opened via 'io.open' in text mode accepts and returns text.
        """
        with io.open(self.mktemp(), "w") as f:
            self.assertEqual(ioType(f), unicodeCompat)


    def test_3openBinaryMode(self):
        """
        A file opened via 'io.open' in binary mode accepts and returns bytes.
        """
        with io.open(self.mktemp(), "wb") as f:
            self.assertEqual(ioType(f), bytes)


    def test_codecsOpenBytes(self):
        """
        The L{codecs} module, oddly, returns a file-like object which returns
        bytes when not passed an 'encoding' argument.
        """
        with codecs.open(self.mktemp(), 'wb') as f:
            self.assertEqual(ioType(f), bytes)


    def test_codecsOpenText(self):
        """
        When passed an encoding, however, the L{codecs} module returns unicode.
        """
        with codecs.open(self.mktemp(), 'wb', encoding='utf-8') as f:
            self.assertEqual(ioType(f), unicodeCompat)


    def test_defaultToText(self):
        """
        When passed an object about which no sensible decision can be made, err
        on the side of unicode.
        """
        self.assertEqual(ioType(object()), unicodeCompat)



class CompatTests(unittest.SynchronousTestCase):
    """
    Various utility functions in C{twisted.python.compat} provide same
    functionality as modern Python variants.
    """

    def test_set(self):
        """
        L{set} should behave like the expected set interface.
        """
        a = set()
        a.add('b')
        a.add('c')
        a.add('a')
        b = list(a)
        b.sort()
        self.assertEqual(b, ['a', 'b', 'c'])
        a.remove('b')
        b = list(a)
        b.sort()
        self.assertEqual(b, ['a', 'c'])

        a.discard('d')

        b = set(['r', 's'])
        d = a.union(b)
        b = list(d)
        b.sort()
        self.assertEqual(b, ['a', 'c', 'r', 's'])


    def test_frozenset(self):
        """
        L{frozenset} should behave like the expected frozenset interface.
        """
        a = frozenset(['a', 'b'])
        self.assertRaises(AttributeError, getattr, a, "add")
        self.assertEqual(sorted(a), ['a', 'b'])

        b = frozenset(['r', 's'])
        d = a.union(b)
        b = list(d)
        b.sort()
        self.assertEqual(b, ['a', 'b', 'r', 's'])


    def test_reduce(self):
        """
        L{reduce} should behave like the builtin reduce.
        """
        self.assertEqual(15, reduce(lambda x, y: x + y, [1, 2, 3, 4, 5]))
        self.assertEqual(16, reduce(lambda x, y: x + y, [1, 2, 3, 4, 5], 1))



class ExecfileCompatTests(unittest.SynchronousTestCase):
    """
    Tests for the Python 3-friendly L{execfile} implementation.
    """

    def writeScript(self, content):
        """
        Write L{content} to a new temporary file, returning the L{FilePath}
        for the new file.
        """
        path = self.mktemp()
        with open(path, "wb") as f:
            f.write(content.encode("ascii"))
        return FilePath(path.encode("utf-8"))


    def test_execfileGlobals(self):
        """
        L{execfile} executes the specified file in the given global namespace.
        """
        script = self.writeScript(u"foo += 1\n")
        globalNamespace = {"foo": 1}
        execfile(script.path, globalNamespace)
        self.assertEqual(2, globalNamespace["foo"])


    def test_execfileGlobalsAndLocals(self):
        """
        L{execfile} executes the specified file in the given global and local
        namespaces.
        """
        script = self.writeScript(u"foo += 1\n")
        globalNamespace = {"foo": 10}
        localNamespace = {"foo": 20}
        execfile(script.path, globalNamespace, localNamespace)
        self.assertEqual(10, globalNamespace["foo"])
        self.assertEqual(21, localNamespace["foo"])


    def test_execfileUniversalNewlines(self):
        """
        L{execfile} reads in the specified file using universal newlines so
        that scripts written on one platform will work on another.
        """
        for lineEnding in u"\n", u"\r", u"\r\n":
            script = self.writeScript(u"foo = 'okay'" + lineEnding)
            globalNamespace = {"foo": None}
            execfile(script.path, globalNamespace)
            self.assertEqual("okay", globalNamespace["foo"])



class PYPYTest(unittest.SynchronousTestCase):
    """
    Identification of PyPy.
    """

    def test_PYPY(self):
        """
        On PyPy, L{_PYPY} is True.
        """
        if 'PyPy' in sys.version:
            self.assertTrue(_PYPY)
        else:
            self.assertFalse(_PYPY)



@comparable
class Comparable(object):
    """
    Objects that can be compared to each other, but not others.
    """
    def __init__(self, value):
        self.value = value


    def __cmp__(self, other):
        if not isinstance(other, Comparable):
            return NotImplemented
        return cmp(self.value, other.value)



class ComparableTests(unittest.SynchronousTestCase):
    """
    L{comparable} decorated classes emulate Python 2's C{__cmp__} semantics.
    """

    def test_equality(self):
        """
        Instances of a class that is decorated by C{comparable} support
        equality comparisons.
        """
        # Make explicitly sure we're using ==:
        self.assertTrue(Comparable(1) == Comparable(1))
        self.assertFalse(Comparable(2) == Comparable(1))


    def test_nonEquality(self):
        """
        Instances of a class that is decorated by C{comparable} support
        inequality comparisons.
        """
        # Make explicitly sure we're using !=:
        self.assertFalse(Comparable(1) != Comparable(1))
        self.assertTrue(Comparable(2) != Comparable(1))


    def test_greaterThan(self):
        """
        Instances of a class that is decorated by C{comparable} support
        greater-than comparisons.
        """
        self.assertTrue(Comparable(2) > Comparable(1))
        self.assertFalse(Comparable(0) > Comparable(3))


    def test_greaterThanOrEqual(self):
        """
        Instances of a class that is decorated by C{comparable} support
        greater-than-or-equal comparisons.
        """
        self.assertTrue(Comparable(1) >= Comparable(1))
        self.assertTrue(Comparable(2) >= Comparable(1))
        self.assertFalse(Comparable(0) >= Comparable(3))


    def test_lessThan(self):
        """
        Instances of a class that is decorated by C{comparable} support
        less-than comparisons.
        """
        self.assertTrue(Comparable(0) < Comparable(3))
        self.assertFalse(Comparable(2) < Comparable(0))


    def test_lessThanOrEqual(self):
        """
        Instances of a class that is decorated by C{comparable} support
        less-than-or-equal comparisons.
        """
        self.assertTrue(Comparable(3) <= Comparable(3))
        self.assertTrue(Comparable(0) <= Comparable(3))
        self.assertFalse(Comparable(2) <= Comparable(0))



class Python3ComparableTests(unittest.SynchronousTestCase):
    """
    Python 3-specific functionality of C{comparable}.
    """

    def test_notImplementedEquals(self):
        """
        Instances of a class that is decorated by C{comparable} support
        returning C{NotImplemented} from C{__eq__} if it is returned by the
        underlying C{__cmp__} call.
        """
        self.assertEqual(Comparable(1).__eq__(object()), NotImplemented)


    def test_notImplementedNotEquals(self):
        """
        Instances of a class that is decorated by C{comparable} support
        returning C{NotImplemented} from C{__ne__} if it is returned by the
        underlying C{__cmp__} call.
        """
        self.assertEqual(Comparable(1).__ne__(object()), NotImplemented)


    def test_notImplementedGreaterThan(self):
        """
        Instances of a class that is decorated by C{comparable} support
        returning C{NotImplemented} from C{__gt__} if it is returned by the
        underlying C{__cmp__} call.
        """
        self.assertEqual(Comparable(1).__gt__(object()), NotImplemented)


    def test_notImplementedLessThan(self):
        """
        Instances of a class that is decorated by C{comparable} support
        returning C{NotImplemented} from C{__lt__} if it is returned by the
        underlying C{__cmp__} call.
        """
        self.assertEqual(Comparable(1).__lt__(object()), NotImplemented)


    def test_notImplementedGreaterThanEquals(self):
        """
        Instances of a class that is decorated by C{comparable} support
        returning C{NotImplemented} from C{__ge__} if it is returned by the
        underlying C{__cmp__} call.
        """
        self.assertEqual(Comparable(1).__ge__(object()), NotImplemented)


    def test_notImplementedLessThanEquals(self):
        """
        Instances of a class that is decorated by C{comparable} support
        returning C{NotImplemented} from C{__le__} if it is returned by the
        underlying C{__cmp__} call.
        """
        self.assertEqual(Comparable(1).__le__(object()), NotImplemented)



class CmpTests(unittest.SynchronousTestCase):
    """
    L{cmp} should behave like the built-in Python 2 C{cmp}.
    """

    def test_equals(self):
        """
        L{cmp} returns 0 for equal objects.
        """
        self.assertEqual(cmp(u"a", u"a"), 0)
        self.assertEqual(cmp(1, 1), 0)
        self.assertEqual(cmp([1], [1]), 0)


    def test_greaterThan(self):
        """
        L{cmp} returns 1 if its first argument is bigger than its second.
        """
        self.assertEqual(cmp(4, 0), 1)
        self.assertEqual(cmp(b"z", b"a"), 1)


    def test_lessThan(self):
        """
        L{cmp} returns -1 if its first argument is smaller than its second.
        """
        self.assertEqual(cmp(0.1, 2.3), -1)
        self.assertEqual(cmp(b"a", b"d"), -1)



class StringTests(unittest.SynchronousTestCase):
    """
    Compatibility functions and types for strings.
    """

    def assertNativeString(self, original, expected):
        """
        Raise an exception indicating a failed test if the output of
        C{nativeString(original)} is unequal to the expected string, or is not
        a native string.
        """
        self.assertEqual(nativeString(original), expected)
        self.assertIsInstance(nativeString(original), str)


    def test_nonASCIIBytesToString(self):
        """
        C{nativeString} raises a C{UnicodeError} if input bytes are not ASCII
        decodable.
        """
        self.assertRaises(UnicodeError, nativeString, b"\xFF")


    def test_nonASCIIUnicodeToString(self):
        """
        C{nativeString} raises a C{UnicodeError} if input Unicode is not ASCII
        encodable.
        """
        self.assertRaises(UnicodeError, nativeString, u"\u1234")


    def test_bytesToString(self):
        """
        C{nativeString} converts bytes to the native string format, assuming
        an ASCII encoding if applicable.
        """
        self.assertNativeString(b"hello", "hello")


    def test_unicodeToString(self):
        """
        C{nativeString} converts unicode to the native string format, assuming
        an ASCII encoding if applicable.
        """
        self.assertNativeString(u"Good day", "Good day")


    def test_stringToString(self):
        """
        C{nativeString} leaves native strings as native strings.
        """
        self.assertNativeString("Hello!", "Hello!")


    def test_unexpectedType(self):
        """
        C{nativeString} raises a C{TypeError} if given an object that is not a
        string of some sort.
        """
        self.assertRaises(TypeError, nativeString, 1)


    def test_unicode(self):
        """
        C{compat.unicode} is C{str} on Python 3, C{unicode} on Python 2.
        """
        self.assertIs(unicodeCompat, str)


    def test_nativeStringIO(self):
        """
        L{NativeStringIO} is a file-like object that stores native strings in
        memory.
        """
        f = NativeStringIO()
        f.write("hello")
        f.write(" there")
        self.assertEqual(f.getvalue(), "hello there")



class NetworkStringTests(unittest.SynchronousTestCase):
    """
    Tests for L{networkString}.
    """
    def test_unicode(self):
        """
        L{networkString} returns a C{unicode} object passed to it encoded into
        a C{bytes} instance.
        """
        self.assertEqual(b"foo", networkString(u"foo"))


    def test_unicodeOutOfRange(self):
        """
        L{networkString} raises L{UnicodeError} if passed a C{unicode} instance
        containing characters not encodable in ASCII.
        """
        self.assertRaises(
            UnicodeError, networkString, u"\N{SNOWMAN}")


    def test_nonString(self):
        """
        L{networkString} raises L{TypeError} if passed a non-string object or
        the wrong type of string object.
        """
        self.assertRaises(TypeError, networkString, object())
        self.assertRaises(TypeError, networkString, b"bytes")



class ReraiseTests(unittest.SynchronousTestCase):
    """
    L{reraise} re-raises exceptions on both Python 2 and Python 3.
    """

    def test_reraiseWithNone(self):
        """
        Calling L{reraise} with an exception instance and a traceback of
        L{None} re-raises it with a new traceback.
        """
        try:
            1/0
        except:
            typ, value, tb = sys.exc_info()
        try:
            reraise(value, None)
        except:
            typ2, value2, tb2 = sys.exc_info()
            self.assertEqual(typ2, ZeroDivisionError)
            self.assertIs(value, value2)
            self.assertNotEqual(traceback.format_tb(tb)[-1],
                                traceback.format_tb(tb2)[-1])
        else:
            self.fail("The exception was not raised.")


    def test_reraiseWithTraceback(self):
        """
        Calling L{reraise} with an exception instance and a traceback
        re-raises the exception with the given traceback.
        """
        try:
            1/0
        except:
            typ, value, tb = sys.exc_info()
        try:
            reraise(value, tb)
        except:
            typ2, value2, tb2 = sys.exc_info()
            self.assertEqual(typ2, ZeroDivisionError)
            self.assertIs(value, value2)
            self.assertEqual(traceback.format_tb(tb)[-1],
                             traceback.format_tb(tb2)[-1])
        else:
            self.fail("The exception was not raised.")



class Python3BytesTests(unittest.SynchronousTestCase):
    """
    Tests for L{iterbytes}, L{intToBytes}, L{lazyByteSlice}.
    """

    def test_iteration(self):
        """
        When L{iterbytes} is called with a bytestring, the returned object
        can be iterated over, resulting in the individual bytes of the
        bytestring.
        """
        input = b"abcd"
        result = list(iterbytes(input))
        self.assertEqual(result, [b'a', b'b', b'c', b'd'])


    def test_intToBytes(self):
        """
        When L{intToBytes} is called with an integer, the result is an
        ASCII-encoded string representation of the number.
        """
        self.assertEqual(intToBytes(213), b"213")


    def test_lazyByteSliceNoOffset(self):
        """
        L{lazyByteSlice} called with some bytes returns a semantically equal
        version of these bytes.
        """
        data = b'123XYZ'
        self.assertEqual(bytes(lazyByteSlice(data)), data)


    def test_lazyByteSliceOffset(self):
        """
        L{lazyByteSlice} called with some bytes and an offset returns a
        semantically equal version of these bytes starting at the given offset.
        """
        data = b'123XYZ'
        self.assertEqual(bytes(lazyByteSlice(data, 2)), data[2:])


    def test_lazyByteSliceOffsetAndLength(self):
        """
        L{lazyByteSlice} called with some bytes, an offset and a length returns
        a semantically equal version of these bytes starting at the given
        offset, up to the given length.
        """
        data = b'123XYZ'
        self.assertEqual(bytes(lazyByteSlice(data, 2, 3)), data[2:5])



class BytesEnvironTests(unittest.TestCase):
    """
    Tests for L{BytesEnviron}.
    """
    def test_alwaysBytes(self):
        """
        The output of L{BytesEnviron} should always be a L{dict} with L{bytes}
        values and L{bytes} keys.
        """
        result = bytesEnviron()
        types = set()

        for key, val in iteritems(result):
            types.add(type(key))
            types.add(type(val))

        self.assertEqual(list(types), [bytes])

    if platform.isWindows():
        test_alwaysBytes.skip = "Environment vars are always str on Windows."



class CoercedUnicodeTests(unittest.TestCase):
    """
    Tests for L{twisted.python.compat._coercedUnicode}.
    """

    def test_unicodeASCII(self):
        """
        Unicode strings with ASCII code points are unchanged.
        """
        result = _coercedUnicode(u'text')
        self.assertEqual(result, u'text')
        self.assertIsInstance(result, unicodeCompat)


    def test_unicodeNonASCII(self):
        """
        Unicode strings with non-ASCII code points are unchanged.
        """
        result = _coercedUnicode(u'\N{SNOWMAN}')
        self.assertEqual(result, u'\N{SNOWMAN}')
        self.assertIsInstance(result, unicodeCompat)


    def test_nativeASCII(self):
        """
        Native strings with ASCII code points are unchanged.

        On Python 2, this verifies that ASCII-only byte strings are accepted,
        whereas for Python 3 it is identical to L{test_unicodeASCII}.
        """
        result = _coercedUnicode('text')
        self.assertEqual(result, u'text')
        self.assertIsInstance(result, unicodeCompat)


    def test_bytesPy3(self):
        """
        Byte strings are not accceptable in Python 3.
        """
        exc = self.assertRaises(TypeError, _coercedUnicode, b'bytes')
        self.assertEqual(str(exc), "Expected str not b'bytes' (bytes)")



class UnichrTests(unittest.TestCase):
    """
    Tests for L{unichr}.
    """

    def test_unichr(self):
        """
        unichar exists and returns a unicode string with the given code point.
        """
        self.assertEqual(unichr(0x2603), u"\N{SNOWMAN}")


class RawInputTests(unittest.TestCase):
    """
    Tests for L{raw_input}
    """
    def test_raw_input(self):
        """
        L{twisted.python.compat.raw_input}
        """
        class FakeStdin:
            def readline(self):
                return "User input\n"

        class FakeStdout:
            data = ""
            def write(self, data):
                self.data += data

        self.patch(sys, "stdin", FakeStdin())
        stdout = FakeStdout()
        self.patch(sys, "stdout", stdout)
        self.assertEqual(raw_input("Prompt"), "User input")
        self.assertEqual(stdout.data, "Prompt")



class FutureBytesReprTests(unittest.TestCase):
    """
    Tests for L{twisted.python.compat._bytesRepr}.
    """

    def test_bytesReprNotBytes(self):
        """
        L{twisted.python.compat._bytesRepr} raises a
        L{TypeError} when called any object that is not an instance of
        L{bytes}.
        """
        exc = self.assertRaises(TypeError, _bytesRepr, ["not bytes"])
        self.assertEquals(str(exc), "Expected bytes not ['not bytes']")


    def test_bytesReprPrefix(self):
        """
        L{twisted.python.compat._bytesRepr} always prepends
        ``b`` to the returned repr on both Python 2 and 3.
        """
        self.assertEqual(_bytesRepr(b'\x00'), "b'\\x00'")



class GetAsyncParamTests(unittest.SynchronousTestCase):
    """
    Tests for L{twisted.python.compat._get_async_param}
    """

    def test_get_async_param(self):
        """
        L{twisted.python.compat._get_async_param} uses isAsync by default,
        or deprecated async keyword argument if isAsync is None.
        """
        self.assertEqual(_get_async_param(isAsync=False), False)
        self.assertEqual(_get_async_param(isAsync=True), True)
        self.assertEqual(
            _get_async_param(isAsync=None, **{'async': False}), False)
        self.assertEqual(
            _get_async_param(isAsync=None, **{'async': True}), True)
        self.assertRaises(TypeError, _get_async_param, False, {'async': False})


    def test_get_async_param_deprecation(self):
        """
        L{twisted.python.compat._get_async_param} raises a deprecation
        warning if async keyword argument is passed.
        """
        self.assertEqual(
            _get_async_param(isAsync=None, **{'async': False}), False)
        currentWarnings = self.flushWarnings(
            offendingFunctions=[self.test_get_async_param_deprecation])
        self.assertEqual(
            currentWarnings[0]['message'],
            "'async' keyword argument is deprecated, please use isAsync")

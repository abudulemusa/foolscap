
import sets, re
from twisted.trial import unittest
from foolscap import schema, copyable, broker
from foolscap.tokens import Violation, InvalidRemoteInterface
from foolscap.constraint import IConstraint
from foolscap.remoteinterface import RemoteMethodSchema, \
     RemoteInterfaceConstraint, LocalInterfaceConstraint
from foolscap.referenceable import RemoteReferenceTracker, \
     RemoteReference, Referenceable, TubRef
from foolscap.test import common

have_builtin_set = False
try:
    set
    have_builtin_set = True
except NameError:
    pass # oh well

class Dummy:
    pass

HEADER = 64
INTSIZE = HEADER+1
STR10 = HEADER+1+10

class ConformTest(unittest.TestCase):
    """This tests how Constraints are asserted on outbound objects (where the
    object already exists). Inbound constraints are checked in
    test_banana.InboundByteStream in the various testConstrainedFoo methods.
    """
    def conforms(self, c, obj):
        c.checkObject(obj, False)
    def violates(self, c, obj):
        self.assertRaises(schema.Violation, c.checkObject, obj, False)

    def testInteger(self):
        # s_int32_t
        c = schema.IntegerConstraint()
        self.conforms(c, 123)
        self.violates(c, 2**64)
        self.conforms(c, 0)
        self.conforms(c, 2**31-1)
        self.violates(c, 2**31)
        self.conforms(c, -2**31)
        self.violates(c, -2**31-1)
        self.violates(c, "123")
        self.violates(c, Dummy())
        self.violates(c, None)

    def testLargeInteger(self):
        c = schema.IntegerConstraint(64)
        self.conforms(c, 123)
        self.violates(c, "123")
        self.violates(c, None)
        self.conforms(c, 2**512-1)
        self.violates(c, 2**512)
        self.conforms(c, -2**512+1)
        self.violates(c, -2**512)

    def testByteString(self):
        c = schema.ByteStringConstraint(10)
        self.conforms(c, "I'm short")
        self.violates(c, "I am too long")
        self.conforms(c, "a" * 10)
        self.violates(c, "a" * 11)
        self.violates(c, 123)
        self.violates(c, Dummy())
        self.violates(c, None)

        c2 = schema.ByteStringConstraint(15, 10)
        self.violates(c2, "too short")
        self.conforms(c2, "long enough")
        self.violates(c2, "this is too long")
        self.violates(c2, u"I am unicode")

        c3 = schema.ByteStringConstraint(regexp="needle")
        self.violates(c3, "no present")
        self.conforms(c3, "needle in a haystack")
        c4 = schema.ByteStringConstraint(regexp="[abc]+")
        self.violates(c4, "spelled entirely without those letters")
        self.conforms(c4, "add better cases")
        c5 = schema.ByteStringConstraint(regexp=re.compile("\d+\s\w+"))
        self.conforms(c5, ": 123 boo")
        self.violates(c5, "more than 1  spaces")
        self.violates(c5, "letters first 123")

    def testString(self):
        # this test will change once the definition of "StringConstraint"
        # changes. For now, we assert that StringConstraint is the same as
        # ByteStringConstraint.

        c = schema.StringConstraint(20)
        self.conforms(c, "I'm short")
        self.violates(c, u"I am unicode")

    def testUnicode(self):
        c = schema.UnicodeConstraint(10)
        self.violates(c, "I'm a bytestring")
        self.conforms(c, u"I'm short")
        self.violates(c, u"I am too long")
        self.conforms(c, u"a" * 10)
        self.violates(c, u"a" * 11)
        self.violates(c, 123)
        self.violates(c, Dummy())
        self.violates(c, None)

        c2 = schema.UnicodeConstraint(15, 10)
        self.violates(c2, "I'm a bytestring")
        self.violates(c2, u"too short")
        self.conforms(c2, u"long enough")
        self.violates(c2, u"this is too long")

        c3 = schema.UnicodeConstraint(regexp="needle")
        self.violates(c3, "I'm a bytestring")
        self.violates(c3, u"no present")
        self.conforms(c3, u"needle in a haystack")
        c4 = schema.UnicodeConstraint(regexp="[abc]+")
        self.violates(c4, "I'm a bytestring")
        self.violates(c4, u"spelled entirely without those letters")
        self.conforms(c4, u"add better cases")
        c5 = schema.UnicodeConstraint(regexp=re.compile("\d+\s\w+"))
        self.violates(c5, "I'm a bytestring")
        self.conforms(c5, u": 123 boo")
        self.violates(c5, u"more than 1  spaces")
        self.violates(c5, u"letters first 123")

    def testBool(self):
        c = schema.BooleanConstraint()
        self.conforms(c, False)
        self.conforms(c, True)
        self.violates(c, 0)
        self.violates(c, 1)
        self.violates(c, "vrai")
        self.violates(c, Dummy())
        self.violates(c, None)

    def testPoly(self):
        c = schema.PolyConstraint(schema.ByteStringConstraint(100),
                                  schema.IntegerConstraint())
        self.conforms(c, "string")
        self.conforms(c, 123)
        self.violates(c, u"unicode")
        self.violates(c, 123.4)
        self.violates(c, ["not", "a", "list"])

    def testTuple(self):
        c = schema.TupleConstraint(schema.ByteStringConstraint(10),
                                   schema.ByteStringConstraint(100),
                                   schema.IntegerConstraint() )
        self.conforms(c, ("hi", "there buddy, you're number", 1))
        self.violates(c, "nope")
        self.violates(c, ("string", "string", "NaN"))
        self.violates(c, ("string that is too long", "string", 1))
        self.violates(c, ["Are tuples", "and lists the same?", 0])

    def testNestedTuple(self):
        inner = schema.TupleConstraint(schema.ByteStringConstraint(10),
                                       schema.IntegerConstraint())
        outer = schema.TupleConstraint(schema.ByteStringConstraint(100),
                                       inner)

        self.conforms(inner, ("hi", 2))
        self.conforms(outer, ("long string here", ("short", 3)))
        self.violates(outer, (("long string here", ("short", 3, "extra"))))
        self.violates(outer, (("long string here", ("too long string", 3))))

        outer2 = schema.TupleConstraint(inner, inner)
        self.conforms(outer2, (("hi", 1), ("there", 2)) )
        self.violates(outer2, ("hi", 1, "flat", 2) )

    def testRecursion(self):
        # we have to fiddle with PolyConstraint's innards
        value = schema.ChoiceOf(schema.ByteStringConstraint(),
                                schema.IntegerConstraint(),
                                # will add 'value' here
                                )
        self.conforms(value, "key")
        self.conforms(value, 123)
        self.violates(value, [])

        mapping = schema.TupleConstraint(schema.ByteStringConstraint(10),
                                         value)
        self.conforms(mapping, ("name", "key"))
        self.conforms(mapping, ("name", 123))
        value.alternatives = value.alternatives + (mapping,)

        # but note that the constraint can still be applied
        self.conforms(mapping, ("name", 123))
        self.conforms(mapping, ("name", "key"))
        self.conforms(mapping, ("name", ("key", "value")))
        self.conforms(mapping, ("name", ("key", 123)))
        self.violates(mapping, ("name", ("key", [])))
        l = []
        l.append(l)
        self.violates(mapping, ("name", l))

    def testList(self):
        l = schema.ListOf(schema.ByteStringConstraint(10))
        self.conforms(l, ["one", "two", "three"])
        self.violates(l, ("can't", "fool", "me"))
        self.violates(l, ["but", "perspicacity", "is too long"])
        self.violates(l, [0, "numbers", "allowed"])
        self.conforms(l, ["short", "sweet"])

        l2 = schema.ListOf(schema.ByteStringConstraint(10), 3)
        self.conforms(l2, ["the number", "shall be", "three"])
        self.violates(l2, ["five", "is", "...", "right", "out"])

        l3 = schema.ListOf(schema.ByteStringConstraint(10), None)
        self.conforms(l3, ["long"] * 35)
        self.violates(l3, ["number", 1, "rule", "is", 0, "numbers"])

        l4 = schema.ListOf(schema.ByteStringConstraint(10), 3, 3)
        self.conforms(l4, ["three", "is", "good"])
        self.violates(l4, ["but", "four", "is", "bad"])
        self.violates(l4, ["two", "too"])

    def testSet(self):
        l = schema.SetOf(schema.IntegerConstraint(), 3)
        self.conforms(l, sets.Set([]))
        self.conforms(l, sets.Set([1]))
        self.conforms(l, sets.Set([1,2,3]))
        self.violates(l, sets.Set([1,2,3,4]))
        self.violates(l, sets.Set(["not a number"]))
        self.conforms(l, sets.ImmutableSet([]))
        self.conforms(l, sets.ImmutableSet([1]))
        self.conforms(l, sets.ImmutableSet([1,2,3]))
        self.violates(l, sets.ImmutableSet([1,2,3,4]))
        self.violates(l, sets.ImmutableSet(["not a number"]))
        if have_builtin_set:
            self.conforms(l, set([]))
            self.conforms(l, set([1]))
            self.conforms(l, set([1,2,3]))
            self.violates(l, set([1,2,3,4]))
            self.violates(l, set(["not a number"]))
            self.conforms(l, frozenset([]))
            self.conforms(l, frozenset([1]))
            self.conforms(l, frozenset([1,2,3]))
            self.violates(l, frozenset([1,2,3,4]))
            self.violates(l, frozenset(["not a number"]))

        l = schema.SetOf(schema.IntegerConstraint(), 3, True)
        self.conforms(l, sets.Set([]))
        self.conforms(l, sets.Set([1]))
        self.conforms(l, sets.Set([1,2,3]))
        self.violates(l, sets.Set([1,2,3,4]))
        self.violates(l, sets.Set(["not a number"]))
        self.violates(l, sets.ImmutableSet([]))
        self.violates(l, sets.ImmutableSet([1]))
        self.violates(l, sets.ImmutableSet([1,2,3]))
        self.violates(l, sets.ImmutableSet([1,2,3,4]))
        self.violates(l, sets.ImmutableSet(["not a number"]))
        if have_builtin_set:
            self.conforms(l, set([]))
            self.conforms(l, set([1]))
            self.conforms(l, set([1,2,3]))
            self.violates(l, set([1,2,3,4]))
            self.violates(l, set(["not a number"]))
            self.violates(l, frozenset([]))
            self.violates(l, frozenset([1]))
            self.violates(l, frozenset([1,2,3]))
            self.violates(l, frozenset([1,2,3,4]))
            self.violates(l, frozenset(["not a number"]))

        l = schema.SetOf(schema.IntegerConstraint(), 3, False)
        self.violates(l, sets.Set([]))
        self.violates(l, sets.Set([1]))
        self.violates(l, sets.Set([1,2,3]))
        self.violates(l, sets.Set([1,2,3,4]))
        self.violates(l, sets.Set(["not a number"]))
        self.conforms(l, sets.ImmutableSet([]))
        self.conforms(l, sets.ImmutableSet([1]))
        self.conforms(l, sets.ImmutableSet([1,2,3]))
        self.violates(l, sets.ImmutableSet([1,2,3,4]))
        self.violates(l, sets.ImmutableSet(["not a number"]))
        if have_builtin_set:
            self.violates(l, set([]))
            self.violates(l, set([1]))
            self.violates(l, set([1,2,3]))
            self.violates(l, set([1,2,3,4]))
            self.violates(l, set(["not a number"]))
            self.conforms(l, frozenset([]))
            self.conforms(l, frozenset([1]))
            self.conforms(l, frozenset([1,2,3]))
            self.violates(l, frozenset([1,2,3,4]))
            self.violates(l, frozenset(["not a number"]))


    def testDict(self):
        d = schema.DictOf(schema.ByteStringConstraint(10),
                          schema.IntegerConstraint(),
                          maxKeys=4)

        self.conforms(d, {"a": 1, "b": 2})
        self.conforms(d, {"foo": 123, "bar": 345, "blah": 456, "yar": 789})
        self.violates(d, None)
        self.violates(d, 12)
        self.violates(d, ["nope"])
        self.violates(d, ("nice", "try"))
        self.violates(d, {1:2, 3:4})
        self.violates(d, {"a": "b"})
        self.violates(d, {"a": 1, "b": 2, "c": 3, "d": 4, "toomuch": 5})

    def testAttrDict(self):
        d = copyable.AttributeDictConstraint(('a', int), ('b', str))
        self.conforms(d, {"a": 1, "b": "string"})
        self.violates(d, {"a": 1, "b": 2})
        self.violates(d, {"a": 1, "b": "string", "c": "is a crowd"})

        d = copyable.AttributeDictConstraint(('a', int), ('b', str),
                                             ignoreUnknown=True)
        self.conforms(d, {"a": 1, "b": "string"})
        self.violates(d, {"a": 1, "b": 2})
        self.conforms(d, {"a": 1, "b": "string", "c": "is a crowd"})

        d = copyable.AttributeDictConstraint(attributes={"a": int, "b": str})
        self.conforms(d, {"a": 1, "b": "string"})
        self.violates(d, {"a": 1, "b": 2})
        self.violates(d, {"a": 1, "b": "string", "c": "is a crowd"})


class CreateTest(unittest.TestCase):
    def check(self, obj, expected):
        self.failUnless(isinstance(obj, expected))

    def testMakeConstraint(self):
        make = IConstraint
        c = make(int)
        self.check(c, schema.IntegerConstraint)
        self.failUnlessEqual(c.maxBytes, -1)

        c = make(str)
        self.check(c, schema.ByteStringConstraint)
        self.failUnlessEqual(c.maxLength, None)

        c = make(schema.ByteStringConstraint(2000))
        self.check(c, schema.ByteStringConstraint)
        self.failUnlessEqual(c.maxLength, 2000)

        c = make(unicode)
        self.check(c, schema.UnicodeConstraint)
        self.failUnlessEqual(c.maxLength, None)

        self.check(make(bool), schema.BooleanConstraint)
        self.check(make(float), schema.NumberConstraint)

        self.check(make(schema.NumberConstraint()), schema.NumberConstraint)
        c = make((int, str))
        self.check(c, schema.TupleConstraint)
        self.check(c.constraints[0], schema.IntegerConstraint)
        self.check(c.constraints[1], schema.ByteStringConstraint)

        c = make(common.RIHelper)
        self.check(c, RemoteInterfaceConstraint)
        self.failUnlessEqual(c.interface, common.RIHelper)

        c = make(common.IFoo)
        self.check(c, LocalInterfaceConstraint)
        self.failUnlessEqual(c.interface, common.IFoo)

        c = make(Referenceable)
        self.check(c, RemoteInterfaceConstraint)
        self.failUnlessEqual(c.interface, None)


class Arguments(unittest.TestCase):
    def test_arguments(self):
        def foo(a=int, b=bool, c=int): return str
        r = RemoteMethodSchema(method=foo)
        getpos = r.getPositionalArgConstraint
        getkw = r.getKeywordArgConstraint
        self.failUnless(isinstance(getpos(0)[1], schema.IntegerConstraint))
        self.failUnless(isinstance(getpos(1)[1], schema.BooleanConstraint))
        self.failUnless(isinstance(getpos(2)[1], schema.IntegerConstraint))

        self.failUnless(isinstance(getkw("a")[1], schema.IntegerConstraint))
        self.failUnless(isinstance(getkw("b")[1], schema.BooleanConstraint))
        self.failUnless(isinstance(getkw("c")[1], schema.IntegerConstraint))

        self.failUnless(isinstance(r.getResponseConstraint(),
                                   schema.ByteStringConstraint))

        self.failUnless(isinstance(getkw("c", 1, [])[1],
                                   schema.IntegerConstraint))
        self.failUnlessRaises(schema.Violation, getkw, "a", 1, [])
        self.failUnlessRaises(schema.Violation, getkw, "b", 1, ["b"])
        self.failUnlessRaises(schema.Violation, getkw, "a", 2, [])
        self.failUnless(isinstance(getkw("c", 2, [])[1],
                                   schema.IntegerConstraint))
        self.failUnless(isinstance(getkw("c", 0, ["a", "b"])[1],
                                   schema.IntegerConstraint))

        try:
            r.checkAllArgs((1,True,2), {}, False)
            r.checkAllArgs((), {"a":1, "b":False, "c":2}, False)
            r.checkAllArgs((1,), {"b":False, "c":2}, False)
            r.checkAllArgs((1,True), {"c":3}, False)
            r.checkResults("good", False)
        except schema.Violation:
            self.fail("that shouldn't have raised a Violation")
        self.failUnlessRaises(schema.Violation, # 2 is not bool
                              r.checkAllArgs, (1,2,3), {}, False)
        self.failUnlessRaises(schema.Violation, # too many
                              r.checkAllArgs, (1,True,3,4), {}, False)
        self.failUnlessRaises(schema.Violation, # double "a"
                              r.checkAllArgs, (1,), {"a":1, "b":True, "c": 3},
                              False)
        self.failUnlessRaises(schema.Violation, # missing required "b"
                              r.checkAllArgs, (1,), {"c": 3}, False)
        self.failUnlessRaises(schema.Violation, # missing required "a"
                              r.checkAllArgs, (), {"b":True, "c": 3}, False)
        self.failUnlessRaises(schema.Violation,
                              r.checkResults, 12, False)

    def test_bad_arguments(self):
        def foo(nodefault): return str
        self.failUnlessRaises(InvalidRemoteInterface,
                              RemoteMethodSchema, method=foo)
        def bar(nodefault, a=int): return str
        self.failUnlessRaises(InvalidRemoteInterface,
                              RemoteMethodSchema, method=bar)


class Interfaces(unittest.TestCase):
    def check_inbound(self, obj, constraint):
        try:
            constraint.checkObject(obj, True)
        except Violation, f:
            self.fail("constraint was violated: %s" % f)

    def check_outbound(self, obj, constraint):
        try:
            constraint.checkObject(obj, False)
        except Violation, f:
            self.fail("constraint was violated: %s" % f)

    def violates_inbound(self, obj, constraint):
        try:
            constraint.checkObject(obj, True)
        except Violation:
            return
        self.fail("constraint wasn't violated")

    def violates_outbound(self, obj, constraint):
        try:
            constraint.checkObject(obj, False)
        except Violation:
            return
        self.fail("constraint wasn't violated")

    def test_referenceable(self):
        h = common.HelperTarget()
        c1 = RemoteInterfaceConstraint(common.RIHelper)
        c2 = RemoteInterfaceConstraint(common.RIMyTarget)
        self.violates_inbound("bogus", c1)
        self.violates_outbound("bogus", c1)
        self.check_outbound(h, c1)
        self.violates_inbound(h, c1)
        self.violates_inbound(h, c2)
        self.violates_outbound(h, c2)

    def test_remotereference(self):
        # we need to create a fake RemoteReference here
        tracker = RemoteReferenceTracker(broker.Broker(TubRef("fake-tubid")),
                                         0, None,
                                         common.RIHelper.__remote_name__)
        rr = RemoteReference(tracker)

        c1 = RemoteInterfaceConstraint(common.RIHelper)
        self.check_inbound(rr, c1)
        self.check_outbound(rr, c1) # gift

        c2 = RemoteInterfaceConstraint(common.RIMyTarget)
        self.violates_inbound(rr, c2)
        self.violates_outbound(rr, c2)


# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""
This module represents flavors of remotely acessible objects.

Currently this is only objects accessible through Perspective Broker, but will
hopefully encompass all forms of remote access which can emulate subsets of PB
(such as XMLRPC or SOAP).

"""

# system imports
import types

# twisted imports
from twisted.python import log

# sibling imports
from jelly import setUnjellyableForClass, setUnjellyableForClassTree, unjellyableRegistry
from jelly import Jellyable, Unjellyable, _Dummy
from jelly import setInstanceState, getInstanceState
# compatibility
setCopierForClass = setUnjellyableForClass
setCopierForClassTree = setUnjellyableForClassTree
copyTags = unjellyableRegistry

copy_atom = "copy"
cache_atom = "cache"
cached_atom = "cached"
remote_atom = "remote"



class Serializable(Jellyable):
    """An object that can be passed remotely.

    I am a style of object which can be serialized by Perspective
    Broker.  Objects which wish to be referenceable or copied remotely
    have to subclass Serializable.  However, clients of Perspective
    Broker will probably not want to directly subclass Serializable; the
    Flavors of transferable objects are listed below.

    What it means to be \"Serializable\" is that an object can be
    passed to or returned from a remote method.  Certain basic types
    (dictionaries, lists, tuples, numbers, strings) are serializable by
    default; however, classes need to choose a specific serialization
    style: Referenceable, Viewable, Copyable or Cacheable.

    You may also pass [lists, dictionaries, tuples] of Serializable
    instances to or return them from remote methods, as many levels deep
    as you like.
    """

    def processUniqueID(self):
        """Return an ID which uniquely represents this object for this process.

        By default, this uses the 'id' builtin, but can be overridden to
        indicate that two values are identity-equivalent (such as proxies
        for the same object).
        """

        return id(self)

class Referenceable(Serializable):
    perspective = None
    """I am an object sent remotely as a direct reference.

    When one of my subclasses is sent as an argument to or returned
    from a remote method call, I will be serialized by default as a
    direct reference.

    This means that the peer will be able to call methods on me;
    a method call xxx() from my peer will be resolved to methods
    of the name remote_xxx.
    """

    def remoteMessageReceived(self, broker, message, args, kw):
        """A remote message has been received.  Dispatch it appropriately.

        The default implementation is to dispatch to a method called
        'remote_messagename' and call it with the same arguments.
        """
        args = broker.unserialize(args)
        kw = broker.unserialize(kw)
        method = getattr(self, "remote_%s" % message)
        try:
            state = apply(method, args, kw)
        except TypeError:
            print ("%s didn't accept %s and %s" % (method, args, kw))
            raise
        return broker.serialize(state, self.perspective)

    def jellyFor(self, jellier):
        """(internal)

        Return a tuple which will be used as the s-expression to
        serialize this to a peer.
        """

        return "remote", jellier.invoker.registerReference(self)


class Root(Referenceable):
    """I provide a root object to Brokers for a BrokerFactory.

    When a BrokerFactory produces a Broker, it supplies that Broker
    with an object named "root".  That object is obtained by calling
    my rootObject method.

    See also: getObjectAt
    """

    def rootObject(self, broker):
        """A BrokerFactory is requesting to publish me as a root object.

        When a BrokerFactory is sending me as the root object, this
        method will be invoked to allow per-broker versions of an
        object.  By default I return myself.
        """
        return self

class ViewPoint(Referenceable):
    """I act as an indirect reference to an object accessed through a Perspective.

    Simply put, I combine an object with a perspective so that when a
    peer calls methods on the object I refer to, the method will be
    invoked with that perspective as a first argument, so that it can
    know who is calling it.

    While Viewable objects will be converted to ViewPoints by default
    when they are returned from or sent as arguments to a remote
    method, any object may be manually proxied as well. (XXX: Now that
    this class is no longer named Proxy, this is the only occourance
    of the term 'proxied' in this docstring, and may be unclear.)

    This can be useful when dealing with Perspectives, Copyables,
    and Cacheables.  It is legal to implement a method as such on
    a perspective::

     | def perspective_getViewPointForOther(self, name):
     |     defr = self.service.getPerspectiveRequest(name)
     |     defr.addCallbacks(lambda x, self=self: ViewPoint(self, x), log.msg)
     |     return defr

    This will allow you to have references to Perspective objects in two
    different ways.  One is through the initial 'attach' call -- each
    peer will have a RemoteReference to their perspective directly.  The
    other is through this method; each peer can get a RemoteReference to
    all other perspectives in the service; but that RemoteReference will
    be to a ViewPoint, not directly to the object.

    The practical offshoot of this is that you can implement 2 varieties
    of remotely callable methods on this Perspective; view_xxx and
    perspective_xxx. view_xxx methods will follow the rules for
    ViewPoint methods (see ViewPoint.remoteMessageReceived), and
    perspective_xxx methods will follow the rules for Perspective
    methods.
    """

    def __init__(self, perspective, object):
        """Initialize me with a Perspective and an Object.
        """
        self.perspective = perspective
        self.object = object

    def processUniqueID(self):
        """Return an ID unique to a proxy for this perspective+object combination.
        """
        return (id(self.perspective), id(self.object))

    def remoteMessageReceived(self, broker, message, args, kw):
        """A remote message has been received.  Dispatch it appropriately.

        The default implementation is to dispatch to a method called
        'view_messagename' to my Object and call it on my object with
        the same arguments, modified by inserting my Perspective as
        the first argument.
        """
        args = broker.unserialize(args, self.perspective)
        kw = broker.unserialize(kw, self.perspective)
        method = getattr(self.object, "view_%s" % message)
        try:
            state = apply(method, (self.perspective,)+args, kw)
        except TypeError:
            print ("%s didn't accept %s and %s" % (method, args, kw))
            raise
        rv = broker.serialize(state, self.perspective, method, args, kw)
        return rv


class Viewable(Serializable):
    """I will be converted to a ViewPoint when passed to or returned from a remote method.

    The beginning of a peer's interaction with a PB Service is always
    through a perspective.  However, if a perspective_xxx method returns
    a Viewable, it will be serialized to the peer as a response to that
    method.
    """

    def jellyFor(self, jellier):
        """Serialize a ViewPoint for me and the perspective of the given broker.
        """
        return ViewPoint(jellier.invoker.serializingPerspective, self).jellyFor(jellier)



class Copyable(Serializable):
    """Subclass me to get copied each time you are returned from or passed to a remote method.

    When I am returned from or passed to a remote method call, I will be
    converted into data via a set of callbacks (see my methods for more
    info).  That data will then be serialized using Jelly, and sent to
    the peer.

    The peer will then look up the type to represent this with; see
    RemoteCopy for details.
    """

    def getStateToCopy(self):
        """Gather state to send when I am serialized for a peer.

        I will default to returning self.__dict__.  Override this to
        customize this behavior.
        """

        return self.__dict__

    def getStateToCopyFor(self, perspective):
        """Gather state to send when I am serialized for a particular perspective.

        I will default to calling getStateToCopy.  Override this to
        customize this behavior.
        """

        return self.getStateToCopy()

    def getTypeToCopy(self):
        """Determine what type tag to send for me.

        By default, send the string representation of my class
        (package.module.Class); normally this is adequate, but
        you may override this to change it.
        """

        return str(self.__class__)

    def getTypeToCopyFor(self, perspective):
        """Determine what type tag to send for me.

        By default, defer to self.getTypeToCopy() normally this is
        adequate, but you may override this to change it.
        """

        return self.getTypeToCopy()

    def jellyFor(self, jellier):
        """Assemble type tag and state to copy for this broker.

        This will call getTypeToCopyFor and getStateToCopy, and
        return an appropriate s-expression to represent me.
        """

        if jellier.invoker is None:
            return getInstanceState(self, jellier)
        p = jellier.invoker.serializingPerspective
        return (self.getTypeToCopyFor(p),
                jellier.jelly(self.getStateToCopyFor(p)))


class Cacheable(Copyable):
    """A cached instance.

    This means that it's copied; but there is some logic to make sure
    that it's only copied once.  Additionally, when state is retrieved,
    it is passed a "proto-reference" to the state as it will exist on
    the client.

    XXX: The documentation for this class needs work, but it's the most
    complex part of PB and it is inherently difficult to explain.
    """

    def getStateToCacheAndObserveFor(self, perspective, observer):
        """Get state to cache on the client and client-cache reference to observe locally.

        This is similiar to getStateToCopyFor, but it additionally
        passes in a reference to the client-side RemoteCache instance
        that will be created when it is unserialized.  This allows
        Cacheable instances to keep their RemoteCaches up to date when
        they change, such that no changes can occurr between the point
        at which the state is initially copied and the client receives
        it that are not propogated.
        """

        return self.getStateToCopyFor(perspective)

    def jellyFor(self, jellier):
        """Return an appropriate tuple to serialize me.

        Depending on whether this broker has cached me or not, this may
        return either a full state or a reference to an existing cache.
        """
        if jellier.invoker is None:
            return getInstanceState(self, jellier)
        luid = jellier.invoker.cachedRemotelyAs(self, 1)
        if luid is None:
            luid = jellier.invoker.cacheRemotely(self)
            p = jellier.invoker.serializingPerspective
            type_ = self.getTypeToCopyFor(p)
            observer = RemoteCacheObserver(jellier.invoker, self, p)
            state = self.getStateToCacheAndObserveFor(p, observer)
            l = jellier.prepare(self)
            jstate = jellier.jelly(state)
            l.extend([type_, luid, jstate])
            return jellier.preserve(self, l)
        else:
            return cached_atom, luid

    def stoppedObserving(self, perspective, observer):
        """This method is called when a client has stopped observing me.

        The 'observer' argument is the same as that passed in to
        getStateToCacheAndObserveFor.
        """



class RemoteCopy(Unjellyable):
    """I am a remote copy of a Copyable object.

    When the state from a Copyable object is received, an instance will
    be created based on the copy tags table (see setCopierForClass) and
    sent the setCopyableState message.  I provide a reasonable default
    implementation of that message; subclass me if you wish to serve as
    a copier for remote data.

    NOTE: copiers are invoked with no arguments.  Do not implement a
    constructor which requires args in a subclass of RemoteCopy!
    """

    def setCopyableState(self, state):
        """I will be invoked with the state to copy locally.

        'state' is the data returned from the remote object's
        'getStateToCopyFor' method, which will often be the remote
        object's dictionary (or a filtered approximation of it depending
        on my peer's perspective).
        """

        self.__dict__ = state

    def unjellyFor(self, unjellier, jellyList):
        if unjellier.invoker is None:
            return setInstanceState(self, unjellier, jellyList)
        self.setCopyableState(unjellier.unjelly(jellyList[1]))
        return self
           


class RemoteCache(RemoteCopy, Serializable):
    """A cache is a local representation of a remote Cacheable object.

    This represents the last known state of this object.  It may
    also have methods invoked on it -- in order to update caches,
    the cached class generates a RemoteReference to this object as
    it is originally sent.

    Much like copy, I will be invoked with no arguments.  Do not
    implement a constructor that requires arguments in one of my
    subclasses.
    """

    def remoteMessageReceived(self, broker, message, args, kw):
        """A remote message has been received.  Dispatch it appropriately.

        The default implementation is to dispatch to a method called
        'observe_messagename' and call it on my  with the same arguments.
        """

        args = broker.unserialize(args)
        kw = broker.unserialize(kw)
        method = getattr(self, "observe_%s" % message)
        try:
            state = apply(method, args, kw)
        except TypeError:
            print ("%s didn't accept %s and %s" % (method, args, kw))
            raise
        return broker.serialize(state, None, method, args, kw)

    def jellyFor(self, jellier):
        """serialize me (only for the broker I'm for) as the original cached reference
        """
        if jellier.invoker is None:
            return getInstanceState(self, jellier)
        assert jellier.invoker is self.broker, "You cannot exchange cached proxies between brokers."
        return 'lcache', self.luid


    def unjellyFor(self, unjellier, jellyList):
        if unjellier.invoker is None:
            return setInstanceState(self, unjellier, jellyList)
        self.broker = unjellier.invoker
        self.luid = jellyList[1]
        cProxy = _Dummy()
        cProxy.__class__ = self.__class__
        cProxy.__dict__ = self.__dict__
        # XXX questionable whether this was a good design idea...
        init = getattr(cProxy, "__init__", None)
        if init:
            init()
        unjellier.invoker.cacheLocally(jellyList[1], self)
        cProxy.setCopyableState(unjellier.unjelly(jellyList[2]))
        # Might have changed due to setCopyableState method; we'll assume that
        # it's bad form to do so afterwards.
        self.__dict__ = cProxy.__dict__
        # chomp, chomp -- some existing code uses "self.__dict__ =", some uses
        # "__dict__.update".  This is here in order to handle both cases.
        self.broker = unjellier.invoker
        self.luid = jellyList[1]
        return cProxy
    
    def __really_del__(self):
        """Final finalization call, made after all remote references have been lost.
        """

    def __cmp__(self, other):
        """Compare me [to another RemoteCache.
        """
        if isinstance(other, self.__class__):
            return cmp(id(self.__dict__), id(other.__dict__))
        else:
            return cmp(id(self.__dict__), other)

    def __hash__(self):
        """Hash me.
        """
        return id(self.__dict__)

    broker = None
    luid = None

    def __del__(self):
        """Do distributed reference counting on finalize.
        """
        try:
            # log.msg( ' --- decache: %s %s' % (self, self.luid) )
            if self.broker:
                self.broker.decCacheRef(self.luid)
        except:
            log.deferr()

def unjellyCached(unjellier, unjellyList):
    luid = unjellyList[1]
    cNotProxy = unjellier.invoker.cachedLocallyAs(luid)

    cProxy = _Dummy()
    cProxy.__class__ = cNotProxy.__class__
    cProxy.__dict__ = cNotProxy.__dict__
    return cProxy

setUnjellyableForClass("cached", unjellyCached)

def unjellyLCache(unjellier, unjellyList):
    luid = unjellyList[1]
    obj = unjellier.invoker.remotelyCachedForLUID(luid)
    return obj

setUnjellyableForClass("lcache", unjellyLCache)

def unjellyLocal(unjellier, unjellyList):
    obj = unjellier.invoker.localObjectForID(unjellyList[1])
    return obj
    
setUnjellyableForClass("local", unjellyLocal)

class RemoteCacheMethod:
    """A method on a reference to a RemoteCache.
    """

    def __init__(self, name, broker, cached, perspective):
        """(internal) initialize.
        """
        self.name = name
        self.broker = broker
        self.perspective = perspective
        self.cached = cached

    def __cmp__(self, other):
        return cmp((self.name, self.broker, self.perspective, self.cached), other)

    def __hash__(self):
        return hash((self.name, self.broker, self.perspective, self.cached))

    def __call__(self, *args, **kw):
        """(internal) action method.
        """
        cacheID = self.broker.cachedRemotelyAs(self.cached)
        if cacheID is None:
            from pb import ProtocolError
            raise ProtocolError("You can't call a cached method when the object hasn't been given to the peer yet.")
        return self.broker._sendMessage('cache', self.perspective, cacheID, self.name, args, kw)

class RemoteCacheObserver:
    """I am a reverse-reference to the peer's RemoteCache.

    I am generated automatically when a cache is serialized.  I
    represent a reference to the client's RemoteCache object that
    will represent a particular Cacheable; I am the additional
    object passed to getStateToCacheAndObserveFor.
    """

    def __init__(self, broker, cached, perspective):
        """Initialize me pointing at a client side cache for a particular broker/perspective.
        """

        self.broker = broker
        self.cached = cached
        self.perspective = perspective

    def __repr__(self):
        return "<RemoteCacheObserver(%s, %s, %s) at %s>" % (
            self.broker, self.cached, self.perspective, id(self))

    def __hash__(self):
        """generate a hash unique to all RemoteCacheObservers for this broker/perspective/cached triplet
        """

        return (  (hash(self.broker) % 2**10)
                + (hash(self.perspective) % 2**10)
                + (hash(self.cached) % 2**10))

    def __cmp__(self, other):
        """compare me to another RemoteCacheObserver
        """

        return cmp((self.broker, self.perspective, self.cached), other)

    def callRemote(self, name, *args, **kw):
        """(internal) action method.
        """
        cacheID = self.broker.cachedRemotelyAs(self.cached)
        if cacheID is None:
            from pb import ProtocolError
            raise ProtocolError("You can't call a cached method when the object hasn't been given to the peer yet.")
        return self.broker._sendMessage('cache', self.perspective, cacheID, name, args, kw)

    def remoteMethod(self, key):
        """Get a RemoteMethod for this key.
        """
        return RemoteCacheMethod(key, self.broker, self.cached, self.perspective)

import asyncio
import time
import types
from aiostream.stream import zip
from .base import _wrap, FunctionWrapper, Foo, Const


def Timer(foo_or_val, kwargs=None, interval=1, repeat=0):
    '''Streaming wrapper to repeat a value or calls to a function

    Arguments:
        foo_or_val (any): function to call or value to return
        kwargs (dict): kwargs for foo_or_val if its a function
        interval (int): time between queries
        repeat (int): number of times to repeat
    Returns:
        FunctionWrapper: a streaming wrapper
    '''
    kwargs = kwargs or {}
    if not isinstance(foo_or_val, types.FunctionType):
        foo = Const(foo_or_val)
    else:
        foo = Foo(foo_or_val, kwargs)

    async def _repeater(foo, repeat, interval):
        while repeat > 0:
            t1 = time.time()
            yield foo()
            t2 = time.time()
            if interval > 0:
                # sleep for rest of time that _p didnt take
                await asyncio.sleep(max(0, interval - (t2 - t1)))
            repeat -= 1

    return _wrap(_repeater, dict(foo=foo, repeat=repeat, interval=interval), name='Timer', wraps=(foo,), share=foo)


def Delay(f_wrap, kwargs=None, delay=1):
    '''Streaming wrapper to delay a stream

    Arguments:
        f_wrap (callable): input stream
        kwargs (dict): kwargs for input stream
        delay (float): time to delay input stream
    Returns:
        FunctionWrapper: a streaming wrapper
    '''
    if not isinstance(f_wrap, FunctionWrapper):
        f_wrap = Foo(f_wrap, kwargs or {})

    async def _delay(f_wrap, delay):
        async for f in f_wrap():
            yield f
            await asyncio.sleep(delay)

    return _wrap(_delay, dict(f_wrap=f_wrap, delay=delay), name='Delay', wraps=(f_wrap,), share=f_wrap)


def State(foo, foo_kwargs=None, **state):
    '''Streaming wrapper to maintain state

    Arguments:
        foo (callable): input stream
        foo_kwargs (dict): kwargs for input stream
        state (dict): state dictionary of values to hold
    Returns:
        FunctionWrapper: a streaming wrapper
    '''
    foo_kwargs = foo_kwargs or {}
    foo = _wrap(foo, foo_kwargs, name=foo.__name__, wraps=(foo,), state=state)
    return foo


def Apply(foo, f_wrap, foo_kwargs=None):
    '''Streaming wrapper to apply a function to an input stream

    Arguments:
        foo (callable): function to apply
        f_wrap (callable): input stream
        foo_kwargs (dict): kwargs for function
    Returns:
        FunctionWrapper: a streaming wrapper
    '''
    if not isinstance(f_wrap, FunctionWrapper):
        raise Exception('Apply expects a tributary')
    foo_kwargs = foo_kwargs or {}
    foo = Foo(foo, foo_kwargs)
    foo._wraps = foo._wraps + (f_wrap, )

    async def _apply(foo):
        async for f in f_wrap():
            item = foo(f)
            if isinstance(item, types.AsyncGeneratorType):
                async for i in item:
                    yield i
            elif isinstance(item, types.CoroutineType):
                yield await item
            else:
                yield item
    return _wrap(_apply, dict(foo=foo), name='Apply', wraps=(foo,), share=foo)


def Window(foo, foo_kwargs=None, size=-1, full_only=True):
    foo_kwargs = foo_kwargs or {}
    foo = Foo(foo, foo_kwargs)

    accum = []

    async def _window(foo, size, full_only, accum):
        async for x in foo():
            if size == 0:
                yield x
            else:
                accum.append(x)

                if size > 0:
                    accum = accum[-size:]
                if full_only:
                    if len(accum) == size or size == -1:
                        yield accum
                else:
                    yield accum

    return _wrap(_window, dict(foo=foo, size=size, full_only=full_only, accum=accum), name='Window', wraps=(foo,), share=foo)


def Unroll(foo_or_val, kwargs=None):
    if not isinstance(foo_or_val, types.FunctionType):
        foo = Const(foo_or_val)
    else:
        foo = Foo(foo_or_val, kwargs or {})

    async def _unroll(foo):
        async for ret in foo():
            if isinstance(ret, list):
                for f in ret:
                    yield f
            elif isinstance(ret, types.AsyncGeneratorType):
                async for f in ret:
                    yield f

    return _wrap(_unroll, dict(foo=foo), name='Unroll', wraps=(foo,), share=foo)


def UnrollDataFrame(foo_or_val, kwargs=None, json=True, wrap=False):
    if not isinstance(foo_or_val, types.FunctionType):
        foo = Const(foo_or_val)
    else:
        foo = Foo(foo_or_val, kwargs or {})

    async def _unrolldf(foo):
        async for df in foo():
            for i in range(len(df)):
                row = df.iloc[i]
                if json:
                    data = row.to_dict()
                    data['index'] = row.name
                    yield data
                else:
                    yield row

    return _wrap(_unrolldf, dict(foo=foo), name='UnrollDataFrame', wraps=(foo,), share=foo)


def Merge(f_wrap1, f_wrap2):
    if not isinstance(f_wrap1, FunctionWrapper):
        if not isinstance(f_wrap1, types.FunctionType):
            f_wrap1 = Const(f_wrap1)
        else:
            f_wrap1 = Foo(f_wrap1)

    if not isinstance(f_wrap2, FunctionWrapper):
        if not isinstance(f_wrap2, types.FunctionType):
            f_wrap2 = Const(f_wrap2)
        else:
            f_wrap2 = Foo(f_wrap2)

    async def _merge(foo1, foo2):
        async for gen1, gen2 in zip(foo1(), foo2()):
            if isinstance(gen1, types.AsyncGeneratorType) and \
               isinstance(gen2, types.AsyncGeneratorType):
                async for f1, f2 in zip(gen1, gen2):
                    yield [f1, f2]
            elif isinstance(gen1, types.AsyncGeneratorType):
                async for f1 in gen1:
                    yield [f1, gen2]
            elif isinstance(gen2, types.AsyncGeneratorType):
                async for f2 in gen2:
                    yield [gen1, f2]
            else:
                yield [gen1, gen2]

    return _wrap(_merge, dict(foo1=f_wrap1, foo2=f_wrap2), name='Merge', wraps=(f_wrap1, f_wrap2), share=None)


def ListMerge(f_wrap1, f_wrap2):
    if not isinstance(f_wrap1, FunctionWrapper):
        if not isinstance(f_wrap1, types.FunctionType):
            f_wrap1 = Const(f_wrap1)
        else:
            f_wrap1 = Foo(f_wrap1)

    if not isinstance(f_wrap2, FunctionWrapper):
        if not isinstance(f_wrap2, types.FunctionType):
            f_wrap2 = Const(f_wrap2)
        else:
            f_wrap2 = Foo(f_wrap2)

    async def _merge(foo1, foo2):
        async for gen1, gen2 in zip(foo1(), foo2()):
            if isinstance(gen1, types.AsyncGeneratorType) and \
               isinstance(gen2, types.AsyncGeneratorType):
                async for f1, f2 in zip(gen1, gen2):
                    ret = []
                    ret.extend(f1)
                    ret.extend(f1)
                    yield ret
            elif isinstance(gen1, types.AsyncGeneratorType):
                async for f1 in gen1:
                    ret = []
                    ret.extend(f1)
                    ret.extend(gen2)
                    yield ret
            elif isinstance(gen2, types.AsyncGeneratorType):
                async for f2 in gen2:
                    ret = []
                    ret.extend(gen1)
                    ret.extend(f2)
                    yield ret
            else:
                ret = []
                ret.extend(gen1)
                ret.extend(gen2)
                yield ret

    return _wrap(_merge, dict(foo1=f_wrap1, foo2=f_wrap2), name='ListMerge', wraps=(f_wrap1, f_wrap2), share=None)


def DictMerge(f_wrap1, f_wrap2):
    if not isinstance(f_wrap1, FunctionWrapper):
        if not isinstance(f_wrap1, types.FunctionType):
            f_wrap1 = Const(f_wrap1)
        else:
            f_wrap1 = Foo(f_wrap1)

    if not isinstance(f_wrap2, FunctionWrapper):
        if not isinstance(f_wrap2, types.FunctionType):
            f_wrap2 = Const(f_wrap2)
        else:
            f_wrap2 = Foo(f_wrap2)

    async def _dictmerge(foo1, foo2):
        async for gen1, gen2 in zip(foo1(), foo2()):
            if isinstance(gen1, types.AsyncGeneratorType) and \
               isinstance(gen2, types.AsyncGeneratorType):
                async for f1, f2 in zip(gen1, gen2):
                    ret = {}
                    ret.update(f1)
                    ret.update(f1)
                    yield ret
            elif isinstance(gen1, types.AsyncGeneratorType):
                async for f1 in gen1:
                    ret = {}
                    ret.update(f1)
                    ret.update(gen2)
                    yield ret
            elif isinstance(gen2, types.AsyncGeneratorType):
                async for f2 in gen2:
                    ret = {}
                    ret.update(gen1)
                    ret.update(f2)
                    yield ret
            else:
                ret = {}
                ret.update(gen1)
                ret.update(gen2)
                yield ret

    return _wrap(_dictmerge, dict(foo1=f_wrap1, foo2=f_wrap2), name='DictMerge', wraps=(f_wrap1, f_wrap2), share=None)


def Reduce(*f_wraps):
    f_wraps = list(f_wraps)
    for i, f_wrap in enumerate(f_wraps):
        if not isinstance(f_wrap, types.FunctionType):
            f_wraps[i] = Const(f_wrap)
        else:
            f_wraps[i] = Foo(f_wrap)

    async def _reduce(foos):
        async for all_gens in zip(*[foo() for foo in foos]):
            gens = []
            vals = []
            for gen in all_gens:
                if isinstance(gen, types.AsyncGeneratorType):
                    gens.append(gen)
                else:
                    vals.append(gen)
            if gens:
                for gens in zip(*gens):
                    ret = list(vals)
                    for gen in gens:
                        ret.append(next(gen))
                    yield ret
            else:
                yield vals

    return _wrap(_reduce, dict(foos=f_wraps), name='Reduce', wraps=tuple(f_wraps), share=None)

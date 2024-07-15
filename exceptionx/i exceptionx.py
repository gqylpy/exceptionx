import sys
import time
import logging
import asyncio
import builtins
import warnings
import functools
import traceback
import threading

from copy import copy, deepcopy
from contextlib import contextmanager

from types import FunctionType, FrameType, TracebackType
from typing import TypeVar, Type, Final, Optional, Union, Tuple, Callable, Any

if sys.version_info >= (3, 9):
    from typing import Annotated
else:
    class Annotated(metaclass=type('', (type,), {
        '__new__': lambda *a: type.__new__(*a)()
    })):
        def __getitem__(self, *a): ...

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    TypeAlias = TypeVar('TypeAlias')

Closure = TypeVar('Closure', bound=Callable)

ExceptionTypes: TypeAlias = Union[Type[Exception], Tuple[Type[Exception], ...]]
ExceptionLogger: TypeAlias = Union[logging.Logger, 'gqylpy_log']
ExceptionCallback: TypeAlias = Callable[[Exception, FunctionType, '...'], None]

UNIQUE: Final[Annotated[object, 'A unique object.']] = object()

CO_QUALNAME: Final[Annotated[str, '''
    The alternative solution of the old version for `co_qualname` attribute.
''']] = 'co_qualname' if sys.version_info >= (3, 11) else 'co_name'


class Error(Exception):
    __module__ = builtins.__name__

    def __init_subclass__(cls) -> None:
        cls.__module__ = builtins.__name__
        setattr(builtins, cls.__name__, cls)

    msg: Any = Exception.args


builtins.Error = Error


class MasqueradeClass(type):
    """
    Masquerade one class as another (default masquerade as first parent class).
    Warning, masquerade the class can cause unexpected problems, use caution.
    """
    __module__ = builtins.__name__

    __qualname__ = type.__qualname__
    # Warning, masquerade (modify) this attribute will cannot create the
    # portable serialized representation. In practice, however, this metaclass
    # often does not need to be serialized, so we try to ignore it.

    def __new__(mcs, __name__: str, __bases__: tuple, __dict__: dict):
        __masquerade_class__: Type[object] = __dict__.setdefault(
            '__masquerade_class__', __bases__[0] if __bases__ else object
        )

        if not isinstance(__masquerade_class__, type):
            raise TypeError('"__masquerade_class__" is not a class.')

        cls = type.__new__(
            mcs, __masquerade_class__.__name__, __bases__, __dict__
        )

        if cls.__module__ != __masquerade_class__.__module__:
            setattr(sys.modules[__masquerade_class__.__module__], __name__, cls)

        cls.__realname__   = __name__
        cls.__realmodule__ = cls.__module__
        cls.__module__     = __masquerade_class__.__module__

        # cls.__qualname__ = __masquerade_class__.__qualname__
        # Masquerade (modify) this attribute will cannot create the portable
        # serialized representation. We have not yet found an effective
        # solution, and we will continue to follow up.

        return cls

    def __hash__(cls) -> int:
        if sys._getframe(1).f_code in (deepcopy.__code__, copy.__code__):
            return type.__hash__(cls)
        return hash(cls.__masquerade_class__)

    def __eq__(cls, o) -> bool:
        return True if o is cls.__masquerade_class__ else type.__eq__(cls, o)

    def __init_subclass__(mcs) -> None:
        setattr(builtins, mcs.__name__, mcs)
        mcs.__name__     = MasqueradeClass.__name__
        mcs.__qualname__ = MasqueradeClass.__qualname__
        mcs.__module__   = MasqueradeClass.__module__


MasqueradeClass.__name__ = type.__name__
builtins.MasqueradeClass = MasqueradeClass


class __history__(dict, metaclass=type('SingletonMode', (MasqueradeClass,), {
    '__new__': lambda *a: MasqueradeClass.__new__(*a)()
})):

    def __setitem__(self, *a, **kw) -> None:
        raise __getattr__('ReadOnlyError')('this dictionary is read-only.')

    __delitem__ = setdefault = update = pop = popitem = clear = __setitem__

    def __reduce_ex__(self, protocol: int) -> ...:
        return self.__class__, (dict(self),)

    def copy(self) -> '__history__.__class__':
        return copy(self)


def __getattr__(ename: str, /) -> Union[Type[BaseException], Type[Error]]:
    if ename in __history__:
        return __history__[ename]

    if ename[:2] == ename[-2:] == '__' and ename[2] != '_' and ename[-3] != '_':
        # Some special modules may attempt to call non-built-in magic method,
        # such as `copy`, `pickle`. Compatible for this purpose.
        raise AttributeError(f'"{__package__}" has no attribute "{ename}".')

    etype = getattr(builtins, ename, None)
    if isinstance(etype, type) and issubclass(etype, BaseException):
        return etype

    if ename[-5:] != 'Error':
        warnings.warn(
            f'strange exception class "{ename}", exception class name should '
            'end with "Error".', stacklevel=2
        )

    etype = type(ename, (Error,), {})
    dict.__setitem__(__history__, ename, etype)

    return etype


class TryExcept:

    def __init__(
            self,
            etype:      ExceptionTypes,
            /, *,
            silent:     Optional[bool]              = None,
            silent_exc: bool                        = UNIQUE,
            raw:        Optional[bool]              = None,
            raw_exc:    bool                        = UNIQUE,
            last_tb:    bool                        = False,
            logger:     Optional[ExceptionLogger]   = None,
            ereturn:    Optional[Any]               = None,
            ecallback:  Optional[ExceptionCallback] = None,
            eexit:      bool                        = False
    ):
        if silent_exc is not UNIQUE:
            warnings.warn(
                'parameter "silent_exc" will be deprecated soon, replaced to '
                '"silent". (Did you switch from "gqylpy-exception"?)',
                category=DeprecationWarning,
                stacklevel=2 if self.__class__ is TryExcept else 3
            )
            if silent is None:
                silent = silent_exc

        if raw_exc is not UNIQUE:
            warnings.warn(
                'parameter "raw_exc" will be deprecated soon, replaced to '
                '"raw". (Did you switch from "gqylpy-exception"?)',
                category=DeprecationWarning,
                stacklevel=2 if self.__class__ is TryExcept else 3
            )
            if raw is None:
                raw = raw_exc

        self.etype     = etype
        self.silent    = silent
        self.raw       = raw
        self.last_tb   = last_tb
        self.logger    = get_logger(logger)
        self.ereturn   = ereturn
        self.ecallback = ecallback
        self.eexit     = eexit

    def __call__(self, func: FunctionType) -> Closure:
        try:
            core = func.__closure__[1].cell_contents.core.__func__
        except (TypeError, IndexError, AttributeError):
            if asyncio.iscoroutinefunction(func):
                self.core = self.acore
        else:
            if core in (TryExcept.acore, Retry.acore):
                self.core = self.acore

        @functools.wraps(func, updated=('__dict__', '__globals__'))
        def inner(*a, **kw) -> Any:
            return self.core(func, *a, **kw)

        return inner

    def core(self, func: FunctionType, *a, **kw) -> Any:
        try:
            return func(*a, **kw)
        except self.etype as e:
            self.exception_handling(func, e, *a, **kw)
        return self.ereturn

    async def acore(self, func: FunctionType, *a, **kw) -> Any:
        try:
            return await func(*a, **kw)
        except self.etype as e:
            self.exception_handling(func, e, *a, **kw)
        return self.ereturn

    def exception_handling(
            self, func: FunctionType, e: Exception, *a, **kw
    ) -> None:
        if not self.silent:
            self.logger(get_einfo(e, raw=self.raw, last_tb=self.last_tb))
        if self.ecallback is not None:
            self.ecallback(e, func, *a, **kw)
        if self.eexit:
            raise SystemExit(4)


class Retry(TryExcept):

    def __init__(
            self,
            etype:      ExceptionTypes              = Exception,
            /, *,
            count:      int                         = 0,
            sleep:      Optional[Union[int, float]] = None,
            cycle:      Union[int, float]           = UNIQUE,
            limit_time: Union[int, float]           = 0,
            event:      threading.Event             = threading.Event(),
            emsg:       str                         = None,
            silent:     Optional[bool]              = None,
            silent_exc: bool                        = UNIQUE,
            raw:        Optional[bool]              = None,
            raw_exc:    bool                        = UNIQUE,
            last_tb:    bool                        = None,
            logger:     Optional[ExceptionLogger]   = None
    ):
        x = 'sleep'
        if cycle is not UNIQUE:
            warnings.warn(
                'parameter "cycle" will be deprecated soon, replaced to '
                '"sleep". (Did you switch from "gqylpy-exception"?)',
                category=DeprecationWarning, stacklevel=2
            )
            if sleep is None:
                sleep = cycle
                x = 'cycle'

        if count == 0:
            count = 'N'
        elif not (isinstance(count, int) and count > 0):
            raise __getattr__('ParameterError')(
                'parameter "count" must be of type int and greater than or '
                f'equal to 0, not {count!r}.'
            )

        if sleep is None:
            sleep = 0
        elif not (isinstance(sleep, (int, float)) and sleep >= 0):
            raise __getattr__('ParameterError')(
                f'parameter "{x}" must be of type int or float and greater '
                f'than or equal to 0, not {sleep!r}.'
            )

        if limit_time == 0:
            limit_time = float('inf')
        elif not (isinstance(limit_time, (int, float)) and limit_time > 0):
            raise __getattr__('ParameterError')(
                'parameter "limit_time" must be of type int or float and '
                f'greater than or equal to 0, not {limit_time!r}.'
            )

        if not isinstance(event, threading.Event):
            raise __getattr__('ParameterError')(
                'parameter "event" must be of type "threading.Event", '
                f'not "{event.__class__.__name__}".'
            )

        if not (emsg is None or isinstance(emsg, str)):
            raise __getattr__('ParameterError')(
                'parameter "emsg" must be of type str, '
                f'not "{emsg.__class__.__name__}".'
            )

        self.count      = count
        self.sleep      = sleep
        self.limit_time = limit_time
        self.event      = event
        self.emsg       = emsg

        TryExcept.__init__(
            self, etype, silent=silent, silent_exc=silent_exc, raw=raw,
            raw_exc=raw_exc, last_tb=last_tb, logger=logger
        )

    def core(self, func: FunctionType, *a, **kw) -> Any:
        count = 0
        before = time.monotonic()
        while True:
            start = time.monotonic()
            try:
                return func(*a, **kw)
            except self.etype as e:
                if not (self.emsg is None or self.emsg in str(e)):
                    raise
                self.exception_handling(e, count=count)
                count += 1
                end = time.monotonic()
                sleep = max(.0, self.sleep - (end - start))
                if (
                        count == self.count
                        or end - before + sleep >= self.limit_time
                        or self.event.is_set()
                ):
                    raise
                time.sleep(sleep)

    async def acore(self, func: FunctionType, *a, **kw) -> Any:
        count = 0
        before = time.monotonic()
        while True:
            start = time.monotonic()
            try:
                return await func(*a, **kw)
            except self.etype as e:
                if not (self.emsg is None or self.emsg in str(e)):
                    raise
                self.exception_handling(e, count=count)
                count += 1
                end = time.monotonic()
                sleep = max(.0, self.sleep - (end - start))
                if (
                        count == self.count
                        or end - before + sleep >= self.limit_time
                        or self.event.is_set()
                ):
                    raise
                time.sleep(sleep)

    def exception_handling(self, e: Exception, *, count: int) -> None:
        if not self.silent:
            einfo: str = get_einfo(e, raw=self.raw, last_tb=self.last_tb)
            einfo = f'[try:{count}/{self.count}:{self.sleep}] {einfo}'
            self.logger(einfo)


@contextmanager
def TryContext(
        etype:     ExceptionTypes,
        /, *,
        silent:    bool                                  = False,
        raw:       bool                                  = False,
        last_tb:   bool                                  = False,
        logger:    Optional[ExceptionLogger]             = None,
        ecallback: Optional[Callable[[Exception], None]] = None,
        eexit:     bool                                  = False
) -> None:
    logger = get_logger(logger)
    try:
        yield
    except etype as e:
        if not silent:
            logger(get_einfo(e, raw=raw, last_tb=last_tb))
        if ecallback is not None:
            ecallback(e)
        if eexit:
            raise SystemExit(4)


def stderr(einfo: str) -> None:
    now: str = time.strftime('%F %T', time.localtime())
    sys.stderr.write(f'[{now}] {einfo}\n')


def get_logger(logger: logging.Logger) -> Callable[[str], None]:
    if logger is None:
        return stderr

    is_glog_module: bool = getattr(logger, '__package__', None) == 'gqylpy_log'

    if not (isinstance(logger, logging.Logger) or is_glog_module):
        raise ValueError(
            'parameter "logger" must be an instance of "logging.Logger", '
            f'not "{logger.__class__.__name__}".'
        )

    previous_frame: FrameType = sys._getframe(1)

    if previous_frame.f_back.f_code is Retry.__init__.__code__:
        caller = logger.warning
    else:
        caller = logger.error

    if previous_frame.f_code is TryContext.__wrapped__.__code__:
        stacklevel = 4
    else:
        stacklevel = 5

    if is_glog_module:
        caller = functools.partial(caller, stacklevel=stacklevel)

    return caller


def get_einfo(e: Exception, /, *, raw: bool, last_tb: bool) -> str:
    try:
        if raw:
            return traceback.format_exc()

        tb: TracebackType = e.__traceback__.tb_next

        if last_tb:
            while tb.tb_next:
                tb = tb.tb_next

        module: str = tb.tb_frame.f_globals['__name__']
        name:   str = getattr(tb.tb_frame.f_code, CO_QUALNAME)
        lineno: int = tb.tb_lineno
        ename:  str = e.__class__.__name__

        return f'[{module}.{name}.line{lineno}.{ename}] {e}'
    except Exception:
        return traceback.format_exc() + '\nPlease note that this exception ' \
            'occurred within the exceptionx library, not in your code.' \
            '\nPlease report the error to ' \
            'https://github.com/gqylpy/exceptionx/issues, thank you.\n'

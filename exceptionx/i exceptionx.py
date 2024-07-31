import re
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

from types import FrameType, TracebackType
from typing import \
    TypeVar, Type, Final, Optional, Union, Tuple, Callable, NoReturn, Any

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

Wrapped = WrappedClosure = TypeVar('Wrapped', bound=Callable[..., Any])
WrappedReturn: TypeAlias = TypeVar('WrappedReturn')

ETypes: TypeAlias = Union[Type[Exception], Tuple[Type[Exception], ...]]
ELogger: TypeAlias = Union[logging.Logger, 'gqylpy_log']
ECallback: TypeAlias = Callable[..., None]

Second: TypeAlias = TypeVar('Second', bound=Union[int, float, str])

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

    def __setitem__(self, *a, **kw) -> NoReturn:
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

    def __new__(
            cls, etype: Union[ETypes, Wrapped], /, **kw
    ) -> Union['TryExcept', WrappedClosure]:
        ins = object.__new__(cls)
        if isinstance(etype, type) and issubclass(etype, Exception):
            return ins
        if callable(etype):
            ins.__init__(Exception)
            return ins(etype)
        if isinstance(etype, tuple):
            for et in etype:
                if not (isinstance(et, type) and issubclass(et, Exception)):
                    break
            else:
                return ins
        raise __getattr__('ParameterError')(
            'parameter "etype" must be a subclass inherited from "Exception" '
            f'or multiple ones packaged using a tuple, not {etype!r}.'
        )

    def __init__(
            self,
            etype:      ETypes,
            /, *,
            emsg:       Optional[str]       = None,
            silent:     Optional[bool]      = None,
            silent_exc: bool                = UNIQUE,
            raw:        Optional[bool]      = None,
            raw_exc:    bool                = UNIQUE,
            invert:     bool                = False,
            last_tb:    bool                = False,
            logger:     Optional[ELogger]   = None,
            ereturn:    Optional[Any]       = None,
            ecallback:  Optional[ECallback] = None,
            eexit:      bool                = False
    ):
        if not (emsg is None or isinstance(emsg, str)):
            raise __getattr__('ParameterError')(
                'parameter "emsg" must be of type str, '
                f'not "{emsg.__class__.__name__}".'
            )

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
        self.emsg      = emsg
        self.silent    = silent
        self.raw       = raw
        self.invert    = invert
        self.last_tb   = last_tb
        self.logger    = get_logger(logger)
        self.ereturn   = ereturn
        self.ecallback = ecallback
        self.eexit     = eexit

    def __call__(self, func: Wrapped, /) -> WrappedClosure:
        try:
            core = func.__closure__[1].cell_contents.core.__func__
        except (TypeError, IndexError, AttributeError):
            if asyncio.iscoroutinefunction(func):
                self.core = self.acore
        else:
            if core in (TryExcept.acore, Retry.acore):
                self.core = self.acore

        @functools.wraps(func)
        def inner(*a, **kw) -> Any:
            return self.core(func, *a, **kw)

        inner.__self = self
        return inner

    def core(self, func: Wrapped, *a, **kw) -> WrappedReturn:
        try:
            return func(*a, **kw)
        except self.etype as e:
            if self.invert or not (self.emsg is None or self.emsg in str(e)):
                raise
            self.exception_handling(func, e, *a, **kw)
        except Exception as e:
            if not (self.invert and (self.emsg is None or self.emsg in str(e))):
                raise
            self.exception_handling(func, e, *a, **kw)
        return self.ereturn

    async def acore(self, func: Wrapped, *a, **kw) -> WrappedReturn:
        try:
            return await func(*a, **kw)
        except self.etype as e:
            if self.invert or not (self.emsg is None or self.emsg in str(e)):
                raise
            self.exception_handling(func, e, *a, **kw)
        except Exception as e:
            if not (self.invert and (self.emsg is None or self.emsg in str(e))):
                raise
            self.exception_handling(func, e, *a, **kw)
        return self.ereturn

    def exception_handling(self, func: Wrapped, e: Exception, *a, **kw) -> None:
        if not self.silent:
            self.logger(get_einfo(e, raw=self.raw, last_tb=self.last_tb))
        if self.ecallback is not None:
            self.ecallback(e, func, *a, **kw)
        if self.eexit:
            raise SystemExit(4)


class Retry(TryExcept):

    def __new__(
            cls, etype: Union[ETypes, Wrapped] = Exception, /, **kw
    ) -> Union['Retry', WrappedClosure]:
        ins = TryExcept.__new__(cls, etype)
        if not isinstance(ins, Retry):
            ins._TryExcept__self.silent = True
        return ins

    def __init__(
            self,
            etype:      ETypes                    = Exception,
            /, *,
            emsg:       Optional[str]             = None,
            sleep:      Optional[Second]          = None,
            cycle:      Second                    = UNIQUE,
            count:      int                       = 0,
            limit_time: Second                    = 0,
            event:      Optional[threading.Event] = None,
            silent:     Optional[bool]            = None,
            silent_exc: bool                      = UNIQUE,
            raw:        Optional[bool]            = None,
            raw_exc:    bool                      = UNIQUE,
            invert:     bool                      = False,
            last_tb:    bool                      = None,
            logger:     Optional[ELogger]         = None
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

        if sleep is None:
            sleep = 0
        elif isinstance(sleep, str):
            sleep = time2second(sleep)
        elif not (isinstance(sleep, (int, float)) and sleep >= 0):
            raise __getattr__('ParameterError')(
                f'parameter "{x}" is expected to be of type int or float and '
                f'greater than or equal to 0, not {sleep!r}.'
            )
        elif isinstance(sleep, float) and sleep.is_integer():
            sleep = int(sleep)

        if count == 0:
            count = 'N'
        elif not (isinstance(count, int) and count > 0):
            raise __getattr__('ParameterError')(
                'parameter "count" must be of type int and greater than or '
                f'equal to 0, not {count!r}.'
            )

        if limit_time == 0:
            limit_time = float('inf')
        elif isinstance(limit_time, str):
            limit_time = time2second(limit_time)
        elif not (isinstance(limit_time, (int, float)) and limit_time > 0):
            raise __getattr__('ParameterError')(
                'parameter "limit_time" is expected to be of type int or float '
                f'and greater than or equal to 0, not {limit_time!r}.'
            )
        elif isinstance(limit_time, float) and limit_time.is_integer():
            limit_time = int(limit_time)

        if not (event is None or isinstance(event, threading.Event)):
            raise __getattr__('ParameterError')(
                'parameter "event" must be of type "threading.Event", '
                f'not "{event.__class__.__name__}".'
            )

        self.sleep      = sleep
        self.count      = count
        self.limit_time = limit_time
        self.event      = event

        TryExcept.__init__(
            self, etype, emsg=emsg, silent=silent, silent_exc=silent_exc,
            raw=raw, raw_exc=raw_exc, invert=invert, last_tb=last_tb,
            logger=logger
        )

    def core(self, func: Wrapped, *a, **kw) -> WrappedReturn:
        count = 0
        before = time.monotonic()
        while True:
            start = time.monotonic()
            try:
                return func(*a, **kw)
            except Exception as e:
                contain_emsg: bool = self.emsg is None or self.emsg in str(e)
                if isinstance(e, self.etype):
                    if self.invert or not contain_emsg:
                        raise
                elif not (self.invert and contain_emsg):
                    raise
                count += 1
                self.output_einfo(e, count=count, start=start, before=before)
                end = time.monotonic()
                sleep = max(.0, self.sleep - (end - start))
                if (
                        count == self.count
                        or end - before + sleep >= self.limit_time
                        or self.event is not None and self.event.is_set()
                ):
                    raise
                time.sleep(sleep)

    async def acore(self, func: Wrapped, *a, **kw) -> WrappedReturn:
        count = 0
        before = time.monotonic()
        while True:
            start = time.monotonic()
            try:
                return await func(*a, **kw)
            except Exception as e:
                contain_emsg: bool = self.emsg is None or self.emsg in str(e)
                if isinstance(e, self.etype):
                    if self.invert or not contain_emsg:
                        raise
                elif not (self.invert and contain_emsg):
                    raise
                count += 1
                self.output_einfo(e, count=count, start=start, before=before)
                end = time.monotonic()
                sleep = max(.0, self.sleep - (end - start))
                if (
                        count == self.count
                        or end - before + sleep >= self.limit_time
                        or self.event is not None and self.event.is_set()
                ):
                    raise
                time.sleep(sleep)

    def output_einfo(
            self, e: Exception, *, count: int, start: float, before: float
    ) -> None:
        if (
                self.silent or time.monotonic() - start + self.sleep < .1
                and (self.count == 'N' or self.count >= 30)
                and 1 < count < self.count
                and (self.event is None or not self.event.is_set())
        ):
            return

        einfo: str = get_einfo(e, raw=self.raw, last_tb=self.last_tb)
        x = f'[try:{count}/{self.count}'

        if self.limit_time != float('inf'):
            x += f':{second2time(self.sleep)}'
            spent_time = second2time(self.get_spent_time(start, before))
            x += f',limit_time:{spent_time}/{second2time(self.limit_time)}'
        elif self.sleep >= 90:
            x += f':{second2time(self.sleep)}'
        else:
            x += f':{self.sleep}'

        if self.event is not None:
            x += f',event={self.event.is_set()}'

        self.logger(f'{x}] {einfo}')

    def get_spent_time(self, start: float, before: float) -> Union[int, float]:
        now = time.monotonic()

        if isinstance(self.sleep, float) or isinstance(self.limit_time, float):
            spent_time = round(now - before, 2)
            if spent_time.is_integer():
                spent_time = int(spent_time)
        else:
            spent_time = now - before
            if now - start + self.sleep >= 3:
                spent_time = round(spent_time)

        return spent_time


@contextmanager
def TryContext(
        etype:     ETypes,
        /, *,
        emsg:      Optional[str]       = None,
        silent:    bool                = False,
        raw:       bool                = False,
        invert:    bool                = False,
        last_tb:   bool                = False,
        logger:    Optional[ELogger]   = None,
        ecallback: Optional[ECallback] = None,
        eexit:     bool                = False
) -> None:
    logger = get_logger(logger)
    try:
        yield
    except Exception as e:
        contain_emsg: bool = emsg is None or emsg in str(e)
        if isinstance(e, etype):
            if invert or not contain_emsg:
                raise
        elif not (invert and contain_emsg):
            raise
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
        stacklevel = 3
    else:
        stacklevel = 4
    if is_glog_module:
        stacklevel += 1

    return functools.partial(caller, stacklevel=stacklevel)


def get_einfo(e: Exception, /, *, raw: bool, last_tb: bool) -> str:
    try:
        if raw:
            return traceback.format_exc()

        tb: TracebackType = e.__traceback__.tb_next

        if last_tb:
            while tb.tb_next:
                tb = tb.tb_next
        else:
            while tb.tb_frame.f_code.co_filename == __file__:
                tb = tb.tb_next

        module: str = tb.tb_frame.f_globals['__name__']
        name:   str = getattr(tb.tb_frame.f_code, CO_QUALNAME)
        lineno: int = tb.tb_lineno
        ename:  str = e.__class__.__name__

        return f'[{module}.{name}.line{lineno}.{ename}] {e}'
    except Exception:
        return traceback.format_exc() + '\nPlease note that this exception ' \
            'occurred within the exceptionx library, not in your code.\n' \
            'Another exception occurred while we were handling the exception ' \
            'in your code, very sorry. \nPlease report the error to ' \
            'https://github.com/gqylpy/exceptionx/issues, thank you.\n'


def time2second(unit_time: str, /, *, __pattern__ = re.compile(r'''
        (?:(\d+(?:\.\d+)?)d)?
        (?:(\d+(?:\.\d+)?)h)?
        (?:(\d+(?:\.\d+)?)m)?
        (?:(\d+(?:\.\d+)?)s?)?
''', flags=re.X | re.I)) -> Union[int, float]:
    if unit_time.isdigit():
        return int(unit_time)

    if not (unit_time and (m := __pattern__.fullmatch(unit_time))):
        raise ValueError(f'unit time {unit_time!r} format is incorrect.')

    r = 0

    for x, s in zip(m.groups(), (86400, 3600, 60, 1)):
        if x is not None:
            x = int(x) if x.isdigit() else float(x)
            r += x * s

    return int(r) if isinstance(r, float) and r.is_integer() else r


def second2time(second: Union[int, float], /) -> str:
    sec = int(second)
    dec = round(second - sec, 2)

    r = ''

    for u, s in ('d', 86400), ('h', 3600), ('m', 60):
        if sec >= s:
            v, sec = divmod(sec, s)
            r += f'{v}{u}'

    if sec or dec:
        sec += dec
        if isinstance(sec, float):
            sec = int(sec) if sec.is_integer() else round(sec, 2)
        r += f'{sec}s'

    return r or '0s'

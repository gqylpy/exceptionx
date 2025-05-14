# coding:utf-8
import re
import sys
import time
import logging
import functools
import traceback
import threading

from contextlib import contextmanager

from typing import Type, Optional, Union, Tuple, Callable, Any

if sys.version_info >= (3, 8):
    from typing import Protocol
else:
    Protocol = object


class HasWarningMethod(Protocol):
    def warning(self, msg):
        pass


class HasErrorMethod(Protocol):
    def error(self, msg):
        pass


ETypes    = Union[Type[Exception], Tuple[Type[Exception], ...]]
ELogger   = Union[HasWarningMethod, HasErrorMethod]
ECallback = Callable[..., None]
Second    = Union[int, float, str]

py2 = sys.version_info.major == 2

CO_QUALNAME = 'co_qualname' if sys.version_info >= (3, 11) else 'co_name'


class TryExcept(object):

    def __new__(cls, etype, *a, **kw):
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
        raise ParameterError(
            'parameter "etype" must be a subclass inherited from "Exception" '
            'or multiple ones packaged using a tuple, not %s.' % repr(etype)
        )

    def __init__(
            self,
            etype,            # type: ETypes
            emsg     =None,   # type: Optional[str]
            silent   =None,   # type: Optional[bool]
            raw      =None,   # type: Optional[bool]
            invert   =False,  # type: bool
            last_tb  =False,  # type: bool
            logger   =None,   # type: Optional[ELogger]
            ereturn  =None,   # type: Optional[Any]
            ecallback=None,   # type: Optional[ECallback]
            eexit    =False   # type: bool
    ):
        if not (emsg is None or isinstance(emsg, str)):
            raise ParameterError(
                'parameter "emsg" must be of type str, not "%s".'
                % emsg.__class__.__name__
            )

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

    def __call__(self, func):
        @functools.wraps(func)
        def inner(*a, **kw):
            return self.core(func, *a, **kw)
        inner.__wrapped__ = func
        inner.__self = self
        return inner

    def core(self, func, *a, **kw):
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

    def exception_handling(self, func, e, *a, **kw):
        if not self.silent:
            self.logger(get_einfo(e, raw=self.raw, last_tb=self.last_tb))
        if self.ecallback is not None:
            self.ecallback(e, func, *a, **kw)
        if self.eexit:
            raise SystemExit(4)


class Retry(TryExcept):

    def __new__(cls, etype=Exception, **kw):
        ins = TryExcept.__new__(cls, etype)
        if not isinstance(ins, Retry):
            ins._TryExcept__self.silent = True
        return ins

    def __init__(
            self,
            etype     =Exception,  # type: ETypes
            emsg      =None,       # type: Optional[str]
            sleep     =None,       # type: Optional[Second]
            count     =0,          # type: int
            limit_time=0,          # type: Second
            event     =None,       # type: Optional[threading.Event]
            silent    =None,       # type: Optional[bool]
            raw       =None,       # type: Optional[bool]
            invert    =False,      # type: bool
            last_tb   =None,       # type: bool
            logger    =None        # type: Optional[ELogger]
    ):
        if sleep is None:
            sleep = 0
        elif isinstance(sleep, str):
            sleep = time2second(sleep)
        elif not (isinstance(sleep, (int, float)) and sleep >= 0):
            raise ParameterError(
                'parameter "sleep" is expected to be of type int or float and '
                'greater than or equal to 0, not %s.' % repr(sleep)
            )
        elif isinstance(sleep, float) and sleep.is_integer():
            sleep = int(sleep)

        if count == 0:
            count = float('inf')
        elif not (isinstance(count, int) and count > 0):
            raise ParameterError(
                'parameter "count" must be of type int and greater than or '
                'equal to 0, not %s.' % repr(count)
            )

        if limit_time == 0:
            limit_time = float('inf')
        elif isinstance(limit_time, str):
            limit_time = time2second(limit_time)
        elif not (isinstance(limit_time, (int, float)) and limit_time > 0):
            raise ParameterError(
                'parameter "limit_time" is expected to be of type int or float '
                'and greater than or equal to 0, not %s.' % repr(limit_time)
            )
        elif isinstance(limit_time, float) and limit_time.is_integer():
            limit_time = int(limit_time)

        if not (event is None or isinstance(event, threading.Event)):
            raise ParameterError(
                'parameter "event" must be of type "threading.Event", not "%s".'
                % event.__class__.__name__
            )

        self.sleep      = sleep
        self.count      = count
        self.limit_time = limit_time
        self.event      = event

        TryExcept.__init__(
            self, etype, emsg, silent, raw, invert, last_tb, logger
        )

    def core(self, func, *a, **kw):
        count = 1
        before = time.time()
        while True:
            start = time.time()
            try:
                return func(*a, **kw)
            except Exception as e:
                count, sleep = self.retry_handling(
                    e, count=count, start=start, before=before
                )
                time.sleep(sleep)

    def retry_handling(self, e, count, start, before):
        contain_emsg = self.emsg is None or self.emsg in str(e)
        if isinstance(e, self.etype):
            if self.invert or not contain_emsg:
                raise
        elif not (self.invert and contain_emsg):
            raise
        if not (
                self.silent
                or time.time() - start + self.sleep < .1
                and self.count >= 30
                and 1 < count < self.count
                and (self.event is None or not self.event.is_set())
        ):
            self.output_einfo(e, count=count, start=start, before=before)
        end = time.time()
        sleep = max(.0, self.sleep - (end - start))
        if (
                count == self.count
                or end - before + sleep >= self.limit_time
                or self.event is not None and self.event.is_set()
        ):
            raise
        return count + 1, sleep

    def output_einfo(self, e, count, start, before):
        einfo = get_einfo(e, raw=self.raw, last_tb=self.last_tb)

        max_count = 'N' if self.count == float('inf') else self.count
        x = '[try:%d/%s' % (count, max_count)

        if self.limit_time != float('inf'):
            x += ':' + second2time(self.sleep)
            spent_time = second2time(self.get_spent_time(start, before))
            limit_time = second2time(self.limit_time)
            x += ',limit_time:%s/%s' % (spent_time, limit_time)
        elif self.sleep >= 90:
            x += ':' + second2time(self.sleep)
        else:
            x += ':%s' % self.sleep

        if self.event is not None:
            x += ',event=' + str(self.event.is_set())

        self.logger(x + '] ' + einfo)

    def get_spent_time(self, start, before):
        now = time.time()

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
        etype,            # type: ETypes
        emsg     =None,   # type: Optional[str]
        silent   =False,  # type: bool
        raw      =False,  # type: bool
        invert   =False,  # type: bool
        last_tb  =False,  # type: bool
        logger   =None,   # type: Optional[ELogger]
        ecallback=None,   # type: Optional[ECallback]
        eexit    =False   # type: bool
):
    logger = get_logger(logger)
    try:
        yield
    except Exception as e:
        contain_emsg = emsg is None or emsg in str(e)
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


def stderr(einfo):
    now = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    sys.stderr.write('[%s] %s\n' % (now, einfo))


def get_logger(logger):
    if logger is None:
        return stderr

    previous_frame = sys._getframe(1)

    if previous_frame.f_back.f_code is Retry.__init__.__code__:
        name = 'warning'
    else:
        name = 'error'

    method = getattr(logger, name, None)
    if not callable(method):
        raise ParameterError(
            'parameter "logger" must have a "%s" method.' % name
        )

    if py2:
        return method
    if isinstance(logger, logging.Logger):
        stacklevel = 4
    elif getattr(logger, '__package__', None) == 'gqylpy_log':
        stacklevel = 5
    else:
        return method

    if previous_frame.f_code is TryContext.__wrapped__.__code__:
        stacklevel -= 1

    return functools.partial(method, stacklevel=stacklevel)


def get_einfo(e, raw, last_tb):
    try:
        if raw:
            return traceback.format_exc()

        if sys.version_info >= (3, 6):
            tb = e.__traceback__.tb_next
        else:
            tb = sys.exc_info()[2].tb_next

        if last_tb:
            while tb.tb_next:
                tb = tb.tb_next
        else:
            self_file = __file__
            if py2 and self_file[-1] == 'c':
                self_file = self_file[:-1]
            while tb.tb_frame.f_code.co_filename == self_file:
                tb = tb.tb_next

        module = tb.tb_frame.f_globals['__name__']
        name   = getattr(tb.tb_frame.f_code, CO_QUALNAME)
        lineno = tb.tb_lineno
        ename  = e.__class__.__name__

        return '[%s.%s.line%d.%s] %s' % (module, name, lineno, ename, e)
    except Exception:
        return traceback.format_exc() + '\nPlease note that this exception ' \
            'occurred within the exceptionx library, not in your code.\n' \
            'Another exception occurred while we were handling the exception ' \
            'in your code, very sorry. \nPlease report the error to ' \
            'https://github.com/gqylpy/exceptionx/issues, thank you.\n'


def time2second(unit_time, __pattern__=re.compile(r'''
       ^(?:(\d+(?:\.\d+)?)d)?
        (?:(\d+(?:\.\d+)?)h)?
        (?:(\d+(?:\.\d+)?)m)?
        (?:(\d+(?:\.\d+)?)s?)?$
''', flags=re.VERBOSE | re.IGNORECASE)):
    if unit_time.isdigit():
        return int(unit_time)

    m = __pattern__.match(unit_time)

    if not m:
        raise ValueError('unit time %s format is incorrect.' % repr(unit_time))

    r = 0

    for x, s in zip(m.groups(), (86400, 3600, 60, 1)):
        if x is not None:
            x = int(x) if x.isdigit() else float(x)
            r += x * s

    return int(r) if isinstance(r, float) and r.is_integer() else r


def second2time(second):
    sec = int(second)
    dec = round(second - sec, 2)

    r = ''

    for u, s in ('d', 86400), ('h', 3600), ('m', 60):
        if sec >= s:
            v, sec = divmod(sec, s)
            r += str(v) + u

    if sec or dec:
        sec += dec
        if isinstance(sec, float):
            sec = int(sec) if sec.is_integer() else round(sec, 2)
        r += str(sec) + 's'

    return r or '0s'


class ParameterError(ValueError):
    __module__ = 'builtins' if sys.version_info.major == 3 else 'exceptions'

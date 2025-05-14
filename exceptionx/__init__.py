# coding:utf-8
"""
The `exceptionx` is a flexible and convenient Python exception handling library
that provides multiple exception handling mechanisms.

Key Features:

- Powerful Exception Handling:
    Offers decorators (`TryExcept`, `Retry`) and context managers (`TryContext`)
    for flexible handling of exceptions within functions or code blocks.

- Configurable Options:
    Supports various exception handling options such as silent handling, raw
    exception output, logging, custom callbacks, and more.

Example Usage:

Handling Exceptions with Decorators:
    >>> from exceptionx import TryExcept, Retry

    >>> @TryExcept(ValueError)
    >>> def func():
    >>>     int('a')

    >>> @Retry(sleep=1, count=3)
    >>> def func():
    >>>     int('a')

Handling Exceptions with Context Managers:
    >>> from exceptionx import TryContext

    >>> with TryContext(ValueError):
    >>>     int('a')

For more information please visit https://github.com/gqylpy/exceptionx.
"""
from typing import Type, TypeVar, Optional, Tuple, Callable, Any

ETypes = TypeVar('ETypes', Type[Exception], Tuple[Type[Exception], ...])

ELogger = TypeVar('ELogger')
ECallback = TypeVar('ECallback', bound=Callable[..., None])

WrappedClosure = TypeVar('WrappedClosure', bound=Callable[..., Any])
Second = TypeVar('Second', int, float, str)


def TryExcept(
        etype,           # type: ETypes
        emsg     =None,  # type: Optional[str]
        silent   =None,  # type: Optional[bool]
        raw      =None,  # type: Optional[bool]
        invert   =None,  # type: Optional[bool]
        last_tb  =None,  # type: Optional[bool]
        logger   =None,  # type: Optional[ELogger]
        ereturn  =None,  # type: Optional[Any]
        ecallback=None,  # type: Optional[ECallback]
        eexit    =None   # type: Optional[bool]
):
    """
    `TryExcept` is a decorator that handles exceptions raised by the function it
    decorates (support decorating asynchronous functions).

        >>> @TryExcept(ValueError)
        >>> def func():
        >>>    int('a')

    @param etype:
        The types of exceptions to be handled, multiple types can be passed in
        using a tuple.

    @param emsg:
        The exception message. Only when the information of the captured
        exception contains this string, a retry will be performed; otherwise,
        the encountered exception will be thrown immediately. This is used to
        filter the exception messages that need to be retried, but it is not
        recommended to use it.

    @param silent:
        If True, exceptions will be silently handled without any output. The
        default is False.

    @param raw:
        If True, raw exception information will be directly output. The default
        is False. Note that its priority is lower than the `silent` parameter.

    @param invert:
        Used for inverting the exception type. If set to True, it will not
        handle the exception specified by the parameter `etype`, but instead
        handle all other exceptions that inherit from `Exception`. The default
        is False.

    @param last_tb:
        Whether to trace to the last traceback object of the exception. The
        default is False, tracing only to the current code segment.

    @param logger:
        By default, exception information is output to the terminal via
        `sys.stderr`. If you want to use your own logger to record exception
        information, you can pass the logger to this parameter, and the `error`
        method of the logger will be called internally.

    @param ereturn:
        The value to be returned when the decorated function raises an
        exception. The default is None.

    @param ecallback:
        Accepts a callable object and invokes it when an exception is raised.
        The callable object takes one argument, the raised exception object.

    @param eexit:
        If True, the program will execute `raise SystemExit(4)` and exit after
        an exception is raised, with an exit code of 4. If the ecallback
        parameter is provided, the program will execute the callback function
        first before exiting. The default is False.
    """


def Retry(
        etype     =None,  # type: Optional[ETypes]
        emsg      =None,  # type: Optional[str]
        sleep     =None,  # type: Optional[Second]
        count     =None,  # type: Optional[int]
        limit_time=None,  # type: Optional[Second]
        event     =None,  # type: Optional['threading.Event']
        silent    =None,  # type: Optional[bool]
        raw       =None,  # type: Optional[bool]
        invert    =None,  # type: Optional[bool]
        last_tb   =None,  # type: Optional[bool]
        logger    =None   # type: Optional[ELogger]
):
    """
    `Retry` is a decorator that retries exceptions raised by the function it
    decorates (support decorating asynchronous functions). When an exception is
    raised in the decorated function, it attempts to re-execute the decorated
    function.

        >>> @Retry(sleep=1, count=3)
        >>> def func():
        >>>     int('a')

        >>> @TryExcept(ValueError)
        >>> @Retry(sleep=1, count=3)
        >>> def func():
        >>>     int('a')

    @param etype:
        The types of exceptions to be handled, multiple types can be specified
        by passing them in a tuple. The default is `Exception`.

    @param emsg:
        The exception message. Only when the information of the captured
        exception contains this string, a retry will be performed; otherwise,
        the encountered exception will be thrown immediately. This is used to
        filter the exception messages that need to be retried, but it is not
        recommended to use it.

    @param sleep:
        The interval time between each retry, default is 0 seconds. The interval
        time will always be slightly longer than the actual value (almost
        negligible). Note that the interval time will be reduced by the time
        consumed by the execution of the decorated function. `sleep` supports
        passing time in the format of "1h2m3s".

    @param count:
        The number of retries, 0 means infinite retries, infinite by default.

    @param limit_time:
        This parameter is used to set the total time limit for retry operations
        in seconds. 0 indicates no time limit, default is no time limit. If the
        total time taken by the retry operation (including the time to execute
        the function and the interval time, with the interval time always added
        beforehand) exceeds this limit, the retry will be stopped immediately
        and the last encountered exception will be thrown. `limit_time` supports
        passing time in the format of "1h2m3s".

    @param event:
        An optional `threading.Event` object used to control the retry
        mechanism. During the retry process, this event can be set at any time
        to stop retrying. Once the event is set, even if the retry count has
        not reached the set upper limit or the time limit has not been exceeded,
        retrying will stop immediately and the last encountered exception will
        be thrown.

    @param silent:
        If True, exceptions will be silently handled without any output. The
        default is False.

    @param raw:
        If True, raw exception information will be directly output. The default
        is False. Note that its priority is lower than the `silent` parameter.

    @param invert:
        Used for inverting the exception type. If set to True, it will not retry
        the exception specified by the parameter `etype`, but instead retry all
        other exceptions that inherit from `Exception`. The default is False.

    @param last_tb:
        Whether to trace to the last traceback object of the exception. The
        default is False, tracing only to the current code segment.

    @param logger:
        By default, exception information is output to the terminal via
        `sys.stderr`. If you want to use your own logger to record exception
        information, you can pass the logger to this parameter, and the
        `warning` method of the logger will be called internally.
    """


def TryContext(
        etype,           # type: ETypes
        emsg     =None,  # type: Optional[str]
        silent   =None,  # type: Optional[bool]
        raw      =None,  # type: Optional[bool]
        invert   =None,  # type: Optional[bool]
        last_tb  =None,  # type: Optional[bool]
        logger   =None,  # type: Optional[ELogger]
        ecallback=None,  # type: Optional[ECallback]
        eexit    =None   # type: Optional[bool]
):
    """
    `TryContext` is a context manager that handles exceptions raised within the
    context.

        >>> with TryContext(ValueError):
        >>>     int('a')

    @param etype:
        The types of exceptions to be handled, multiple types can be passed in
        using a tuple.

    @param emsg:
        The exception message. Only when the information of the captured
        exception contains this string, a retry will be performed; otherwise,
        the encountered exception will be thrown immediately. This is used to
        filter the exception messages that need to be retried, but it is not
        recommended to use it.

    @param silent:
        If True, exceptions will be silently handled without any output. The
        default is False.

    @param raw:
        If True, raw exception information will be directly output. The default
        is False. Note that its priority is lower than the `silent` parameter.

    @param invert:
        Used for inverting the exception type. If set to True, it will not
        handle the exception specified by the parameter `etype`, but instead
        handle all other exceptions that inherit from `Exception`. The default
        is False.

    @param last_tb:
        Whether to trace to the last traceback object of the exception. The
        default is False, tracing only to the current code segment.

    @param logger:
        By default, exception information is output to the terminal via
        `sys.stderr`. If you want to use your own logger to record exception
        information, you can pass the logger to this parameter, and the `error`
        method of the logger will be called internally.

    @param ecallback:
        Accepts a callable object and invokes it when an exception is raised.
        The callable object takes one argument, the raised exception object.

    @param eexit:
        If True, the program will execute `raise SystemExit(4)` and exit after
        an exception is raised, with an exit code of 4. If the ecallback
        parameter is provided, the program will execute the callback function
        first before exiting. The default is False.
    """


class _xe6_xad_x8c_xe7_x90_xaa_xe6_x80_xa1_xe7_x8e_xb2_xe8_x90_x8d_xe4_xba_x91:
    gpack = globals()
    gpath = __name__ + '.i ' + __name__
    gcode = __import__(gpath, fromlist='sys')

    for gname in dir(gcode):
        gfunc = getattr(gcode, gname)
        if gname in gpack and getattr(gfunc, '__module__', None) == gpath:
            gfunc.__module__ = __package__
            try:
                gfunc.__doc__ = gpack[gname].__doc__
            except AttributeError:
                pass
            gpack[gname] = gfunc

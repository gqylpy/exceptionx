[<img alt="LOGO" src="https://python.org/favicon.ico" height="21" width="21"/>](http://gqylpy.com)
[![Release](https://img.shields.io/github/release/gqylpy/exceptionx.svg?style=flat-square")](https://github.com/gqylpy/exceptionx/releases/latest)
[![Python Versions](https://img.shields.io/pypi/pyversions/exceptionx)](https://pypi.org/project/exceptionx)
[![License](https://img.shields.io/pypi/l/exceptionx)](https://github.com/gqylpy/exceptionx/blob/master/LICENSE)
[![Downloads](https://static.pepy.tech/badge/exceptionx)](https://pepy.tech/project/exceptionx)

# exceptionx
English | [中文](https://github.com/gqylpy/exceptionx/blob/master/README_CN.md)

__exceptionx__ is a flexible and convenient Python exception handling library that allows you to dynamically create exception classes and provides various exception handling mechanisms.
> The predecessor of exceptionx is [gqylpy-exception](https://github.com/gqylpy/gqylpy-exception).

<kbd>pip3 install exceptionx</kbd>

## Dynamically Creating Exceptions

With exceptionx, you can instantly create exception classes when needed, without the need for advance definition. For example, if you want to throw an exception named `NotUnderstandError`, you can simply import the library and call it as follows:

```python
import exceptionx as ex

raise ex.NotUnderstandError(...)
```

Here, `NotUnderstandError` is not predefined by exceptionx but is dynamically created through the magic method `__getattr__` when you try to access `e.NotUnderstandError`. This flexibility means you can create exception classes with any name as needed.

Additionally, exceptionx ensures that the same exception class is not created repeatedly. All created exception classes are stored in the `e.__history__` dictionary for quick access later.

There is another usage, import and create immediately:

```python
from exceptionx import NotUnderstandError

raise NotUnderstandError(...)
```

## Powerful Exception Handling Capabilities

exceptionx also provides a series of powerful exception handling tools:

- `TryExcept`: A decorator that catches exceptions raised in the decorated function and outputs the exception information to the terminal (instead of throwing it). This helps prevent the program from crashing due to unhandled exceptions.
- `Retry`: A decorator that works similarly to `TryExcept` but attempts to re-execute the function, controlling the number of attempts and the interval between each retry through parameters. It throws an exception after reaching the maximum number of attempts.
- `TryContext`: A context manager that allows you to easily catch exceptions raised in a code block using the `with` statement and output the exception information to the terminal.

**Handling Exceptions in Functions with `TryExcept`**

```python
from exceptionx import TryExcept

@TryExcept(ValueError)
def func():
    int('a')
```

The default handling scheme is to output brief exception information to the terminal without interrupting program execution. Of course, it can also be output to logs or processed in other ways through parameters.

> According to Python programming conventions, exception types should be explicitly specified when handling exceptions. Therefore, when using the `TryExcept` decorator, it is necessary to explicitly pass the handled exception types.

**Retrying Exceptions in Functions with `Retry`**

```python
from exceptionx import Retry

@Retry(sleep=1, count=3)
def func():
    int('a')
```

If an exception is raised in the decorated function, it will attempt to re-execute the decorated function. The default behavior is to retry exceptions of type `Exception` and all its subclasses. Calling `Retry(sleep=1, count=3)` as above means a maximum of 3 attempts will be made, with a 1-second interval between each attempt.

`Retry` can be used in combination with `TryExcept` to retry exceptions first and then handle them if the retries are unsuccessful:

```python
from exceptionx import TryExcept, Retry

@TryExcept(ValueError)
@Retry(sleep=1, count=3)
def func():
    int('a')
```

**Handling Exceptions in Contexts with `TryContext`**

```python
from exceptionx import TryContext

with TryContext(ValueError):
    int('a')
```

With exceptionx, you can handle exceptions in Python programs more flexibly and efficiently, enhancing the robustness and reliability of your code.

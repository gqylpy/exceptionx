"""
─────────────────────────────────────────────────────────────────────────────────────────────────────
─██████████████─██████████████───████████──████████─██████─────────██████████████─████████──████████─
─██░░░░░░░░░░██─██░░░░░░░░░░██───██░░░░██──██░░░░██─██░░██─────────██░░░░░░░░░░██─██░░░░██──██░░░░██─
─██░░██████████─██░░██████░░██───████░░██──██░░████─██░░██─────────██░░██████░░██─████░░██──██░░████─
─██░░██─────────██░░██──██░░██─────██░░░░██░░░░██───██░░██─────────██░░██──██░░██───██░░░░██░░░░██───
─██░░██─────────██░░██──██░░██─────████░░░░░░████───██░░██─────────██░░██████░░██───████░░░░░░████───
─██░░██──██████─██░░██──██░░██───────████░░████─────██░░██─────────██░░░░░░░░░░██─────████░░████─────
─██░░██──██░░██─██░░██──██░░██─────────██░░██───────██░░██─────────██░░██████████───────██░░██───────
─██░░██──██░░██─██░░██──██░░██─────────██░░██───────██░░██─────────██░░██───────────────██░░██───────
─██░░██████░░██─██░░██████░░████───────██░░██───────██░░██████████─██░░██───────────────██░░██───────
─██░░░░░░░░░░██─██░░░░░░░░░░░░██───────██░░██───────██░░░░░░░░░░██─██░░██───────────────██░░██───────
─██████████████─████████████████───────██████───────██████████████─██████───────────────██████───────
─────────────────────────────────────────────────────────────────────────────────────────────────────

Copyright (C) 2022 GQYLPY <http://gqylpy.com>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import re
import time
import asyncio
import warnings
import functools
import traceback


class GqylpyException(metaclass=type(
    'SingletonMode', (type,),
    {'__new__': lambda *a: type.__new__(*a)()}
)):
    __history__ = {}

    def __getattr__(self, ename: str) -> type:
        try:
            eclass = self.__history__[ename]
        except KeyError:
            if ename[-5:] != 'Error':
                warnings.warn(
                    f'Strange exception class "{ename}", exception '
                    f'class name should end with "Error".'
                )
            eclass = self.__history__[ename] = type(
                ename, (self.GqylpyError,),
                {'__module__': self.GqylpyError.__module__}
            )
        return eclass

    def __getitem__(self, ename: str) -> type:
        return getattr(self, ename)

    class GqylpyError(Exception):
        __module__ = 'E'


class TryExcept:

    def __init__(
            self,
            etype:          [type, tuple],
            *,
            ignore:         bool          = False,
            output_raw_exc: bool          = False,
            logger:         ...           = None,
            ereturn:        ...           = None,
            ecallback:      ...           = None,
            eexit:          bool          = False
    ):
        self.etype          = etype
        self.ignore         = ignore
        self.output_raw_exc = output_raw_exc
        self.logger         = logger
        self.ereturn        = ereturn
        self.ecallback      = ecallback
        self.eexit          = eexit

    def __call__(self, func):
        @functools.wraps(func, updated=('__dict__', '__globals__',))
        def inner(*a, **kw):
            return self.core(func, *a, **kw)
        return inner

    def core(self, func, *a, **kw):
        try:
            return func(*a, **kw)
        except self.etype as e:
            self.exception_handling(func, e, *a, **kw)
        return self.ereturn

    def exception_handling(self, func, e: Exception, *a, **kw):
        local_instance: bool = self.__class__ in (TryExcept, TryExceptAsync)

        if not self.ignore:
            try:
                einfo: str = self.exception_analysis(func, e)
            except Exception as ee:
                einfo: str = f'{self.__class__.__name__}Error: {ee}'

            if not local_instance:
                einfo: str = f'[try:{kw["count"]}/{self.count}] {einfo}'

            if self.logger:
                (self.logger.error if local_instance else self.logger.warning)(einfo)
            else:
                now: str = time.strftime('%F %T', time.localtime())
                print(f'\033[0;31m[{now}] {einfo}\033[0m')

        if local_instance:
            self.ecallback and self.ecallback(*a, **kw)
            self.eexit     and exit(4)

    def exception_analysis(self, func, e: Exception) -> str:
        einfo: str = traceback.format_exc()

        if self.output_raw_exc:
            return einfo

        filepath: str = func.__globals__['__file__']
        funcpath: str = f'{func.__module__}.{func.__qualname__}'

        for line in reversed(einfo.split('\n')[1:-3]):
            if filepath in line:
                eline: str = re.search(
                    r'line \d+', line
                ).group().replace(' ', '')
                break
        else:
            eline: str = 'lineX'

        return f'[{funcpath}.{eline}.{e.__class__.__name__}] {e}'


class Retry(TryExcept):

    def __init__(
            self,
            etype:          [type, tuple] = Exception,
            *,
            count:          int           = 'N',
            cycle:          int           = 0,
            ignore:         bool          = False,
            output_raw_exc: bool          = False,
            logger:         ...           = None,
    ):
        self.count          = count
        self.cycle          = cycle

        super().__init__(
            etype,
            ignore=ignore,
            output_raw_exc=output_raw_exc,
            logger=logger
        )

    def core(self, func, *a, **kw):
        count = 0

        while True:
            try:
                return func(*a, **kw)
            except self.etype as e:
                count += 1
                self.exception_handling(func, e, count=count)
                if count == self.count:
                    raise e

            time.sleep(self.cycle)


class TryExceptAsync(TryExcept):

    async def core(self, func, *a, **kw):
        try:
            return await func(*a, **kw)
        except self.etype as e:
            self.exception_handling(func, e, *a, **kw)
        return self.ereturn


class RetryAsync(Retry):

    async def core(self, func, *a, **kw):
        count = 0

        while True:
            try:
                return await func(*a, **kw)
            except self.etype as e:
                count += 1
                self.exception_handling(func, e, count=count)
                if count == self.count:
                    raise e

            await asyncio.sleep(self.cycle)
from __future__ import annotations

import logging
import os

from virtualenv.discovery.builtin import Builtin
from virtualenv.discovery.builtin import check_path
from virtualenv.discovery.builtin import get_paths
from virtualenv.discovery.builtin import LazyPathDump
from virtualenv.discovery.builtin import PathPythonInfo
from virtualenv.discovery.builtin import possible_specs
from virtualenv.discovery.py_info import PythonInfo
from virtualenv.discovery.py_spec import PythonSpec


# Same as Builtin, needed for scope
class Mock(Builtin):
    def run(self):
        for python_spec in self.python_spec:
            result = get_interpreter(python_spec, self.try_first_with, self.app_data, self._env)
            if result is not None:
                return result
        return None

# Same as builtin, needed for scope


def get_interpreter(key, try_first_with, app_data=None, env=None):
    spec = PythonSpec.from_string_spec(key)
    logging.info('find interpreter for spec %r', spec)
    proposed_paths = set()
    env = os.environ if env is None else env
    for interpreter, impl_must_match in propose_interpreters(spec, try_first_with, app_data, env):
        key = interpreter.system_executable, impl_must_match
        if key in proposed_paths:
            continue
        logging.info('proposed %s', interpreter)
        if interpreter.satisfies(spec, impl_must_match):
            logging.debug('accepted %s', interpreter)
            return interpreter
        proposed_paths.add(key)

# Current interpreter is removed


def propose_interpreters(spec, try_first_with, app_data, env=None):
    # 0. try with first
    env = os.environ if env is None else env
    for py_exe in try_first_with:
        path = os.path.abspath(py_exe)
        try:
            # Windows Store Python does not work with os.path.exists, but does for os.lstat
            os.lstat(path)
        except OSError:
            pass
        else:
            yield PythonInfo.from_exe(os.path.abspath(path), app_data, env=env), True

    # 1. if it's a path and exists
    if spec.path is not None:
        try:
            # Windows Store Python does not work with os.path.exists, but does for os.lstat
            os.lstat(spec.path)
        except OSError:
            if spec.is_abs:
                raise
        else:
            yield PythonInfo.from_exe(os.path.abspath(spec.path), app_data, env=env), True
        if spec.is_abs:
            return
    # finally just find on path, the path order matters (as the candidates are less easy to control by end user)
    paths = get_paths(env)
    tested_exes = set()
    for pos, path in enumerate(paths):
        path_str = str(path)
        logging.debug(LazyPathDump(pos, path_str, env))
        for candidate, match in possible_specs(spec):
            found = check_path(candidate, path_str)
            if found is not None:
                exe = os.path.abspath(found)
                if exe not in tested_exes:
                    tested_exes.add(exe)
                    interpreter = PathPythonInfo.from_exe(exe, app_data, raise_on_error=False, env=env)
                    if interpreter is not None:
                        yield interpreter, match

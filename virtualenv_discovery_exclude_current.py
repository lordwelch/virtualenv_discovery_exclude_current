from __future__ import annotations

import logging
import os

from virtualenv.discovery.builtin import Builtin
from virtualenv.discovery.builtin import fs_path_id
from virtualenv.discovery.builtin import get_paths
from virtualenv.discovery.builtin import IS_WIN
from virtualenv.discovery.builtin import LazyPathDump
from virtualenv.discovery.builtin import path_exe_finder
from virtualenv.discovery.builtin import PathPythonInfo
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


def propose_interpreters(  # noqa: C901, PLR0912, PLR0915
    spec: PythonSpec,
    try_first_with,
    app_data=None,
    env=None,
):
    # 0. try with first
    env = os.environ if env is None else env
    tested_exes: set[str] = set()
    for py_exe in try_first_with:
        path = os.path.abspath(py_exe)
        try:
            os.lstat(path)  # Windows Store Python does not work with os.path.exists, but does for os.lstat
        except OSError:
            pass
        else:
            exe_raw = os.path.abspath(path)
            exe_id = fs_path_id(exe_raw)
            if exe_id in tested_exes:
                continue
            tested_exes.add(exe_id)
            yield PythonInfo.from_exe(exe_raw, app_data, env=env), True

    # 1. if it's a path and exists
    if spec.path is not None:
        try:
            os.lstat(spec.path)  # Windows Store Python does not work with os.path.exists, but does for os.lstat
        except OSError:
            if spec.is_abs:
                raise
        else:
            exe_raw = os.path.abspath(spec.path)
            exe_id = fs_path_id(exe_raw)
            if exe_id not in tested_exes:
                tested_exes.add(exe_id)
                yield PythonInfo.from_exe(exe_raw, app_data, env=env), True
        if spec.is_abs:
            return
    else:

        # 3. otherwise fallback to platform default logic
        if IS_WIN:
            from .windows import propose_interpreters  # noqa: PLC0415

            for interpreter in propose_interpreters(spec, app_data, env):
                exe_raw = str(interpreter.executable)
                exe_id = fs_path_id(exe_raw)
                if exe_id in tested_exes:
                    continue
                tested_exes.add(exe_id)
                yield interpreter, True
    # finally just find on path, the path order matters (as the candidates are less easy to control by end user)
    find_candidates = path_exe_finder(spec)
    for pos, path in enumerate(get_paths(env)):
        logging.debug(LazyPathDump(pos, path, env))
        for exe, impl_must_match in find_candidates(path):
            exe_raw = str(exe)
            exe_id = fs_path_id(exe_raw)
            if exe_id in tested_exes:
                continue
            tested_exes.add(exe_id)
            interpreter = PathPythonInfo.from_exe(exe_raw, app_data, raise_on_error=False, env=env)
            if interpreter is not None:
                yield interpreter, impl_must_match

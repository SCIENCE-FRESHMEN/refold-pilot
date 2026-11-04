"""Check the installed cache-path helper without loading GPU model code."""

import ast
import json
import os
from pathlib import Path

from platformdirs import user_cache_dir


def main() -> None:
    source = Path('/usr/local/lib/python3.12/dist-packages/cuequivariance_ops/triton/cache_manager.py')
    tree = ast.parse(source.read_text())
    names = {'overridden_cache_dir', 'get_triton_cache_dir'}
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in functions} != names:
        raise ValueError('Installed cache helper interface changed')
    namespace = {'os': os, 'Path': Path, 'user_cache_dir': user_cache_dir}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), namespace)
    path = namespace['get_triton_cache_dir']().resolve()
    if not path.is_relative_to(Path.cwd().resolve()):
        raise ValueError('Compiler cache escapes the task directory')
    sentinel = path / '.cache-preflight'
    sentinel.write_text('cache-write-check')
    assert sentinel.read_text() == 'cache-write-check'
    sentinel.unlink()
    print(json.dumps({'status': 'passed', 'installed_cache_helper_checked': True,
                      'task_local_cache': True, 'write_read_roundtrip': True,
                      'gpu_inference_tested': False}))


if __name__ == '__main__':
    main()

import os
import subprocess
import tempfile


def run(*args: str) -> tuple[int, bytes]:
    cmd = ['photons', '--no-user'] + list(args)
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode, result.stdout.rstrip()


def test_invalid_config():
    code, stdout = run('does-not-exist.xml')
    assert code == 1
    assert stdout.endswith(b"No such file or directory: 'does-not-exist.xml'")


def test_alias_and_name():
    code, stdout = run('--name', 'n', '--alias', 'a')
    assert code == 1
    assert stdout.endswith(b"You cannot specify both the alias ('a') and the name ('n') to start a Service.")


def test_bad_kwargs():
    code, stdout = run('--name', 'n', '--kwargs', 'host=localhost')
    assert code == 1
    assert stdout.endswith(b"Received the following kwargs: host=localhost")


def test_invalid_name():
    code, stdout = run('--name', 'n', '--kwargs', '{"host": "localhost"}')
    assert code == 1
    assert stdout.endswith(b"No Service exists with the name 'n'")


def test_invalid_alias():
    file = os.path.join(tempfile.gettempdir(), 'pr-single-photons-dummy.xml')
    with open(file, mode='wt') as f:
        f.write('<?xml version="1.0" encoding="UTF-8" ?>\n<photons/>')

    code, stdout = run('--alias', 'a', file)
    assert code == 1
    assert stdout.endswith(b"No EquipmentRecord exists with the alias 'a'")

    os.remove(file)


def test_find():
    code, stdout = run('--find')
    assert code == 0
    assert stdout.startswith(b'Finding equipment (network timeout is 2.0 seconds)...')


def test_find_with_timeout():
    code, stdout = run('-f 0.4')
    assert code == 0
    assert stdout.startswith(b'Finding equipment (network timeout is 0.4 seconds)...')

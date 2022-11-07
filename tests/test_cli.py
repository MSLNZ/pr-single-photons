import subprocess


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
    code, stdout = run('--alias', 'a', '--kwargs', '{"host": "localhost", "port": 2000}')
    assert code == 1
    assert stdout.endswith(b"No EquipmentRecord exists with the alias 'a'")

# -*- coding: utf-8 -*-
#
import configparser
from datetime import datetime
from distutils.version import LooseVersion
import json
import os
import requests
from sys import platform
import tempfile


class _bash_color:
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    DARKCYAN = '\033[36m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


_config_file = os.path.join(os.path.expanduser('~'), '.pypi_update_checker')
_log_file = os.path.join(
        tempfile.gettempdir(),
        'pypi_update_checker_last_check_time'
        )


def _get_sbc():
    if not os.path.exists(_config_file):
        # add default config
        config = configparser.ConfigParser()
        config['DEFAULT'] = {
            'SecondsBetweenChecks': 24*60*60,
            }
        with open(_config_file, 'w') as handle:
            config.write(handle)

    # read config
    config = configparser.ConfigParser()
    config.read(_config_file)

    return int(config['DEFAULT']['SecondsBetweenChecks'])


def _get_last_check_time(name):
    if not os.path.exists(_log_file):
        return None
    with open(_log_file, 'r') as handle:
        d = json.load(handle)
        if name in d:
            last_checked = datetime.strptime(
                d[name],
                '%Y-%m-%d %H:%M:%S'
                )
        else:
            return None
    return last_checked


def _log_time(name):
    if os.path.exists(_log_file):
        with open(_log_file, 'r') as handle:
            d = json.load(handle)
    else:
        d = {}

    d[name] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(_log_file, 'w') as handle:
        json.dump(d, handle)
    return


def needs_checking(name):
    seconds_between_checks = _get_sbc()

    if seconds_between_checks < 0:
        return False

    # get the last time we checked and compare with seconds_between_checks
    last_checked = _get_last_check_time(name)
    if last_checked is not None and \
            (datetime.now() - last_checked).total_seconds() \
            < seconds_between_checks:
        return False

    return True


def check_and_notify(name, installed_version, semantic_versioning=True):
    try:
        _check(
            name,
            installed_version,
            semantic_versioning=semantic_versioning,
            )
        # write timestamp to log file
        _log_time(name)
    except RuntimeError:
        pass

    return


def get_pypi_version(name):
    r = requests.get('https://pypi.python.org/pypi/%s/json' % name)
    if not r.ok:
        raise RuntimeError('Response code %s.' % r.status_code)
    data = r.json()
    return data['info']['version']


def _check(name, installed_version, semantic_versioning):
    upstream_version = get_pypi_version(name)
    iv = LooseVersion(installed_version)
    uv = LooseVersion(upstream_version)
    if iv < uv:
        _print_update_warning(
            name,
            uv,
            iv,
            semantic_versioning
            )
    return


def _change_in_leftmost_nonzero(a, b):
    leftmost_changed = False
    for k in range(min(len(a), len(b))):
        if a[k] == 0 and b[k] == 0:
            continue
        leftmost_changed = (a[k] != b[k])
        break
    return leftmost_changed


def _print_update_warning(
        name,
        uv,
        iv,
        semantic_versioning
        ):
    print(
        '>\n> Upgrade to   ' +
        _bash_color.GREEN +
        '%s %s' % (name, uv.vstring) +
        _bash_color.END +
        '    available! (installed: %s)\n>' % iv.vstring
        )
    # Check if the leftmost nonzero version number changed. If yes,
    # this means an API change according to Semantic Versioning.
    if semantic_versioning and \
            _change_in_leftmost_nonzero(iv.version, uv.version):
        print(
           ('> ' +
            _bash_color.YELLOW +
            '%s\'s API changes in this upgrade. '
            'Changes to your code may be necessary.\n' +
            _bash_color.END +
            '>'
            ) % name
           )
    if platform == 'linux' or platform == 'linux2':
        print((
            '> To upgrade %s with pip, type\n>\n'
            '>    pip install -U %s\n>\n'
            '> To upgrade all pip-installed packages, type\n>\n'
            '>    pip freeze --local | grep -v \'^\-e\' | '
            'cut -d = -f 1 | xargs -n1 pip install -U\n>'
            ) % (name, name))

    print(
        '> To disable these checks, '
        'set SecondsBetweenChecks in %s to -1.\n>' % _config_file
        )

    return

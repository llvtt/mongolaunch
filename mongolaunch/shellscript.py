'''Utilities for managing EC2 instances with shell scripts'''

import os.path
import re

from mongolaunch.settings import ML_PATH

LINUX_INSTALL = "install-linux.sh"
WINDOWS_INSTALL = "install-windows.ps1"


def _make_substitutions(template, context):
    patt = '(%s)' % '|'.join(('{{\s*%s\s*}}' % k) for k in context.keys())
    # remove {{ and }} from key (must be at beginning/end of match)
    repl = lambda m: context.get(m.group(0)[2:][:-2].strip(), "")
    return re.sub(patt, repl, template)


def get_script(template_name, context, windows=False):
    template = "%s-%s" % (
        template_name,
        "windows.ps1" if windows else "linux.sh"
    )
    with open(os.path.join(ML_PATH, "shell", template), 'rb') as fd:
        return _format_newlines(_make_substitutions(fd.read(), context),
                                windows=windows)


def script_from_config(context, windows=False):
    '''Provide a shell script that bootstraps the instance described in
    <context> with MongoDB

    '''
    script = WINDOWS_INSTALL if windows else LINUX_INSTALL
    with open(os.path.join(ML_PATH, "shell", script), "rb") as fd:
        return _format_newlines(_make_substitutions(fd.read(), context),
                                windows=windows)


def build_context(config, instance_config):
    '''Produce a flat dictionary that can be used with script_for_image
    out of the loaded json configuration and the particular configuration
    for the instance

    '''
    inst_conf = dict((k, v) for k, v in config.items() if k != 'instances')
    inst_conf.update(instance_config)
    inst_conf.update(instance_config['mongo'])
    return inst_conf


def _format_newlines(document, windows=True):
    if windows:
        # ugh...
        return document.replace(
            "\r\n", "\n"
        ).replace(
            "\r", "\n"
        ).replace(
            "\n", "\r\n"
        ).strip()
    else:
        return document.replace(
            "\r\n", "\n"
        ).replace(
            "\r", "\n"
        ).strip()

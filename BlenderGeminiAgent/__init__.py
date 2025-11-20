# SPDX-License-Identifier: GPL-3.0-or-later

_modules: None | tuple = None


def _ensure_modules():
    global _modules
    if _modules is None:
        from . import hello_operator, hello_ui_panel
        _modules = (hello_operator, hello_ui_panel)


def register():
    _ensure_modules()
    for m in _modules:
        m.register()


def unregister():
    _ensure_modules()
    for m in reversed(_modules):
        m.unregister()

# SPDX-License-Identifier: GPL-3.0-or-later

from . import operators
from . import server

def register():
    operators.register()

def unregister():
    operators.unregister()
    server.stop_server()

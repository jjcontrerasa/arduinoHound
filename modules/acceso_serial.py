"""Coordina el monitor explicito con el sondeo automatico de RF Hound."""

import threading

_guardia = threading.Lock()
_puertos = {}


def acceso_puerto(puerto):
    with _guardia:
        if puerto not in _puertos:
            _puertos[puerto] = (threading.Lock(), threading.Event())
        return _puertos[puerto]


def reservado_por_reader(puerto):
    return acceso_puerto(puerto)[1].is_set()

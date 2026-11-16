# -*- coding: utf-8 -*-
import functools
import inspect
import logging

import werkzeug.exceptions

from odoo import models
from odoo.http import request

_logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=2048)
def required_params(func):
    """Names the controller function needs and has no default for.

    ``func`` is the route's original function, so its first parameter is
    the controller instance (``self``). A function whose signature can't
    be read, or that takes anything through ``*args``/``**kwargs`` only,
    requires nothing as far as this check is concerned.

    ``follow_wrapped=False``: a decorator between ``@route`` and the
    function may supply some values itself (a record looked up from a
    token, say). Only the outermost signature is what core calls, so only
    that one is checked; a decorated endpoint is simply left alone.
    """
    try:
        params = list(inspect.signature(func, follow_wrapped=False).parameters.values())
    except (TypeError, ValueError):
        return frozenset()
    names = set()
    for index, param in enumerate(params):
        if param.default is not inspect.Parameter.empty:
            continue
        if param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD and index > 0:
            names.add(param.name)
        elif param.kind == inspect.Parameter.KEYWORD_ONLY:
            names.add(param.name)
    return frozenset(names)


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _dispatch(cls, endpoint):
        # request.params already holds the path's own values (<int:id>
        # and the like) merged with the query string, form or JSON params,
        # exactly what core then calls the endpoint with.
        func = getattr(endpoint, 'original_endpoint', None)
        if func is not None and request:
            missing = required_params(func) - set(request.params)
            if missing:
                _logger.info(
                    "%s %s is missing %s; answering 404",
                    request.httprequest.method, request.httprequest.path,
                    ", ".join(sorted(missing)),
                )
                raise werkzeug.exceptions.NotFound()
        return super()._dispatch(endpoint)

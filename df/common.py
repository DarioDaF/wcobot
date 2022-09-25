from functools import wraps

def wrapConsumer(f):
    @wraps(f)
    def _(*args):
        return lambda v: f(v, *args)
    return _

def pipe(*fs):
    def _(v):
        for f in reversed(fs):
            v = f(v)
        return v
    return _

__all__ = ['wrapConsumer', 'pipe']

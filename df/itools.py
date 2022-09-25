from .common import wrapConsumer

def ifile(f, MAX_BUF = 1024):
    buf = f.read(MAX_BUF)
    while buf != b'':
        yield from buf
        buf = f.read(MAX_BUF)

@wrapConsumer
def iafter(it, target):
    ''' Warning: does not work for overlapping '''
    pos = 0
    for c in it:
        if c == target[pos]:
            pos += 1
            if pos >= len(target):
                # Just read the target, now you are after
                yield from it
                return
        else:
            pos = 0

@wrapConsumer
def ibefore(it, target):
    ''' Warning: does not work for overlapping '''
    pos = 0
    for c in it:
        if c == target[pos]:
            pos += 1
            if pos >= len(target):
                # Already ended
                return
        else:
            yield from target[:pos]
            yield c
            pos = 0

@wrapConsumer
def igroup(it, start, stop):
    inData = len(start) == 0
    pos = 0
    res = b''
    for c in it:
        if c == (stop if inData else start)[pos]:
            pos += 1
            if pos >= len(stop if inData else start):
                # Just read the target, now you are after
                if inData:
                    yield res
                inData = not inData or len(start) == 0
                pos = 0
                res = b''
        else:
            if inData:
                res += stop[:pos] + bytes([c])
            pos = 0

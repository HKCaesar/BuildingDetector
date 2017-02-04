import urllib2
import decorator, time

# Allow urlopen requests to retry n times
def retry(howmany, *exception_types, **kwargs):
    timeout = kwargs.get('timeout', 0.0) # seconds
    @decorator.decorator
    def tryIt(func, *fargs, **fkwargs):
        for _ in xrange(howmany):
            try: return func(*fargs, **fkwargs)
            except exception_types or Exception:
                if timeout is not None: time.sleep(timeout)
    return tryIt

@retry(3)
def urlopen_with_retry(url):
    return urllib2.urlopen(url)
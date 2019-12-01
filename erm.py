import ccxt
import logging


class testT:
    def __init__(self):
        self.a = 0

    def _try_until_timeout(self, func, *args, **kwargs):
        func(*args, **kwargs)
        self.a = 1

    def test_func(self, a, b, c=0):
        print(a,b,c)

    def test(self):
        self._try_until_timeout(self.test_func, 1, 5, c=10)


t = testT()
t.test()
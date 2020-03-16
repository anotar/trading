import ccxt
bi = ccxt.binance()
iso = bi.iso8601(bi.milliseconds()).iso
print(iso)
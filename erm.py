a = {'a':{'b':'c'}}
d = a['a']
d['b'] = 'd'
del d['b']
print(a)
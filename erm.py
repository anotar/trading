import pandas as pd
dict_t = {'a': 1, 'b':2}
list_t = [1,2,3,]
data = pd.Series(list)
if dict_t:
    print(1)
if list_t:
    print(2)
if data.empty:
    print(data)
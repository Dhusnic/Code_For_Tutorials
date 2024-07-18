dictionaries = {"a": 1, "b": 2, "c": "dhusnic", "d": "gopinath"}
print(dictionaries)
print(len(dictionaries))
print(set(dictionaries.keys()))
print(list(dictionaries.values()))
print(dictionaries.pop("a"))
print(dictionaries)
print(list(dictionaries.items()))
print(type(dictionaries))
for i in dictionaries:
    print(i)
    print(dictionaries[i])
    print("="*50)

for i,j in dictionaries.items():
    print(i," ",j)
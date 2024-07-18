list_name1=[1,2,3,4,5,6,7]
print(list_name1)
print(list_name1[0])
print(list_name1[-1])
print(list_name1[3])

list_name2=[8,9,10,11,12,13,14,15]

print(list_name1+list_name2)
list_name1.append(8)
print(list_name1)
print(list_name2)
list_name1.extend(list_name2)
print(list_name1)

#slicing
print("-"*60)
print(list_name1[::-1])
print(list_name1[0:-1])
print(list_name1[3:0:-1])
print(list_name1[-2:])
print(list_name1.index(8))
# print(list_name1.index(25))

for i in list_name1:
    print(i)
x=0
while x<6:
    print(x)
    x+=1

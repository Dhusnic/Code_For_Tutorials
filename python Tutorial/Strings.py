string = "helloWorld "
print(string[0])
print("")
print(len(string))
print("")
for i in range(0, len(string)):
    print(string[i])

print(string.upper())
print(string.capitalize())
print(string.lower())

String1 = string + " hello"
print(String1)

print(string * 5)

print("{} {} {}".format("hello ", "everyone", "python"))
print("{1} {2} {0}".format("hello ", "everyone", "python"))
print("")
print("{0:8} | {1:8}".format("fruit", "quantity"))
print("{0:8} | {1:8}".format("mango", "30"))
print("{0:8} | {1:8}".format("apple", "20"))
print("{0:8} | {1:8}".format("apple", "10"))
print("")
print("{0:8} | {1:8}".format("fruit", "quantity"))
print("{0:8} | {1:8}".format("mango", "30"))
print("{0:8} | {1:8}".format("apple", "20"))
print("{0:8} | {1:8}".format("apple", "10"))

#excersise 1
animal="cat"
vegtable="carrot"
mineral="gold"
print("Here is an Animal , A vegtable , and a mineral")
print(animal)
print(vegtable)
print(mineral)


#excersice 2
inp=input()
print(inp)


#excercise 3
text=input("what would you like the cat to say?")
print(' {}'.format('_'*len(text)))
print("<{}>".format(text))
print(' {}'.format('_'*len(text)))
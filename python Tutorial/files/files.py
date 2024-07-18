file = open("./files/abc.txt")
print(file.read())
print(file.close())
print(file.closed)

with open("./files/abc.txt") as host:
    print(host.read())
print(host.closed)

# file=open('./list.py')
with open("./files/abc.txt") as the_file:
    for line in the_file:
        print(line)
""""
Mode 
r-open for reading
w-open for writing , truncating first
x-create a nwe file and open it for writing
a-open for writing appending to file
+ - open  a file for updateing
b - binary mode
t - text Mode
"""
the_file=open("./files/abc.txt",'w')
the_file.write("hello everyone im new text")
the_file.close()
print(the_file.closed)
the_file=open("./files/abc.txt",'+a')
the_file.write("hello everyone im new text 2")
the_file.close()
print(the_file.closed)







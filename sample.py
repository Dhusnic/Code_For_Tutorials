# Global scope
x = 10

def outer_function():
    # Enclosing scope
    y = 20
    
    def inner_function():
        # Local scope
        z = 30
        print("Inner function:")
        print("x (global):", x)
        print("y (enclosing):", y)
        print("z (local):", z)
    
    inner_function()
    print("Outer function:")
    print("x (global):", x)
    print("y (enclosing):", y)
    # z is not accessible here
    # print("z (local):", z)  # This would raise a NameError

outer_function()
print("Global scope:")
print("x (global):", x)
# y and z are not accessible here
# print("y (enclosing):", y)  # This would raise a NameError
# print("z (local):", z)  # This would raise a NameError
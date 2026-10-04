from security import create_token, decode_token

token = create_token("bob", "employee")
print("Token:", token)

decoded = decode_token(token)
print("Decoded:", decoded)
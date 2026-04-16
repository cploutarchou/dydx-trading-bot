from src.api.auth_utils import JWTUtils

print("Creating token...")
access = JWTUtils.create_access_token({"sub": "test_user", "roles": ["user"]})
print("Token:", access)
print("Verifying token...")
payload = JWTUtils.verify_token(access)
print("Verified payload:", payload)

# test invalid token
print("Verifying invalid token...", JWTUtils.verify_token(access + "x"))

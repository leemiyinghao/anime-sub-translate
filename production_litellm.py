import os

# Prevent litellm from loading .env files
# We will load the environment variables via setting module.
os.environ["LITELLM_MODE"] = "PRODUCTION"
import litellm

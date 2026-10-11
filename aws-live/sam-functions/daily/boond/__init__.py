import logging

# Lambda sets the root logger to WARNING; per-field and Bedrock outcome lines are INFO.
logging.getLogger("boond").setLevel(logging.INFO)

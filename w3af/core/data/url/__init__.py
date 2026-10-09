import ssl

# The stdlib http clients verify certificates by default (PEP 476), the scanner
# must be able to talk to any target so we disable it globally
# https://github.com/andresriancho/w3af/issues/8115
ssl._create_default_https_context = ssl._create_unverified_context

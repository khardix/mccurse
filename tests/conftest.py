"""Global test configuration"""


import os

import betamax


# Ensure cassete dir
CASSETE_DIR = 'tests/cassetes/'
if not os.path.exists(CASSETE_DIR):
    os.makedirs(CASSETE_DIR)

with betamax.Betamax.configure() as config:
    config.cassette_library_dir = CASSETE_DIR

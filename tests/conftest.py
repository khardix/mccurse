"""Global test configuration"""


import os

import betamax


# Ensure cassete dir
CASSETE_DIR = 'tests/cassetes/'
if not os.path.exists(CASSETE_DIR):
    os.makedirs(CASSETE_DIR)

record_mode = 'none' if os.environ.get('TRAVIS_BUILD') else 'once'

with betamax.Betamax.configure() as config:
    config.cassette_library_dir = CASSETE_DIR
    config.default_cassette_options.update({
        'record_mode': record_mode,
        'preserve_exact_body_bytes': True,
    })

#! /bin/bash

# ignore collections warning about deprecation warning, there's nothing we can do about that for now
pytest -W ignore::DeprecationWarning "$@"
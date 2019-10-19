#! /bin/bash

# ignore collections warning about deprecation warning, there's nothing we can do about that for now
sleep 20 && pytest -W ignore::DeprecationWarning "$@"
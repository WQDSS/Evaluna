#! /bin/bash

# ignore collections warning about deprecation warning, there's nothing we can do about that for now
sleep 10 && pytest -W ignore::DeprecationWarning "$@"
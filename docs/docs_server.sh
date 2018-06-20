#!/usr/bin/env bash

sphinx-apidoc -f -o docs/source/ frkl
sphinx-autobuild -p 8001 docs build/html

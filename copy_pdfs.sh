#!/bin/bash

for file in downloads/*.pdf; do
    [[ "$file" =~ ^downloads/[0-9]+.*[Ss]emester.*\.pdf$ ]] && cp "$file" download/
done

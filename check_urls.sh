#!/bin/bash

# Extract all URLs
for recipe in recipes/*.recipe; do
    url=$(grep -oP '^source\s*=\s*\n\s+\K(http\S+)' "$recipe" 2>/dev/null || grep -oP '^\s*(http\S+)' "$recipe" | head -n1)
    if [ -n "$url" ]; then
        status=$(curl -sL -I -m 10 "$url" | head -n 1 | awk '{print $2}')
        if [ "$status" != "200" ]; then
            echo "$recipe: $url -> STATUS $status"
        fi
    fi
done

#!/bin/bash
# Start all *.service units in the current directory

# Loop over any .service files; if none exist, the loop won’t run
for service_file in *.service; do
    # Skip if no matching files (glob expands to literal pattern when no matches)
    [ -e "$service_file" ] || continue

    echo "Starting $service_file..."
    sudo systemctl start "$service_file"
done

# Optional: inform if no services were found
if ! compgen -G "*.service" > /dev/null; then
    echo "No .service files found in the current directory."
fi

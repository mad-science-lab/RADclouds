# Version: V26.284.1900
ARG BUILD_FROM
FROM $BUILD_FROM

# Standard library only - no pip packages.
RUN apk add --no-cache python3 tzdata

# The repository root is the add-on folder, so these paths are repo-relative.
# (build_addon.ps1 stages the same layout for installing from the Samba share.)
COPY radclouds/ /opt/radclouds/radclouds/
COPY settings.example.json /opt/radclouds/

COPY addon-run.sh /run.sh
RUN chmod a+x /run.sh
CMD [ "/run.sh" ]

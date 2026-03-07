FROM node:22-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git jq ripgrep python3 && \
    rm -rf /var/lib/apt/lists/* && \
    ln -s /usr/bin/python3 /usr/bin/python

RUN npm install -g openclaw@latest shards-cli@latest

# Install shards wrapper to prevent self-targeting
RUN SHARDS_PATH=$(which shards) && \
    mv "$SHARDS_PATH" "${SHARDS_PATH}.real"
COPY shards-wrapper.sh /usr/local/bin/shards
RUN chmod +x /usr/local/bin/shards

RUN mkdir -p /home/node/.openclaw \
             /home/node/.config/shards \
             /home/node/.cache \
             /home/node/.local/share && \
    chown -R node:node /home/node

COPY --chown=node:node entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Install elite skills
COPY --chown=node:node skills/ /home/node/.openclaw/skills/

USER node
WORKDIR /home/node

EXPOSE 18789

ENTRYPOINT ["entrypoint.sh"]

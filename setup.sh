#!/bin/bash
# Usage: source setup.sh
#
# Non-secret configuration for local development and tests. Secrets (role
# tokens, or a non-default database password) go in setup.local.sh, which is
# git-ignored and loaded at the end of this file. Production settings live in
# the hosting platform (see render.yaml).

export FLASK_APP=api

# Database (local defaults; override in setup.local.sh)
export DATABASE_URL='postgresql://postgres:postgres@localhost:5432/aeropress'
export TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:5432/aeropress_test'

# Auth0
export AUTH0_DOMAIN='dev-chmt7px7cn0johtc.us.auth0.com'
export AUTH0_CLIENT_ID='g7iSOV53ZIYI2Uopn6ulAAq8XkioM00Y'
export API_AUDIENCE='aeropress-brews'
# Tokens are signed with RS256 (asymmetric), so there is no shared signing
# secret: the API verifies signatures with Auth0's public keys, fetched from
# https://$AUTH0_DOMAIN/.well-known/jwks.json
export ALGORITHMS='RS256'

# Role tokens for the tests. Set real values in setup.local.sh:
#   export CONTRIBUTOR_TOKEN='...'
#   export OWNER_TOKEN='...'
export CONTRIBUTOR_TOKEN=''
export OWNER_TOKEN=''

# Load local secrets, if present
SETUP_LOCAL="$(dirname "${BASH_SOURCE[0]}")/setup.local.sh"
if [ -f "$SETUP_LOCAL" ]; then
    source "$SETUP_LOCAL"
fi
unset SETUP_LOCAL

#!/usr/bin/env bash
# Shared docker compose file selection from ./.env (sourced by start.sh / update.sh).
compose_env() {
  COMPOSE=(docker compose -f docker-compose.yml)
  local profile="${DEPLOY_PROFILE:-}"
  local llm="${LLM_AUTH_MODE:-}"

  if [[ -f .env ]]; then
    if [[ -z "$profile" ]]; then
      profile="$(grep -E '^DEPLOY_PROFILE=' .env | tail -1 | cut -d= -f2- | tr -d '\r"'"'"' ')"
    fi
    if [[ -z "$llm" ]]; then
      llm="$(grep -E '^LLM_AUTH_MODE=' .env | tail -1 | cut -d= -f2- | tr -d '\r"'"'"' ')"
    fi
    if [[ -z "$profile" ]]; then
      local secure
      secure="$(grep -E '^SESSION_COOKIE_SECURE=' .env | tail -1 | cut -d= -f2- | tr -d '\r"'"'"' ')"
      if [[ "$secure" == "true" ]]; then
        profile=prod
      else
        profile=dev
      fi
    fi
  fi

  profile="${profile:-dev}"
  if [[ "$profile" == "prod" ]]; then
    COMPOSE+=(-f docker-compose.prod.yml)
  elif [[ "$llm" == "chatgpt_oauth" ]]; then
    COMPOSE+=(-f docker-compose.oauth.yml)
    if [[ -z "${OAUTH_AUTH_HOST_PATH:-}" ]]; then
      local oauth_path
      oauth_path="$(grep -E '^CODEX_OAUTH_AUTH_PATH=' .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\r"'"'"' ')"
      oauth_path="${oauth_path/#\~/$HOME}"
      export OAUTH_AUTH_HOST_PATH="${oauth_path:-$HOME/.oauth_codex/auth.json}"
    fi
  fi
}

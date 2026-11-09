#!/bin/sh
set -eu
PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT"
WAR=${JENKINS_WAR:-"$PROJECT_ROOT/.tools/jenkins.war"}
JAVA=java
if [ -n "${JAVA_HOME:-}" ]; then JAVA="$JAVA_HOME/bin/java"; fi
export JENKINS_HOME=${JENKINS_HOME:-"$PROJECT_ROOT/.local/jenkins-home"}
test -f "$WAR" || { echo 'Missing verified Jenkins WAR; see docs/ci-demo.md'; exit 1; }
mkdir -p "$PROJECT_ROOT/.local/jenkins-runtime"
exec "$JAVA" -Xms256m -Xmx1536m -jar "$WAR" --httpPort="${JENKINS_PORT:-8080}" --httpListenAddress=127.0.0.1 --webroot="$PROJECT_ROOT/.local/jenkins-runtime/webroot"

#!/usr/bin/env bash
# shell-function.sh — Shell function template for `memoria` command
# This file is sourced from shell-init.sh (generated during install)
# It provides the `memoria` command that dispatches to subcommands

MEMORIA_DIR="${MEMORIA_DIR:-${HOME}/.local/share/memoria}"

memoria() {
    local cmd="${1:-help}"
    shift 2>/dev/null || true

    case "$cmd" in
        update)
            local version=""
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --version) version="$2"; shift 2 ;;
                    *) shift ;;
                esac
            done
            bash "$MEMORIA_DIR/memoria-install.sh" update "$version"
            ;;
        check)
            bash "$MEMORIA_DIR/memoria-install.sh" check
            ;;
        health)
            bash "$MEMORIA_DIR/memoria-install.sh" health
            ;;
        version)
            bash "$MEMORIA_DIR/memoria-install.sh" version
            ;;
        uninstall)
            local yes_flag="false"
            [[ "${1:-}" == "--yes" ]] && yes_flag="true"
            bash "$MEMORIA_DIR/memoria-install.sh" uninstall "$yes_flag"
            ;;
        help|*)
            echo "Usage: memoria <command>"
            echo ""
            echo "Commands:"
            echo "  update [--version X.Y.Z]  Update to latest (or specific) version"
            echo "  check                     Check for available updates"
            echo "  health                    Run system health check"
            echo "  version                   Show installed version"
            echo "  uninstall [--yes]         Remove memoria installation"
            echo "  help                      Show this help"
            ;;
    esac
}

#!/bin/bash

# ANSI Color Codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

show_help() {
    echo -e "${CYAN}QMAP Environment Setup Tool${NC}"
    echo -e "Builds and manages isolated Conda environments for QMAP benchmarking."
    echo ""
    echo -e "${YELLOW}Usage:${NC}"
    echo "  ./setup_envs.sh [OPTIONS] [VENDOR]"
    echo ""
    echo -e "${YELLOW}Options:${NC}"
    echo "  -h, --help      Show this help message and exit"
    echo "  --force         Force rebuild of environments (removes existing ones)"
    echo ""
    echo -e "${YELLOW}Arguments:${NC}"
    echo "  VENDOR          Target a specific environment (ibm, iqm, ionq, quantinuum)."
    echo "                  If omitted with --force, rebuilds ALL environments."
    echo ""
    echo -e "${YELLOW}Examples:${NC}"
    echo "  ./setup_envs.sh                 # Standard run (skips existing envs)"
    echo "  ./setup_envs.sh --force         # Nuke and rebuild everything"
    echo "  ./setup_envs.sh --force ibm     # Rebuild only the qmap_ibm environment"
    exit 0
}

# Array of "vendor:yaml_path"
VENDORS=(
    "ibm:envs/ibm.yml"
    "iqm:envs/iqm.yml"
    "ionq:envs/ionq.yml"
    "quantinuum:envs/quantinuum.yml"
)

SUCCESSFUL_BUILDS=""
FAILED_BUILDS=""
SKIPPED_BUILDS=""
FORCE_ALL=false
TARGET_VENDOR=""

if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    show_help
elif [[ "$1" == "--force" ]]; then
    if [[ -n "$2" ]]; then
        TARGET_VENDOR="$2"
        echo -e "${YELLOW}!!! Specific rebuild requested for: qmap_$TARGET_VENDOR${NC}"
    else
        FORCE_ALL=true
        echo -e "${RED}!!! Force mode enabled for ALL environments.${NC}"
    fi
fi

# Create a hidden directory for build logs
mkdir -p .build_logs

# 1. Initialize conda for bash scripting (bulletproof pathing)
eval "$(conda shell.bash hook)"
EXISTING_ENVS=$(conda env list | awk '{print $1}')

for entry in "${VENDORS[@]}"; do
    VENDOR="${entry%%:*}"
    YAML_FILE="${entry#*:}"
    ENV_NAME="qmap_$VENDOR"
    LOG_FILE=".build_logs/${ENV_NAME}.log"

    SHOULD_FORCE=false
    if [ "$FORCE_ALL" = true ] || [ "$TARGET_VENDOR" == "$VENDOR" ]; then
        SHOULD_FORCE=true
    fi

    echo "------------------------------------------"
    echo -e "Processing: ${CYAN}$ENV_NAME${NC}"

    if echo "$EXISTING_ENVS" | grep -w "$ENV_NAME" > /dev/null; then
        if [ "$SHOULD_FORCE" = true ]; then
            echo "-> Removing existing $ENV_NAME..."
            conda env remove -n "$ENV_NAME" -y > /dev/null 2>&1
        else
            echo "-> $ENV_NAME already exists. Skipping."
            SKIPPED_BUILDS="${SKIPPED_BUILDS}${ENV_NAME} "
            continue
        fi
    fi

    if [ -f "$YAML_FILE" ]; then
        echo "-> Building $ENV_NAME from $YAML_FILE (silenced)..."
        
        if conda env create -f "$YAML_FILE" -n "$ENV_NAME" > "$LOG_FILE" 2>&1; then
            echo "-> Installing local QMAP package (silenced)..."
            conda activate "$ENV_NAME"

            # Run pip quietly and append to the same log
            if pip install -q -e . >> "$LOG_FILE" 2>&1; then
                echo -e "-> ${GREEN}Successfully built $ENV_NAME${NC}"
                SUCCESSFUL_BUILDS="${SUCCESSFUL_BUILDS}${ENV_NAME} "
            else
                echo -e "-> ${RED}ERROR: Pip install failed for $ENV_NAME${NC}"
                echo -e "${YELLOW}--- Last 20 lines of log ---${NC}"
                tail -n 20 "$LOG_FILE"
                FAILED_BUILDS="${FAILED_BUILDS}${ENV_NAME} "
            fi
            
            conda deactivate
        else
            echo -e "-> ${RED}ERROR: Conda build failed for $ENV_NAME${NC}"
            echo -e "${YELLOW}--- Last 20 lines of log ---${NC}"
            tail -n 20 "$LOG_FILE"
            FAILED_BUILDS="${FAILED_BUILDS}${ENV_NAME} "
        fi
    else
        echo -e "-> ${YELLOW}WARNING: $YAML_FILE not found. Skipping.${NC}"
        FAILED_BUILDS="${FAILED_BUILDS}${ENV_NAME}(missing_file) "
    fi
done

echo "------------------------------------------"
echo "Cleaning up cached conda files..."
conda clean --all -y > /dev/null 2>&1

# 3. Explicit IF statements to avoid syntax token crashes
echo -e "${CYAN}------------------------------------------${NC}"
echo -e "${CYAN}BUILD SUMMARY${NC}"
echo -e "${CYAN}------------------------------------------${NC}"
if [ -n "$SUCCESSFUL_BUILDS" ]; then
    echo -e "${GREEN}✅ Successfully built:${NC} $SUCCESSFUL_BUILDS"
fi

if [ -n "$SKIPPED_BUILDS" ]; then
    echo -e "${CYAN}ℹ️  Already existed:${NC} $SKIPPED_BUILDS"
fi

if [ -n "$FAILED_BUILDS" ]; then
    echo -e "${RED}❌ FAILED builds:${NC} $FAILED_BUILDS"
    echo -e "${YELLOW}Check the terminal output above for specific pip or dependency errors.${NC}"
else
    echo -e "${GREEN}All requested environments are ready to go.${NC}"
fi
echo -e "${CYAN}------------------------------------------${NC}"
echo -e "${CYAN}To start, run: conda activate qmap_<vendor>${NC}"
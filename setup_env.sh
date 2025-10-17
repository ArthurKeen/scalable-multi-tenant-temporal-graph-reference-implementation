# Environment Setup Script for Interactive Demo
# 
# Usage: 
#   1. Copy environment_variables.example to setup_env.sh
#   2. Edit setup_env.sh with your ArangoDB credentials
#   3. Run: source setup_env.sh

echo "🔧 Setting up ArangoDB environment variables..."

# Update these values with your actual ArangoDB credentials
# DO NOT COMMIT THIS FILE WITH REAL CREDENTIALS!

export ARANGO_ENDPOINT='your-arango-endpoint'
export ARANGO_USERNAME='your-username'
export ARANGO_PASSWORD='your-secure-password' 
export ARANGO_DATABASE='your-database-name'

# For local ArangoDB, use these instead:
# export ARANGO_ENDPOINT='http://localhost:8529'
# export ARANGO_USERNAME='root'
# export ARANGO_PASSWORD='your-local-password'
# export ARANGO_DATABASE='network_assets_demo'

echo " Environment variables set:"
echo "   ARANGO_ENDPOINT: $ARANGO_ENDPOINT"
echo "   ARANGO_USERNAME: $ARANGO_USERNAME"
echo "   ARANGO_DATABASE: $ARANGO_DATABASE"
echo "   ARANGO_PASSWORD: [HIDDEN]"
echo ""
echo " Ready to run demo! Use: python3 demos/demo_launcher.py"

#!/bin/bash

# Debug script for Watchtower deployment issues

echo "================================================"
echo "Watchtower Deployment Debug Script"
echo "================================================"
echo ""

# 1. Check if Watchtower is running
echo "1. Checking Watchtower status..."
if docker ps | grep -q mizual-watchtower; then
    echo "✓ Watchtower is running"
    docker ps --format "table {{.Names}}\t{{.Status}}" | grep watchtower
else
    echo "✗ Watchtower is NOT running!"
    echo "Checking if it exists but stopped:"
    docker ps -a | grep watchtower
fi
echo ""

# 2. Check Watchtower logs
echo "2. Recent Watchtower logs (last 20 lines):"
docker logs mizual-watchtower --tail 20 2>&1 | grep -E "Scanned|Updated|Error|Warning|latest" || echo "No relevant logs found"
echo ""

# 3. Check registry availability
echo "3. Checking registry status..."
if curl -s -f http://localhost:5000/v2/ > /dev/null; then
    echo "✓ Registry is accessible at localhost:5000"
else
    echo "✗ Registry is NOT accessible!"
fi
echo ""

# 4. Check latest tags in registry
echo "4. Checking :latest tags in registry..."
BACKEND_TAGS=$(curl -s http://localhost:5000/v2/mizual-backend/tags/list 2>/dev/null)
CELERY_TAGS=$(curl -s http://localhost:5000/v2/mizual-celery/tags/list 2>/dev/null)

if echo "$BACKEND_TAGS" | grep -q '"latest"'; then
    echo "✓ Backend has :latest tag"
    # Get the digest of latest
    DIGEST=$(curl -s -H "Accept: application/vnd.docker.distribution.manifest.v2+json" \
        http://localhost:5000/v2/mizual-backend/manifests/latest 2>/dev/null | \
        python3 -c "import sys,json; data=json.load(sys.stdin); print(data.get('config',{}).get('digest','')[:19])" 2>/dev/null)
    echo "  Latest digest: $DIGEST"
else
    echo "✗ Backend missing :latest tag!"
    echo "  Available tags: $BACKEND_TAGS"
fi

if echo "$CELERY_TAGS" | grep -q '"latest"'; then
    echo "✓ Celery has :latest tag"
else
    echo "✗ Celery missing :latest tag!"
    echo "  Available tags: $CELERY_TAGS"
fi
echo ""

# 5. Check container images
echo "5. Current container images:"
echo "Backend:"
docker ps --format "{{.Names}}: {{.Image}}" | grep backend
BACKEND_ID=$(docker inspect mizual-backend --format='{{.Image}}' 2>/dev/null | cut -d: -f2 | cut -c1-12)
echo "  Container image ID: $BACKEND_ID"

echo "Celery:"
docker ps --format "{{.Names}}: {{.Image}}" | grep celery
CELERY_ID=$(docker inspect mizual-celery --format='{{.Image}}' 2>/dev/null | cut -d: -f2 | cut -c1-12)
echo "  Container image ID: $CELERY_ID"
echo ""

# 6. Check if containers have Watchtower label
echo "6. Checking Watchtower labels on containers..."
BACKEND_LABEL=$(docker inspect mizual-backend --format='{{.Config.Labels}}' 2>/dev/null | grep -o "com.centurylinklabs.watchtower.enable:true")
CELERY_LABEL=$(docker inspect mizual-celery --format='{{.Config.Labels}}' 2>/dev/null | grep -o "com.centurylinklabs.watchtower.enable:true")

if [ ! -z "$BACKEND_LABEL" ]; then
    echo "✓ Backend has Watchtower label"
else
    echo "✗ Backend missing Watchtower label!"
fi

if [ ! -z "$CELERY_LABEL" ]; then
    echo "✓ Celery has Watchtower label"
else
    echo "✗ Celery missing Watchtower label!"
fi
echo ""

# 7. Check docker-compose configuration
echo "7. Checking docker-compose configuration..."
if [ -f /opt/mizual/docker-compose.zero-downtime.yml ]; then
    echo "✓ docker-compose.zero-downtime.yml exists"
    # Check if images point to registry
    if grep -q "localhost:5000" /opt/mizual/docker-compose.zero-downtime.yml; then
        echo "✓ Compose file uses registry images"
    else
        echo "✗ Compose file doesn't use registry images!"
    fi
else
    echo "✗ docker-compose.zero-downtime.yml not found!"
fi
echo ""

# 8. Force Watchtower to check now
echo "8. Triggering immediate Watchtower check..."
if docker ps | grep -q mizual-watchtower; then
    docker kill -s SIGUSR1 mizual-watchtower 2>/dev/null && echo "✓ Sent SIGUSR1 signal to Watchtower" || echo "✗ Failed to signal Watchtower"
    echo "Waiting 10 seconds for Watchtower to process..."
    sleep 10
    echo "Recent Watchtower activity:"
    docker logs mizual-watchtower --tail 5 2>&1 | grep -E "Scanned|Updated|Checking"
else
    echo "✗ Cannot trigger - Watchtower not running"
fi
echo ""

# 9. Check version endpoint
echo "9. Checking version endpoint..."
VERSION_RESPONSE=$(curl -s http://localhost/version 2>/dev/null)
if [ ! -z "$VERSION_RESPONSE" ]; then
    echo "Version endpoint response:"
    echo "$VERSION_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$VERSION_RESPONSE"
else
    echo "✗ Version endpoint not responding"
fi
echo ""

# 10. Summary
echo "================================================"
echo "SUMMARY"
echo "================================================"

# Count issues
ISSUES=0
[ ! "$(docker ps | grep -q mizual-watchtower)" ] && ISSUES=$((ISSUES + 1)) && echo "• Watchtower not running"
[ ! "$(echo "$BACKEND_TAGS" | grep -q '"latest"')" ] && ISSUES=$((ISSUES + 1)) && echo "• Backend missing :latest tag"
[ ! "$(echo "$CELERY_TAGS" | grep -q '"latest"')" ] && ISSUES=$((ISSUES + 1)) && echo "• Celery missing :latest tag"
[ -z "$BACKEND_LABEL" ] && ISSUES=$((ISSUES + 1)) && echo "• Backend missing Watchtower label"
[ -z "$CELERY_LABEL" ] && ISSUES=$((ISSUES + 1)) && echo "• Celery missing Watchtower label"

if [ $ISSUES -eq 0 ]; then
    echo "✓ No issues found - Watchtower should be working"
    echo ""
    echo "If updates are still not happening, check:"
    echo "1. Watchtower poll interval (currently 1 minute)"
    echo "2. Registry manifest cache"
    echo "3. Container restart policies"
else
    echo ""
    echo "Found $ISSUES issue(s) that need to be fixed"
fi

echo ""
echo "To manually update containers:"
echo "  docker-compose -f /opt/mizual/docker-compose.zero-downtime.yml pull"
echo "  docker-compose -f /opt/mizual/docker-compose.zero-downtime.yml up -d"
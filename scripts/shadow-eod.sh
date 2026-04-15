#!/bin/bash
# Shadow EOD — runs automatically at 3:45 PM IST via cron
cd ~/trading-platform

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S IST')
LOG="~/trading-platform/logs/shadow-eod.log"

echo "[$TIMESTAMP] Running shadow EOD..." >> ~/trading-platform/logs/shadow-eod.log

RESULT=$(curl -s -X POST https://truegrowth.ninja/api/shadow/run-eod)
SUCCESS=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('success', False))" 2>/dev/null)

echo "[$TIMESTAMP] Result: $RESULT" >> ~/trading-platform/logs/shadow-eod.log

if [ "$SUCCESS" = "True" ]; then
  echo "[$TIMESTAMP] Shadow EOD completed successfully." >> ~/trading-platform/logs/shadow-eod.log
else
  echo "[$TIMESTAMP] Shadow EOD FAILED — check logs." >> ~/trading-platform/logs/shadow-eod.log
fi

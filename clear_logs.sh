#!/bin/bash
# Clear all LocalWriter log files in every known location.
# Filenames: localwriter_debug.log, localwriter_agent.log (see core/logging.py).

LO="${HOME}/.config/libreoffice"
rm -f \
  "${HOME}/localwriter_debug.log" \
  "${HOME}/localwriter_agent.log" \
  "${LO}/4/user/localwriter_debug.log" \
  "${LO}/4/user/localwriter_agent.log" \
  "${LO}/4/user/config/localwriter_debug.log" \
  "${LO}/4/user/config/localwriter_agent.log" \
  "${LO}/24/user/localwriter_debug.log" \
  "${LO}/24/user/localwriter_agent.log" \
  "${LO}/24/user/config/localwriter_debug.log" \
  "${LO}/24/user/config/localwriter_agent.log"
echo "Logs deleted."

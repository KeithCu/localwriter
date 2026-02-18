#!/bin/bash
rm -f ~/log.txt ~/localwriter_agent_debug.log \
  ~/.config/libreoffice/4/user/config/localwriter_chat_debug.log \
  ~/.config/libreoffice/4/user/localwriter_chat_debug.log \
  /tmp/localwriter_agent_debug.log /tmp/localwriter_chat_debug.log \
  /tmp/localwriter_markdown_debug.log
echo "Logs deleted."
